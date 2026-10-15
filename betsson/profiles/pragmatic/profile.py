"""Perfil de Pragmatic Play. Todo lo específico del proveedor vive aquí (y en fixtures/pragmatic/)."""
from __future__ import annotations

from pathlib import Path

from betsson.core import Rect
from betsson.profiles.base import Control, IntroStep, ProfileSpec, SpinTiming

ASSETS = Path(__file__).parent / "assets"

PROFILE = ProfileSpec(
    name="pragmatic",
    url_patterns=[r"pragmaticplay\.net", r"/gs2c/", r"ppgames\.net"],
    # El botón redondo del gorila (girar en juego y continuar en la presentación) es de este estudio.
    detect_templates=[ASSETS / "spin.png", ASSETS / "intro_continue.png"],
    intro_screens=[
        # Logo del estudio mientras carga: no se pulsa nada, se espera.
        IntroStep(
            name="carga",
            match_texts=("POWERED BY",),
            wait_only=True,
            click=Rect(x=0.45, y=0.45, w=0.1, h=0.1),  # no se usa: solo se espera
        ),
        # Pantalla de presentación del juego: botón redondo sin texto (flechas) a la derecha.
        IntroStep(
            name="presentacion",
            match_texts=("NO VOLVER A MOSTRAR", "DON'T SHOW NEXT TIME", "DO NOT SHOW"),
            click_text="CONTINU",
            template=ASSETS / "intro_continue.png",
            click=Rect(x=0.73, y=0.39, w=0.12, h=0.21),
        ),
    ],
    labels={
        "balance": {"es": ["CRÉDITO", "SALDO"], "en": ["CREDIT", "BALANCE"]},
        "bet": {"es": ["APUESTA"], "en": ["BET"]},
        "win": {"es": ["GANANCIA", "GANANCIAS", "PREMIO"], "en": ["WIN"]},
    },
    hint_zones={
        "balance": Rect(x=0.0, y=0.85, w=0.35, h=0.15),
        "bet": Rect(x=0.0, y=0.85, w=0.35, h=0.15),
        "win": Rect(x=0.30, y=0.80, w=0.40, h=0.20),
    },
    spin_templates=[ASSETS / "spin.png"],
    spin_hint=Rect(x=0.72, y=0.83, w=0.10, h=0.15),  # botón redondo de flechas, abajo a la derecha
    spin_key="Space",
    bet_down=Control(templates=[ASSETS / "bet_down.png"], hint=Rect(x=0.67, y=0.88, w=0.06, h=0.09)),
    bet_up=Control(templates=[ASSETS / "bet_up.png"], hint=Rect(x=0.82, y=0.88, w=0.06, h=0.09)),
    # Tras una tirada sin premio, la barra inferior no muestra GANANCIA (comprobado en la demo, 15-oct).
    win_hidden_when_zero=True,
    insufficient_texts={
        "es": ["SALDO INSUFICIENTE", "FONDOS INSUFICIENTES", "NO TIENES SUFICIENTE"],
        "en": ["INSUFFICIENT BALANCE", "INSUFFICIENT FUNDS", "NOT ENOUGH"],
    },
    # Calibrado en la demo (15-oct): en reposo las burbujas dan 0.03-0.07; girando, 0.17-0.45.
    spin_end=SpinTiming(diff_threshold=0.12, stable_frames=2, start_timeout_s=8, timeout_s=40),
    network_pattern=r"/gs2c/(ge/v\d+/)?gameService",
    demo_url=(
        "https://demogamesfree.pragmaticplay.net/gs2c/openGame.do?gameSymbol=vs10txbigbass"
        "&websiteUrl=https%3A%2F%2Fwww.pragmaticplay.com&jurisdiction=99&lang=es&cur=EUR"
    ),
)
