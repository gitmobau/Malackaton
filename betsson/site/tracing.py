"""Pausar la traza de Playwright mientras se escriben y envían credenciales.

OJO: `tracing.stop_chunk()` NO basta. Playwright sigue registrando la red con el trozo
parado y la vuelca en el siguiente: el POST del login (usuario y contraseña en el cuerpo)
acababa dentro del trace.zip (lo detectó scan_secrets el 15-oct). Por eso la pausa
DETIENE la traza del todo (`tracing.stop`) y la reanuda con una traza nueva: lo que pasa
durante el login no se graba en ningún archivo, tampoco la red.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Protocol

from playwright.sync_api import BrowserContext

DEFAULT_TRACE_OPTIONS: dict[str, Any] = {"screenshots": True, "snapshots": True, "sources": False}


class TraceControl(Protocol):
    def pause(self) -> None: ...
    def resume(self) -> None: ...


class NoTrace:
    """Para cuando no se graba traza."""

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None


class SegmentedTrace:
    """Traza en segmentos: <out_dir>/trace-0.zip, trace-1.zip… con huecos donde hubo pausa.

    Arranca la traza ella misma (no llames antes a context.tracing.start) y hay que cerrarla con close().
    """

    def __init__(self, context: BrowserContext, out_dir: Path, **options: Any) -> None:
        self._context = context
        self._out_dir = out_dir
        self._options = {**DEFAULT_TRACE_OPTIONS, **options}
        self._segment = 0
        self._running = False
        self._start()

    def _start(self) -> None:
        self._context.tracing.start(**self._options)
        self._running = True

    def _stop(self) -> None:
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._context.tracing.stop(path=self._out_dir / f"trace-{self._segment}.zip")
        self._segment += 1
        self._running = False

    def pause(self) -> None:
        if self._running:
            self._stop()

    def resume(self) -> None:
        if not self._running:
            self._start()

    def close(self) -> None:
        if self._running:
            self._stop()


@contextmanager
def trace_paused(trace: TraceControl) -> Iterator[None]:
    trace.pause()
    try:
        yield
    finally:
        trace.resume()
