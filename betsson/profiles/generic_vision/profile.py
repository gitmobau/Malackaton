"""Perfil de respaldo para proveedores desconocidos: solo etiquetas habituales del sector, sin plantillas.

Más adelante, VisionProvider (IA con visión, opcional) localizará aquí el botón de girar.
"""
from __future__ import annotations

from betsson.core import Rect
from betsson.profiles.base import IntroStep, ProfileSpec

PROFILE = ProfileSpec(
    name="generic-vision",
    # Presentación típica: casilla "no volver a mostrar" y botón continuar. Si no se lee el botón, centro abajo.
    intro_screens=[
        IntroStep(
            name="presentacion",
            match_texts=("NO VOLVER A MOSTRAR", "DON'T SHOW AGAIN", "DO NOT SHOW", "PULSA PARA CONTINUAR"),
            click_text="CONTINUAR",
            click=Rect(x=0.40, y=0.70, w=0.20, h=0.15),
        ),
    ],
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
