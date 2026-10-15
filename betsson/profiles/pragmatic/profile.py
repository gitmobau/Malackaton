"""Perfil de Pragmatic Play. Todo lo específico del proveedor vive aquí (y en fixtures/pragmatic/)."""
from __future__ import annotations

from pathlib import Path

from betsson.profiles.base import IntroScreen, ProviderProfile, Rect, SpinEndSignal

ASSETS = Path(__file__).parent / "assets"

PROFILE = ProviderProfile(
    name="pragmatic",
    url_patterns=[r"pragmaticplay\.net", r"/gs2c/", r"ppgames\.net"],
    intro_screens=[
        # Logo del estudio mientras carga: no se pulsa nada, se espera.
        IntroScreen(name="carga", match_texts=["POWERED BY"], wait_only=True),
        # Pantalla de presentación del juego: botón redondo sin texto (flechas) a la derecha.
        IntroScreen(
            name="presentacion",
            match_texts=["NO VOLVER A MOSTRAR", "DON'T SHOW NEXT TIME", "DO NOT SHOW"],
            click_text="CONTINU",
            click_template=ASSETS / "intro_continue.png",
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
        "bet": Rect(x=0.30, y=0.85, w=0.40, h=0.15),
        "win": Rect(x=0.30, y=0.70, w=0.40, h=0.20),
    },
    spin_templates=[ASSETS / "spin.png"],
    spin_hint=Rect(x=0.72, y=0.83, w=0.10, h=0.15),  # botón redondo de flechas, abajo a la derecha
    spin_key="Space",
    insufficient_texts={
        "es": ["SALDO INSUFICIENTE", "FONDOS INSUFICIENTES", "NO TIENES SUFICIENTE"],
        "en": ["INSUFFICIENT BALANCE", "INSUFFICIENT FUNDS", "NOT ENOUGH"],
    },
    # Calibrado en la demo (15-oct): en reposo las burbujas dan 0.03-0.07; girando, 0.17-0.45.
    spin_end=SpinEndSignal(diff_threshold=0.12, stable_frames=2, start_timeout_s=8, timeout_s=40),
    network_pattern=r"/gs2c/(ge/v\d+/)?gameService",
    demo_url=(
        "https://demogamesfree.pragmaticplay.net/gs2c/openGame.do?gameSymbol=vs10txbigbass"
        "&websiteUrl=https%3A%2F%2Fwww.pragmaticplay.com&jurisdiction=99&lang=es&cur=EUR"
    ),
)
