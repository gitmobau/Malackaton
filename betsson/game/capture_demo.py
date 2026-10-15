"""Captura los estados de un juego desde su demo pública (sin registro, sin cuentas) para fixtures/<perfil>/.

Uso:  python -m betsson.game.capture_demo --profile <nombre> [--spins 6] [--channel chrome]

Guarda carga, inicio, reposo, girando y fin de cada tirada, más un manifest.json con el texto OCR
de cada captura. Los valores esperados (expected) se rellenan a mano revisando las imágenes.
Ritmo humano: entre acciones se espera a señales visibles (cambio o estabilidad), nunca un tiempo fijo.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import cv2
import numpy as np

from betsson.game.sources import PlaywrightCanvasSource
from betsson.profiles.registry import get_profile
from betsson.vision.diff import change_ratio
from betsson.vision.ocr import full_text, read_text

VIEWPORT = {"width": 1366, "height": 768}
_LOAD_TIMEOUT_S = 90
_STABLE_THRESHOLD = 0.004


def find_game_canvas(page, timeout_s: float = _LOAD_TIMEOUT_S):  # noqa: ANN001, ANN201 - tipos de Playwright
    """El canvas más grande de la página o de cualquiera de sus iframes."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        best, best_area = None, 0.0
        for frame in page.frames:
            for canvas in frame.locator("canvas").all():
                box = canvas.bounding_box()
                if box and box["width"] * box["height"] > best_area:
                    best, best_area = canvas, box["width"] * box["height"]
        if best is not None and best_area > 200 * 200:
            return best
        # Un juego nunca llega a "networkidle": se espera a que aparezca algún canvas en cualquier frame.
        for frame in page.frames:
            try:
                frame.wait_for_selector("canvas", state="attached", timeout=3_000)
                break
            except Exception:  # noqa: BLE001 - frame sin canvas todavía o ya desmontado
                continue
    raise TimeoutError("no aparece el canvas del juego")


def wait_stable(source: PlaywrightCanvasSource, frames: int, timeout_s: float) -> np.ndarray:
    start = time.monotonic()
    previous = source.grab()
    stable = 0
    while time.monotonic() - start < timeout_s:
        current = source.grab()
        stable = stable + 1 if change_ratio(previous, current) <= _STABLE_THRESHOLD else 0
        previous = current
        if stable >= frames:
            break
    return previous


def wait_change(source: PlaywrightCanvasSource, reference: np.ndarray, timeout_s: float) -> np.ndarray | None:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        frame = source.grab()
        if change_ratio(reference, frame) > _STABLE_THRESHOLD:
            return frame
    return None


class Recorder:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.out.mkdir(parents=True, exist_ok=True)
        self.entries: list[dict] = []

    def save(self, name: str, frame: np.ndarray, note: str = "") -> None:
        path = self.out / f"{len(self.entries):02d}_{name}.png"
        cv2.imwrite(str(path), frame)
        text = full_text(read_text(frame))
        self.entries.append({"file": path.name, "state": name, "note": note, "ocr": text, "expected": {}})
        print(f"[captura] {path.name}: {text[:160]}")

    def write_manifest(self, meta: dict) -> None:
        manifest = {"meta": meta, "captures": self.entries}
        (self.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run(profile_name: str, out: Path, spins: int, channel: str | None) -> None:
    from playwright.sync_api import sync_playwright

    profile = get_profile(profile_name)
    if not profile.demo_url:
        raise SystemExit(f"el perfil '{profile_name}' no tiene demo_url")
    recorder = Recorder(out)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel=channel)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        page.goto(profile.demo_url, wait_until="domcontentloaded")
        canvas = find_game_canvas(page)
        source = PlaywrightCanvasSource(page, canvas)
        recorder.save("carga", source.grab())
        recorder.save("inicio", wait_stable(source, frames=8, timeout_s=_LOAD_TIMEOUT_S))

        from betsson.game.eyes import GameEyes  # import tardío: GameEyes no hace falta para capturar la carga

        eyes = GameEyes(source, profile, lang="es", parse_money=lambda _t: None)
        dismissed = eyes.dismiss_intro()
        recorder.save("reposo", wait_stable(source, frames=6, timeout_s=30), note=f"intro cerradas: {dismissed}")

        for i in range(1, spins + 1):
            before = wait_stable(source, frames=6, timeout_s=30)
            if eyes.locate_spin(before) is not None:
                eyes.spin()
            elif profile.spin_key:
                source.press(profile.spin_key)
            moving = wait_change(source, before, timeout_s=5)
            if moving is not None:
                recorder.save(f"girando_{i}", moving)
            recorder.save(f"fin_{i}", wait_stable(source, frames=8, timeout_s=40), note="; ".join(eyes.notes))
        recorder.write_manifest({"profile": profile.name, "url": page.url.split("?")[0], "viewport": VIEWPORT})
        browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--spins", type=int, default=6)
    parser.add_argument("--channel", default=None, help="'chrome' para usar el Chrome instalado")
    args = parser.parse_args()
    run(args.profile, args.out or Path("fixtures") / args.profile, args.spins, args.channel)


if __name__ == "__main__":
    main()
