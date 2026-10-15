"""Pausar la traza de Playwright mientras se escriben credenciales.

La traza graba los valores escritos en `fill`, así que durante el login se corta el
trozo actual y se abre uno nuevo al terminar: el login no queda en ningún archivo.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

from playwright.sync_api import BrowserContext


class TraceControl(Protocol):
    def pause(self) -> None: ...
    def resume(self) -> None: ...


class NoTrace:
    """Para cuando no se graba traza."""

    def pause(self) -> None:
        return None

    def resume(self) -> None:
        return None


class ChunkedTrace:
    """Requiere `context.tracing.start(screenshots=..., snapshots=...)` ya llamado por quien crea el contexto.

    Cada pausa guarda el trozo hasta ese momento en `<out_dir>/trace-<n>.zip`.
    """

    def __init__(self, context: BrowserContext, out_dir: Path) -> None:
        self._context = context
        self._out_dir = out_dir
        self._chunk = 0
        self._paused = False

    def pause(self) -> None:
        if self._paused:
            return
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._context.tracing.stop_chunk(path=self._out_dir / f"trace-{self._chunk}.zip")
        self._chunk += 1
        self._paused = True

    def resume(self) -> None:
        if not self._paused:
            return
        self._context.tracing.start_chunk(title=f"chunk-{self._chunk}")
        self._paused = False


@contextmanager
def trace_paused(trace: TraceControl) -> Iterator[None]:
    trace.pause()
    try:
        yield
    finally:
        trace.resume()
