"""Cambio visual entre frames: señal de que la tirada empezó y de que terminó."""
from __future__ import annotations

import cv2
import numpy as np

# Se compara a resolución reducida y en gris: rápido y poco sensible al ruido de compresión.
_COMPARE_WIDTH = 320
_PIXEL_NOISE = 12  # diferencia de gris por debajo de la cual un píxel "no cambia"


def _prepare(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    scale = _COMPARE_WIDTH / gray.shape[1]
    small = cv2.resize(gray, (_COMPARE_WIDTH, max(1, int(gray.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    return cv2.GaussianBlur(small, (3, 3), 0)


def change_ratio(a: np.ndarray, b: np.ndarray) -> float:
    """Fracción de píxeles que cambian de forma apreciable entre dos frames (0..1)."""
    pa, pb = _prepare(a), _prepare(b)
    if pa.shape != pb.shape:
        pb = cv2.resize(pb, (pa.shape[1], pa.shape[0]))
    delta = cv2.absdiff(pa, pb)
    return float(np.count_nonzero(delta > _PIXEL_NOISE)) / delta.size


def is_moving(a: np.ndarray, b: np.ndarray, threshold: float) -> bool:
    return change_ratio(a, b) > threshold
