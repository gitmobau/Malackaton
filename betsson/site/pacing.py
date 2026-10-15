"""Ritmo humano: al menos N segundos entre cargas de página (robots.txt: Crawl-delay 2).

No es una espera a la interfaz (esas van con señales): es un límite de ritmo hacia el servidor.
"""
from __future__ import annotations

import time

MIN_SECONDS_BETWEEN_LOADS = 2.0


class Pacer:
    def __init__(self, min_interval: float = MIN_SECONDS_BETWEEN_LOADS) -> None:
        self._min_interval = min_interval
        self._last: float | None = None

    def wait_turn(self) -> None:
        now = time.monotonic()
        if self._last is not None:
            remaining = self._min_interval - (now - self._last)
            if remaining > 0:
                time.sleep(remaining)
        self._last = time.monotonic()
