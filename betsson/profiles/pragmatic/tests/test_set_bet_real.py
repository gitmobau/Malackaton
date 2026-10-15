"""set_bet("min") sobre capturas reales de betsson.es (2,00 -> 0,10 EUR), con el parse_money del mercado."""
from __future__ import annotations

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
    bet = eyes.set_bet("min")  # sin límite de tiempo en el test: la CI comparte máquina
    assert bet.money is not None and str(bet.money.amount) == "0.10", bet
    assert len(source.clicks) == 2 and source.clicks[0] == source.clicks[1]  # plantilla buscada una sola vez
    assert all(contains(profile.bet_down.hint, c) for c in source.clicks)


def test_one_step_baja_una_vez() -> None:
    """2,00 -> (una pulsación de -) -> 0,10 en las capturas reales: un solo clic, en el control -."""
    profile = get_profile("pragmatic")
    source = FileFrameSource([read_image(S1 / "01_reposo_apuesta_2.png")] * 2 + [read_image(S1 / "02_apuesta_min.png")])
    bet = GameEyes(source, profile, load_market("es")).set_bet("one_step")
    assert bet.money is not None and str(bet.money.amount) == "0.10", bet
    assert len(source.clicks) == 1 and contains(profile.bet_down.hint, source.clicks[0])


def test_one_step_en_la_minima_sube_una_vez() -> None:
    """Ya en 0,10: - no la mueve, así que + una vez (2,00 en la captura): dos clics, - y después +."""
    profile = get_profile("pragmatic")
    at_min = read_image(S1 / "02_apuesta_min.png")
    source = FileFrameSource([at_min, at_min, at_min, at_min, at_min, read_image(S1 / "01_reposo_apuesta_2.png")])
    bet = GameEyes(source, profile, load_market("es")).set_bet("one_step")
    assert bet.money is not None and str(bet.money.amount) == "2.00", bet
    assert len(source.clicks) == 2
    assert contains(profile.bet_down.hint, source.clicks[0]) and contains(profile.bet_up.hint, source.clicks[1])


def test_objetivo_desconocido_no_pulsa_nada() -> None:
    profile = get_profile("pragmatic")
    source = FileFrameSource([read_image(S1 / "01_reposo_apuesta_2.png")])
    bet = GameEyes(source, profile, load_market("es")).set_bet("lo_que_sea")
    assert bet.money is None and not source.clicks
    assert "one_step" in GameEyes.bet_targets
