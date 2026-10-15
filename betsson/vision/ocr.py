"""OCR sobre el canvas con RapidOCR. Devuelve cajas de texto en píxeles del frame original."""
from __future__ import annotations

import hashlib
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np


@dataclass(frozen=True)
class TextBox:
    text: str
    score: float
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    @property
    def norm(self) -> str:
        return normalize(self.text)


def normalize(text: str) -> str:
    """Mayúsculas sin tildes ni espacios repetidos: 'Crédito ' -> 'CREDITO'."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.upper().split())


@lru_cache(maxsize=1)
def _engine():  # noqa: ANN202 - tipo de un paquete externo
    try:  # rapidocr v3 (funciona en Python 3.14)
        from rapidocr import RapidOCR
    except ImportError:  # rapidocr-onnxruntime v1 (Python < 3.13)
        from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()


def _raw_results(image: np.ndarray) -> list[tuple]:
    """(puntos, texto, score) con independencia de la versión de RapidOCR."""
    output = _engine()(image)
    if isinstance(output, tuple):  # v1: (resultados, tiempos)
        return list(output[0] or [])
    if getattr(output, "boxes", None) is None:  # v3 sin texto
        return []
    return list(zip(output.boxes, output.txts, output.scores))


_CACHE_SIZE = 16
_cache: OrderedDict[tuple[str, tuple[int, ...], float, float], tuple[TextBox, ...]] = OrderedDict()


def read_text(frame: np.ndarray, upscale: float = 1.0, min_score: float = 0.5) -> list[TextBox]:
    """Todas las cajas de texto del frame (BGR). upscale > 1 ayuda con textos pequeños del canvas.

    Se cachea por un hash corto del contenido: leer saldo, apuesta y ganancia del mismo frame solo hace
    un OCR, sin retener los frames enteros como clave.
    """
    contiguous = np.ascontiguousarray(frame)
    key = (hashlib.blake2b(contiguous.tobytes(), digest_size=16).hexdigest(), contiguous.shape, upscale, min_score)
    if key in _cache:
        _cache.move_to_end(key)
        return list(_cache[key])
    boxes = tuple(_read_uncached(contiguous, upscale, min_score))
    _cache[key] = boxes
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return list(boxes)


def _read_uncached(frame: np.ndarray, upscale: float, min_score: float) -> list[TextBox]:
    image = frame
    if upscale != 1.0:
        image = cv2.resize(frame, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
    boxes: list[TextBox] = []
    for points, text, score in _raw_results(image):
        if float(score) < min_score or not str(text).strip():
            continue
        xs = [p[0] / upscale for p in points]
        ys = [p[1] / upscale for p in points]
        boxes.append(TextBox(str(text).strip(), float(score), int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
    return boxes


def full_text(boxes: list[TextBox]) -> str:
    """Texto de las cajas en orden de lectura (filas de arriba abajo, de izquierda a derecha)."""
    ordered = sorted(boxes, key=lambda b: (round(b.cy / max(b.height, 1)), b.x0))
    return " ".join(b.text for b in ordered)
