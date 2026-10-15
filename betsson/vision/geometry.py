"""Conversión de rectángulos en fracciones del canvas (betsson.core.Rect) a puntos y píxeles."""
from __future__ import annotations

from betsson.core import Rect


def center(rect: Rect) -> tuple[float, float]:
    """Centro del rectángulo, en fracciones."""
    return (rect.x + rect.w / 2, rect.y + rect.h / 2)


def to_pixels(rect: Rect, width: int, height: int) -> tuple[int, int, int, int]:
    """(x0, y0, x1, y1) en píxeles para una imagen concreta."""
    return (int(rect.x * width), int(rect.y * height), int((rect.x + rect.w) * width), int((rect.y + rect.h) * height))


def contains(rect: Rect, point: tuple[float, float]) -> bool:
    x, y = point
    return rect.x <= x <= rect.x + rect.w and rect.y <= y <= rect.y + rect.h
