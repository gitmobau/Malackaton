"""Errores que distinguen la causa de un fallo."""
from __future__ import annotations

from pathlib import Path

PROVIDER_UI_CHANGED = "PROVIDER_UI_CHANGED"


class GameOpenError(Exception):
    """La web de Betsson no pudo abrir el juego en Real Play (A). Es fallo de integración."""


class ProviderUIChanged(Exception):
    """El perfil de un proveedor conocido ya no reconoce su juego (deriva).

    Lo lanza ProviderRegistry.ensure_recognized() (B). Un proveedor desconocido no
    lo lanza: resolve() devuelve generic-vision. No es un fallo de integración de
    Betsson: las comprobaciones de pantalla quedan como FAIL no concluyente con
    failure_kind="provider_ui_changed" (reason "PROVIDER_UI_CHANGED: …") y un aviso.
    """

    code = PROVIDER_UI_CHANGED

    def __init__(self, reason: str, evidence: list[Path] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.evidence = list(evidence or [])
