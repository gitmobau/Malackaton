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

import hashlib
import os
import re
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
MAX_ASPECT_DIFF = 0.05  # si el canvas cambia de proporción, la huella no es comparable
_TOKENISH = re.compile(r"^[A-Za-z0-9_\-=.]{17,}$")  # segmentos de ruta que parecen ids o tokens


def _now() -> datetime:
    return datetime.now(timezone.utc)


class GameFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    market: str
    game: str
    provider: str | None = None
    iframe_path: str  # esquema + host + ruta, sin query ni fragmento y con tokens tapados
    controls_hash: str
    canvas_w: int = 0
    canvas_h: int = 0
    run_id: str
    created_at: datetime = Field(default_factory=_now)


def iframe_path(url: str) -> str:
    parts = urlsplit(url)
    path = "/".join("*" if _TOKENISH.match(seg) else seg for seg in parts.path.split("/"))
    return f"{parts.scheme}://{parts.netloc}{path}"


def _rgb(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return np.stack([frame] * 3, axis=-1)
    return frame[:, :, :3]


def _controls(frame: np.ndarray) -> Image.Image:
    rgb = _rgb(frame)
    top = int(rgb.shape[0] * (1 - CONTROLS_BAND))
    return Image.fromarray(rgb[top:].astype(np.uint8))


def take(frame: np.ndarray, *, iframe_url: str, market: str, game: str, provider: str | None,
         run_id: str) -> GameFingerprint:
    return GameFingerprint(
        market=market, game=game, provider=provider, iframe_path=iframe_path(iframe_url),
        controls_hash=str(imagehash.phash(_controls(frame), hash_size=HASH_SIZE)), run_id=run_id,
        canvas_w=int(frame.shape[1]), canvas_h=int(frame.shape[0]),
    )


def comparable(before: GameFingerprint, now: GameFingerprint) -> bool:
    if not (before.canvas_w and before.canvas_h and now.canvas_w and now.canvas_h):
        return True
    a, b = before.canvas_w / before.canvas_h, now.canvas_w / now.canvas_h
    return abs(a - b) / a <= MAX_ASPECT_DIFF


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

    @staticmethod
    def _safe(name: str) -> str:
        if not name.strip():
            raise ValueError("nombre vacío para la huella")
        clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
        return f"{clean}-{hashlib.sha1(name.encode()).hexdigest()[:8]}"

    def _paths(self, market: str, game: str) -> tuple[Path, Path]:
        base = self.root / self._safe(market) / self._safe(game)
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
        tmp_image, tmp_meta = image.with_suffix(".png.tmp"), meta.with_suffix(".json.tmp")
        _controls(frame).save(tmp_image, format="PNG")
        tmp_meta.write_text(fp.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp_image, image)  # primero la imagen, después el json que la referencia
        os.replace(tmp_meta, meta)


def _drift_evidence(frame: np.ndarray, before_image: Path, out_dir: Path) -> tuple[Path, ...]:
    """Capturas de antes y ahora en out_dir. Un fallo al copiar solo quita esa captura."""
    paths: list[Path] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        if before_image.exists():
            shutil.copyfile(before_image, out_dir / BEFORE_FILE)
            paths.append(out_dir / BEFORE_FILE)
    except OSError:
        pass  # sin la captura de antes el aviso sigue siendo válido
    now_path = out_dir / NOW_FILE
    _controls(frame).save(now_path)
    return (*paths, now_path)


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
        if not comparable(before, fp):
            warnings.append(f"huella no comparable: el canvas pasó de {before.canvas_w}x{before.canvas_h} "
                            f"a {fp.canvas_w}x{fp.canvas_h}")
            reasons: list[str] = []
        else:
            reasons = compare(before, fp)
        if reasons:
            evidence = _drift_evidence(frame, before_image, out_dir)
            warnings.append(f"el juego del proveedor ha cambiado desde la última ejecución ({before.run_id}): "
                            + "; ".join(reasons))
    if update:
        store.save(fp, frame)
    return warnings, evidence
