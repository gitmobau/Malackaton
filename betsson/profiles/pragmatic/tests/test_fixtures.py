"""Lecturas reales con OCR sobre las capturas de la demo pública (fixtures/pragmatic/, es-ES, EUR)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

from betsson.core import Money, ProviderUIChanged
from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.profiles.base import ProfileSpec
from betsson.profiles.registry import ensure_recognized, get_profile
from betsson.vision.geometry import contains
from betsson.vision.template import find_template

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic"
GAME_FRAMES = ["02_reposo.png", "04_fin_1.png", "06_fin_2.png", "08_fin_3.png"]
# Capturas tras una tirada: (crédito, apuesta, ganancia). La ganancia 0 sale de win_hidden_when_zero.
EXPECTED = {
    "11_fin_tras_girar.png": ("99996.00", "2.00", "0"),
    "12_fin_ocr_dificil.png": ("99996.00", "2.00", "0"),  # el OCR del frame entero lee '300969.96'
    "13_fin_ganancia.png": ("99990.00", "2.00", "2.00"),
}

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class FakeMarket:
    """Lo mínimo de betsson.core.MarketContext para el mercado es."""

    id: str = "es"
    currency_code: str = "EUR"
    language: str = "es"
    money_tolerance: Decimal = Decimal("0.01")


class EurEsReader:
    """Sustituto mínimo del parse_money de A para es-ES: '100.000,00 €' -> 100000.00 EUR."""

    def parse(self, text: str) -> Money | None:
        match = re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", text)
        if not match or "€" not in text:
            return None
        return Money(amount=Decimal(match.group().replace(".", "").replace(",", ".")), currency="EUR")

    def currency_seen(self, text: str) -> bool:
        return "€" in text


@pytest.fixture(scope="module")
def profile() -> ProfileSpec:
    return get_profile("pragmatic")


def eyes_for(profile: ProfileSpec, name: str) -> tuple[GameEyes, object]:
    frame = read_image(FIXTURES / name)
    return GameEyes(FileFrameSource([frame]), profile, FakeMarket(), money_reader=EurEsReader()), frame


@pytest.mark.parametrize("name", GAME_FRAMES)
def test_lee_credito_y_apuesta(profile: ProfileSpec, name: str) -> None:
    eyes, frame = eyes_for(profile, name)
    balance, bet = eyes.read_balance(frame), eyes.read_bet(frame)
    assert balance.money == Money(amount=Decimal("100000.00"), currency="EUR"), balance
    assert bet.money == Money(amount=Decimal("2.00"), currency="EUR"), bet
    assert balance.currency_seen and bet.currency_seen


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_lee_credito_apuesta_y_ganancia(profile: ProfileSpec, name: str) -> None:
    eyes, frame = eyes_for(profile, name)
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    got = tuple(str(r.money.amount) if r.money else None for r in readings)
    assert got == EXPECTED[name], readings


@pytest.mark.parametrize("name", GAME_FRAMES)
def test_encuentra_el_boton_de_girar(profile: ProfileSpec, name: str) -> None:
    match = find_template(read_image(FIXTURES / name), profile.spin_templates)
    assert match is not None and contains(profile.spin_hint, match.center)


@pytest.mark.parametrize("control", ["bet_down", "bet_up"])
def test_encuentra_los_controles_de_apuesta(profile: ProfileSpec, control: str) -> None:
    spec = getattr(profile, control)
    match = find_template(read_image(FIXTURES / "04_fin_1.png"), spec.templates)
    assert match is not None and contains(spec.hint, match.center)


def test_sin_etiquetas_es_inconcluso(profile: ProfileSpec) -> None:
    eyes, frame = eyes_for(profile, "00_carga.png")
    reading = eyes.read_balance(frame)
    assert reading.money is None and reading.reason and reading.reason.startswith("inconclusive")
    win = eyes.read_win(frame)  # sin saldo ni apuesta visibles no se supone ganancia 0
    assert win.money is None


def test_el_registro_reconoce_el_juego(profile: ProfileSpec) -> None:
    ensure_recognized(profile, read_image(FIXTURES / "02_reposo.png"))


def test_el_registro_avisa_si_no_reconoce_la_pantalla(profile: ProfileSpec) -> None:
    with pytest.raises(ProviderUIChanged):
        ensure_recognized(profile, read_image(FIXTURES / "00_carga.png"))


def test_mensaje_sin_aviso_de_saldo(profile: ProfileSpec) -> None:
    eyes, frame = eyes_for(profile, "02_reposo.png")
    message = eyes.read_message(frame)
    assert message.matches_insufficient is False and message.text


def test_fin_de_tirada_sin_tirada_es_inconcluso(profile: ProfileSpec) -> None:
    eyes, _ = eyes_for(profile, "02_reposo.png")
    end = eyes.wait_spin_end()
    assert not end.completed and end.reason and end.reason.startswith("inconclusive")


def test_apuesta_minima_cuando_ya_esta_en_el_minimo(profile: ProfileSpec) -> None:
    """La pantalla no cambia al pulsar -: con el control localizado por plantilla, la apuesta ya es la mínima."""
    eyes, _ = eyes_for(profile, "04_fin_1.png")
    bet = eyes.set_bet("min")
    assert bet.money == Money(amount=Decimal("2.00"), currency="EUR")
    assert len(eyes._source.clicks) == 1 and contains(profile.bet_down.hint, eyes._source.clicks[0])
