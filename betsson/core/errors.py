"""Errores que distinguen la causa de un fallo."""
from __future__ import annotations

from pathlib import Path

PROVIDER_UI_CHANGED = "PROVIDER_UI_CHANGED"


class ProviderUIChanged(Exception):
    """Ningún perfil reconoce el juego (ni recalibrando, ni con generic-vision).

    No es un fallo de integración de Betsson: las comprobaciones de pantalla
    quedan como FAIL no concluyente con failure_kind="provider_ui_changed" y un
    aviso para mantener el perfil.
    """

    code = PROVIDER_UI_CHANGED

    def __init__(self, reason: str, evidence: list[Path] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.evidence = list(evidence or [])
