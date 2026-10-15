"""Búsqueda de un control (p. ej. el botón de girar) con plantillas a varias escalas."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

DEFAULT_SCALES: tuple[float, ...] = tuple(round(0.5 + 0.1 * i, 2) for i in range(11))  # 0.5 .. 1.5
DEFAULT_MIN_SCORE = 0.7


@dataclass(frozen=True)
class TemplateMatch:
    score: float
    center: tuple[float, float]  # fracción del canvas
    scale: float
    template: str


def load_template(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"no se puede leer la plantilla {path}")
    return image


def _edges(gray: np.ndarray) -> np.ndarray:
    # Bordes en vez de color: aguanta recoloreados y cambios de brillo del proveedor.
    # Se engrosan y difuminan para tolerar el cambio de grosor de las líneas al reescalar.
    edges = cv2.dilate(cv2.Canny(gray, 50, 150), np.ones((3, 3), np.uint8))
    return cv2.GaussianBlur(edges, (5, 5), 0)


def find_template(
    frame: np.ndarray,
    templates: list[Path],
    scales: tuple[float, ...] = DEFAULT_SCALES,
    min_score: float = DEFAULT_MIN_SCORE,
) -> TemplateMatch | None:
    """Mejor coincidencia de cualquiera de las plantillas a cualquier escala, o None si no supera min_score.

    Las escalas son relativas a un canvas de 1366 px de ancho, el tamaño con que se recortaron.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    height, width = gray.shape
    canvas_scale = width / 1366
    frame_edges = _edges(gray)
    best: TemplateMatch | None = None
    for path in templates:
        base = load_template(path)
        for scale in scales:
            factor = scale * canvas_scale
            tw, th = int(base.shape[1] * factor), int(base.shape[0] * factor)
            if tw < 12 or th < 12 or tw > width or th > height:
                continue
            resized = cv2.resize(base, (tw, th), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(frame_edges, _edges(resized), cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(result)
            if best is None or score > best.score:
                center = ((loc[0] + tw / 2) / width, (loc[1] + th / 2) / height)
                best = TemplateMatch(float(score), center, scale, path.name)
    if best is None or best.score < min_score:
        return None
    return best
