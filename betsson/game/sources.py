"""De dónde salen los frames del juego y cómo se interactúa con él, "como un jugador".

- PlaywrightCanvasSource: el canvas real dentro del iframe del juego (ratón y teclado de verdad).
- FileFrameSource: una secuencia de capturas de fixtures/<proveedor>/, para tests sin navegador.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


class FrameSource(Protocol):
    def grab(self) -> np.ndarray:
        """Frame actual del canvas en BGR."""
        ...

    def click(self, fx: float, fy: float) -> None:
        """Clic en una posición del canvas expresada en fracciones (0..1)."""
        ...

    def press(self, key: str) -> None:
        ...


def decode_png(data: bytes) -> np.ndarray:
    frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("no se pudo decodificar la captura del canvas")
    return frame


def read_image(path: Path) -> np.ndarray:
    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        raise FileNotFoundError(f"no se puede leer la imagen {path}")
    return frame


class PlaywrightCanvasSource:
    """Canvas del juego en una página de Playwright. `locator` apunta al canvas (o al iframe que lo contiene)."""

    def __init__(self, page, locator) -> None:  # noqa: ANN001 - tipos de Playwright
        self._page = page
        self._locator = locator

    def grab(self) -> np.ndarray:
        return decode_png(self._locator.screenshot(animations="allow", timeout=10_000))

    def click(self, fx: float, fy: float) -> None:
        box = self._locator.bounding_box()
        if box is None:
            raise RuntimeError("el canvas del juego no está visible")
        self._page.mouse.click(box["x"] + fx * box["width"], box["y"] + fy * box["height"])

    def press(self, key: str) -> None:
        # El canvas no siempre es enfocable: la tecla va a la página, que la reenvía al juego.
        self._page.keyboard.press(key)


class HandleFrameSource:
    """Canvas del juego a partir del GameHandle de core (lo devuelve BetssonSite.open_game, área A).

    capture() del handle es RGB y el motor trabaja en BGR (OpenCV). Para pulsar se usa el canvas
    (Locator de Playwright) que el handle de A expone.
    """

    def __init__(self, handle) -> None:  # noqa: ANN001 - betsson.core.GameHandle
        canvas = getattr(handle, "canvas", None)
        if canvas is None:
            raise TypeError("el GameHandle no expone 'canvas': GameEyes no puede pulsar en el juego")
        self._handle = handle
        self._clicker = PlaywrightCanvasSource(canvas.page, canvas)

    def grab(self) -> np.ndarray:
        return cv2.cvtColor(np.ascontiguousarray(self._handle.capture()), cv2.COLOR_RGB2BGR)

    def click(self, fx: float, fy: float) -> None:
        self._clicker.click(fx, fy)

    def press(self, key: str) -> None:
        self._clicker.press(key)


class FileFrameSource:
    """Reproduce capturas en orden: cada grab() avanza un frame y el último se repite.

    Los clics y teclas se registran para que los tests comprueben dónde habría pulsado el jugador.
    """

    def __init__(self, frames: list[np.ndarray | Path]) -> None:
        if not frames:
            raise ValueError("FileFrameSource necesita al menos un frame")
        self._frames = [read_image(f) if isinstance(f, Path) else f for f in frames]
        self._index = 0
        self.clicks: list[tuple[float, float]] = []
        self.keys: list[str] = []

    def grab(self) -> np.ndarray:
        frame = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        return frame

    def click(self, fx: float, fy: float) -> None:
        self.clicks.append((fx, fy))

    def press(self, key: str) -> None:
        self.keys.append(key)
