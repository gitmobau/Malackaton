"""Lecturas reales con OCR sobre las capturas de la demo pública (fixtures/pragmatic/, es-ES, EUR)."""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from betsson.game.contracts import Money
from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.profiles.base import ProviderProfile
from betsson.profiles.registry import get_profile
from betsson.vision.template import find_template

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic"
GAME_FRAMES = ["02_reposo.png", "04_fin_1.png", "06_fin_2.png", "08_fin_3.png"]
# Capturas con valores esperados distintos de 100.000 € (crédito, apuesta, ganancia o None si no se ve).
EXPECTED = {
    "10_girando.png": ("99998.00", "2.00", None),
    "11_fin_tras_girar.png": ("99996.00", "2.00", None),
    "12_fin_ocr_dificil.png": ("99996.00", "2.00", None),  # el OCR del frame entero lee '300969.96'
    "13_fin_ganancia.png": ("99990.00", "2.00", "2.00"),
}

pytestmark = pytest.mark.unit


def parse_eur_es(text: str) -> Money | None:
    """Sustituto mínimo de parse_money (área A) para es-ES: '100.000,00 €' -> 100000.00 EUR."""
    match = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", text)
    if not match or "€" not in text:
        return None
    return Money(amount=Decimal(match.group().replace(".", "").replace(",", ".")), currency="EUR")


@pytest.fixture(scope="module")
def profile() -> ProviderProfile:
    return get_profile("pragmatic")


@pytest.mark.parametrize("name", GAME_FRAMES)
def test_lee_credito_y_apuesta(profile: ProviderProfile, name: str) -> None:
    frame = read_image(FIXTURES / name)
    eyes = GameEyes(FileFrameSource([frame]), profile, "es", parse_eur_es)
    balance, bet = eyes.read_balance(frame), eyes.read_bet(frame)
    assert balance.money == Money(amount=Decimal("100000.00"), currency="EUR"), balance
    assert bet.money == Money(amount=Decimal("2.00"), currency="EUR"), bet


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_lee_credito_apuesta_y_ganancia(profile: ProviderProfile, name: str) -> None:
    frame = read_image(FIXTURES / name)
    eyes = GameEyes(FileFrameSource([frame]), profile, "es", parse_eur_es)
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    got = tuple(str(r.money.amount) if r.money else None for r in readings)
    assert got == EXPECTED[name], readings
    if EXPECTED[name][2] is None:
        assert readings[2].reason and readings[2].reason.startswith("inconclusive")


@pytest.mark.parametrize("name", GAME_FRAMES)
def test_encuentra_el_boton_de_girar(profile: ProviderProfile, name: str) -> None:
    match = find_template(read_image(FIXTURES / name), profile.spin_templates)
    assert match is not None and profile.spin_hint is not None
    hint = profile.spin_hint
    assert hint.x <= match.center[0] <= hint.x + hint.w and hint.y <= match.center[1] <= hint.y + hint.h


def test_sin_etiquetas_es_inconcluso(profile: ProviderProfile) -> None:
    frame = read_image(FIXTURES / "00_carga.png")
    reading = GameEyes(FileFrameSource([frame]), profile, "es", parse_eur_es).read_balance(frame)
    assert reading.money is None and reading.reason and reading.reason.startswith("inconclusive")
