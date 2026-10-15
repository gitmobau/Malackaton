"""Repetición del escenario: GIF animado con los fotogramas del canvas del juego.

Solo usa los fotogramas numerados que guardan los ojos del juego (NNN_<paso>.png), en su
orden. Nunca las capturas de la web de Betsson (saldo, diálogos), que pueden mostrar datos
de la cuenta. Sin vídeo de Playwright ni traza: se monta a partir de lo que ya está guardado.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

REPLAY_FILE = "replay.gif"
FRAME_PATTERN = re.compile(r"^(\d{3})_[\w-]+\.png$")
WIDTH = 480  # px: suficiente para ver el canvas y ligero para el repo
FRAME_MS = 700
LAST_FRAME_MS = 2000


def canvas_frames(folder: Path) -> list[Path]:
    """Fotogramas del canvas de una carpeta de escenario, en orden de captura."""
    frames = [p for p in folder.iterdir() if p.is_file() and FRAME_PATTERN.match(p.name)]
    return sorted(frames, key=lambda p: int(FRAME_PATTERN.match(p.name).group(1)))  # type: ignore[union-attr]


def _scaled(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    height = max(1, round(img.height * WIDTH / img.width))
    return img.resize((WIDTH, height), Image.Resampling.LANCZOS)


def make_replay(folder: Path) -> Path | None:
    """Crea <folder>/replay.gif con los fotogramas del canvas. None si hay menos de dos."""
    frames = canvas_frames(folder)
    if len(frames) < 2:
        return None
    images = [_scaled(p) for p in frames]
    size = images[0].size
    images = [im if im.size == size else im.resize(size) for im in images]
    durations = [FRAME_MS] * (len(images) - 1) + [LAST_FRAME_MS]
    path = folder / REPLAY_FILE
    images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0, optimize=True)
    return path
