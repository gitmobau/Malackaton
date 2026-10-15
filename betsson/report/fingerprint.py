"""Huella de referencia por juego: detecta que el juego del proveedor ha cambiado.

Se compara con la última ejecución buena del mismo juego y mercado:
- hash perceptual de la franja de controles (parte inferior del canvas: saldo,
  apuesta, botón de girar), que no cambia entre tiradas (los rodillos sí, por eso
  no se usan);
- ruta del iframe sin query (la query puede llevar tokens de sesión y nunca se guarda).

Un cambio no altera el veredicto: es un aviso "el juego del proveedor ha cambiado
desde la última ejecución" con las capturas de antes y después.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import imagehash
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

CONTROLS_BAND = 0.2  # fracción inferior del canvas
HASH_SIZE = 8  # 64 bits
MAX_DISTANCE = 10  # bits distintos tolerados en la franja de controles
BEFORE_FILE = "fingerprint_before.png"
NOW_FILE = "fingerprint_now.png"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GameFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    market: str
    game: str
    provider: str | None = None
    iframe_path: str  # esquema + host + ruta, sin query ni fragmento
    controls_hash: str
    run_id: str
    created_at: datetime = Field(default_factory=_now)


def iframe_path(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def _controls(frame: np.ndarray) -> Image.Image:
    height = frame.shape[0]
    top = int(height * (1 - CONTROLS_BAND))
    return Image.fromarray(frame[top:, :, :3].astype(np.uint8))


def take(frame: np.ndarray, *, iframe_url: str, market: str, game: str, provider: str | None,
         run_id: str) -> GameFingerprint:
    return GameFingerprint(
        market=market, game=game, provider=provider, iframe_path=iframe_path(iframe_url),
        controls_hash=str(imagehash.phash(_controls(frame), hash_size=HASH_SIZE)), run_id=run_id,
    )


def compare(before: GameFingerprint, now: GameFingerprint) -> list[str]:
    """Motivos de cambio (vacío si es el mismo juego)."""
    reasons = []
    distance = imagehash.hex_to_hash(before.controls_hash) - imagehash.hex_to_hash(now.controls_hash)
    if distance > MAX_DISTANCE:
        reasons.append(f"la franja de controles ha cambiado ({distance} de {HASH_SIZE ** 2} bits)")
    if before.iframe_path != now.iframe_path:
        reasons.append(f"la ruta del juego ha cambiado: {before.iframe_path} → {now.iframe_path}")
    if before.provider and now.provider and before.provider != now.provider:
        reasons.append(f"el perfil detectado ha cambiado: {before.provider} → {now.provider}")
    return reasons


class BaselineStore:
    """Huellas en <root>/<market>/<game>.json (+ .png). En el runner propio persiste entre runs."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _paths(self, market: str, game: str) -> tuple[Path, Path]:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in game)
        base = self.root / market / safe
        return base.with_suffix(".json"), base.with_suffix(".png")

    def load(self, market: str, game: str) -> tuple[GameFingerprint, Path] | None:
        meta, image = self._paths(market, game)
        if not meta.exists():
            return None
        try:
            return GameFingerprint.model_validate_json(meta.read_text(encoding="utf-8")), image
        except ValueError:
            return None  # huella ilegible: se trata como si no hubiera referencia

    def save(self, fp: GameFingerprint, frame: np.ndarray) -> None:
        meta, image = self._paths(fp.market, fp.game)
        meta.parent.mkdir(parents=True, exist_ok=True)
        _controls(frame).save(image)
        meta.write_text(fp.model_dump_json(indent=2), encoding="utf-8")


def check_drift(store: BaselineStore, frame: np.ndarray, fp: GameFingerprint, out_dir: Path,
                update: bool) -> tuple[list[str], tuple[Path, ...]]:
    """Compara con la referencia. Devuelve (avisos, evidencias en out_dir). update=True guarda la nueva."""
    previous = store.load(fp.market, fp.game)
    warnings: list[str] = []
    evidence: tuple[Path, ...] = ()
    if previous is None:
        warnings.append("huella de referencia del juego creada en esta ejecución" if update
                        else "sin huella de referencia del juego (se crea con la primera ejecución en PASS)")
    else:
        before, before_image = previous
        reasons = compare(before, fp)
        if reasons:
            out_dir.mkdir(parents=True, exist_ok=True)
            now_path = out_dir / NOW_FILE
            _controls(frame).save(now_path)
            paths = [now_path]
            if before_image.exists():
                shutil.copyfile(before_image, out_dir / BEFORE_FILE)
                paths.insert(0, out_dir / BEFORE_FILE)
            evidence = tuple(paths)
            warnings.append(f"el juego del proveedor ha cambiado desde la última ejecución ({before.run_id}): "
                            + "; ".join(reasons))
    if update:
        store.save(fp, frame)
    return warnings, evidence
