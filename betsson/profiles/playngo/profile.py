"""Perfil de Play'n GO. Segundo proveedor: solo datos en esta carpeta, sin tocar el motor.

Interfaz claramente distinta de la del primer proveedor:
- Cada importe aparece dos veces: en monedas (marcos "MONEDAS: …", "APUESTA: 5" encima de los botones)
  y en dinero (barra fina inferior "Saldo: …  Apuesta: …  Ganancias: …"). Las pistas de zona apuntan a
  la barra de dinero para que nunca se lea la apuesta en monedas como si fuera dinero.
- El botón de girar es un rectángulo con el texto GIRAR, y la presentación se cierra con CONTINUAR.
Capturas de referencia: fixtures/playngo/ (demo pública de Book of Dead, 15-oct).
"""
from __future__ import annotations

from pathlib import Path

from betsson.core import Rect
from betsson.profiles.base import IntroStep, ProfileSpec, SpinTiming

ASSETS = Path(__file__).parent / "assets"
_MONEY_BAR_Y, _MONEY_BAR_H = 0.94, 0.06  # barra fina inferior con los importes en dinero

PROFILE = ProfileSpec(
    name="playngo",
    url_patterns=[r"playngonetwork\.com", r"playngo"],
    intro_screens=[
        IntroStep(
            name="presentacion",
            match_texts=("NO VOLVER A MOSTRAR", "DON'T SHOW AGAIN", "DO NOT SHOW"),
            click_text="CONTINUAR",
            click=Rect(x=0.43, y=0.78, w=0.14, h=0.06),
        ),
    ],
    labels={
        "balance": {"es": ["SALDO"], "en": ["BALANCE"]},
        "bet": {"es": ["APUESTA"], "en": ["BET"]},
        "win": {"es": ["GANANCIAS", "GANANCIA"], "en": ["WIN", "WINS"]},
    },
    hint_zones={
        "balance": Rect(x=0.25, y=_MONEY_BAR_Y, w=0.22, h=_MONEY_BAR_H),
        "bet": Rect(x=0.45, y=_MONEY_BAR_Y, w=0.15, h=_MONEY_BAR_H),
        "win": Rect(x=0.58, y=_MONEY_BAR_Y, w=0.22, h=_MONEY_BAR_H),
    },
    spin_templates=[ASSETS / "spin.png"],
    spin_hint=Rect(x=0.66, y=0.86, w=0.10, h=0.10),  # botón GIRAR, abajo a la derecha de los rodillos
    spin_key="Space",
    message_dismiss_texts=["ACEPTAR", "ACCEPT", "OK"],
    insufficient_texts={
        "es": ["SALDO INSUFICIENTE", "FONDOS INSUFICIENTES", "NO TIENE SUFICIENTE"],
        "en": ["INSUFFICIENT FUNDS", "NOT ENOUGH FUNDS", "INSUFFICIENT BALANCE"],
    },
    spin_end=SpinTiming(diff_threshold=0.05, stable_frames=3, start_timeout_s=8, timeout_s=40),
    demo_url=(
        "https://released.playngonetwork.com/casino/ContainerLauncher?pid=2&gid=bookofdead"
        "&lang=es_ES&practice=1&channel=desktop&demo=2"
    ),
)
