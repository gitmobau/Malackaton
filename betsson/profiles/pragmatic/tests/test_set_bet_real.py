"""set_bet("min") sobre capturas reales de betsson.es (2,00 -> 0,10 EUR), con el parse_money del mercado."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.market import load_market
from betsson.profiles.registry import get_profile
from betsson.vision.geometry import contains

S1 = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic" / "real-es" / "s1"

pytestmark = pytest.mark.unit


def test_set_bet_min_rapido_sobre_capturas_reales() -> None:
    """El bucle lee solo la zona de apuesta y el valor final se confirma en pantalla completa."""
    profile = get_profile("pragmatic")
    source = FileFrameSource([read_image(S1 / "01_reposo_apuesta_2.png")] * 2 + [read_image(S1 / "02_apuesta_min.png")])
    eyes = GameEyes(source, profile, load_market("es"))
    start = time.monotonic()
    bet = eyes.set_bet("min")
    elapsed = time.monotonic() - start
    assert bet.money is not None and str(bet.money.amount) == "0.10", bet
    assert len(source.clicks) == 2 and source.clicks[0] == source.clicks[1]  # plantilla buscada una sola vez
    assert all(contains(profile.bet_down.hint, c) for c in source.clicks)
    assert elapsed < 20, f"set_bet tardó {elapsed:.1f}s"
