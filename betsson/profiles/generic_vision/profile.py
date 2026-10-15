"""Perfil de respaldo para proveedores desconocidos: solo etiquetas habituales del sector, sin plantillas.

Más adelante, VisionProvider (IA con visión, opcional) localizará aquí el botón de girar.
"""
from __future__ import annotations

from betsson.core import Rect
from betsson.profiles.base import ProfileSpec

PROFILE = ProfileSpec(
    name="generic-vision",
    labels={
        "balance": {"es": ["SALDO", "CRÉDITO", "BALANCE"], "en": ["BALANCE", "CREDIT", "CASH"]},
        "bet": {"es": ["APUESTA", "APUESTA TOTAL"], "en": ["BET", "TOTAL BET", "STAKE"]},
        "win": {"es": ["GANANCIA", "PREMIO"], "en": ["WIN", "LAST WIN", "PAID"]},
    },
    spin_hint=Rect(x=0.40, y=0.75, w=0.60, h=0.25),
    spin_key="Space",
    message_dismiss_texts=["ACEPTAR", "ACCEPT", "OK", "CERRAR", "CLOSE"],
    insufficient_texts={
        "es": ["SALDO INSUFICIENTE", "FONDOS INSUFICIENTES"],
        "en": ["INSUFFICIENT", "NOT ENOUGH"],
    },
)
