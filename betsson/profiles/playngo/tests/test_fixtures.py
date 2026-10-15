"""Segundo proveedor sobre capturas reales de su demo pública (fixtures/playngo/, Book of Dead).

Mismo motor que el primer proveedor: aquí solo cambian los datos del perfil.
La demo no muestra moneda y usa punto decimal ('24999.90'); en Real Play el formato lo da el mercado.
"""
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
from betsson.profiles.registry import ensure_recognized, get_profile, resolve
from betsson.vision.geometry import contains
from betsson.vision.template import find_template

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "playngo"
# (captura, saldo, apuesta) en dinero: nunca los valores en monedas de los marcos superiores.
EXPECTED = [
    ("02_reposo.png", "25000.00", "1.00"),
    ("03_girando.png", "24999.90", "0.10"),
    ("04_fin.png", "24999.90", "0.10"),
]

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class DemoMarket:
    id: str = "demo"
    currency_code: str = "EUR"
    language: str = "es"
    money_tolerance: Decimal = Decimal("0.01")


class DemoReader:
    """Formato de la demo (sin moneda, punto decimal). Sustituye al parse_money del mercado solo en el test."""

    def parse(self, text: str) -> Money | None:
        match = re.fullmatch(r"\s*(\d+\.\d{2})\s*", text)
        return Money(amount=Decimal(match.group(1)), currency="EUR") if match else None

    def currency_seen(self, text: str) -> bool:
        return False


@pytest.fixture(scope="module")
def profile() -> ProfileSpec:
    return get_profile("playngo")


def test_el_registro_elige_este_perfil_por_la_url(profile: ProfileSpec) -> None:
    assert resolve(profile.demo_url).name == "playngo"


@pytest.mark.parametrize(("name", "balance", "bet"), EXPECTED)
def test_lee_saldo_y_apuesta_en_dinero(profile: ProfileSpec, name: str, balance: str, bet: str) -> None:
    frame = read_image(FIXTURES / name)
    eyes = GameEyes(FileFrameSource([frame]), profile, DemoMarket(), money_reader=DemoReader())
    got = (eyes.read_balance(frame), eyes.read_bet(frame))
    assert tuple(str(r.money.amount) if r.money else None for r in got) == (balance, bet), got


def test_sin_pista_la_apuesta_es_ambigua_y_no_concluyente(profile: ProfileSpec) -> None:
    """Con la pista de la apuesta en un sitio equivocado hay dos APUESTA (monedas y dinero): no se adivina."""
    misplaced = profile.model_copy(update={"hint_zones": {"bet": profile.hint_zones["win"]}})
    frame = read_image(FIXTURES / "04_fin.png")
    reading = GameEyes(FileFrameSource([frame]), misplaced, DemoMarket(), money_reader=DemoReader()).read_bet(frame)
    assert reading.money is None


@pytest.mark.parametrize("name", ["02_reposo.png", "04_fin.png"])
def test_encuentra_el_boton_girar(profile: ProfileSpec, name: str) -> None:
    match = find_template(read_image(FIXTURES / name), profile.spin_templates)
    assert match is not None and contains(profile.spin_hint, match.center)


def test_reconoce_el_juego_y_no_la_presentacion(profile: ProfileSpec) -> None:
    ensure_recognized(profile, read_image(FIXTURES / "04_fin.png"))
    with pytest.raises(ProviderUIChanged):
        ensure_recognized(profile, read_image(FIXTURES / "01_presentacion.png"))


def test_cierra_la_presentacion_pulsando_continuar(profile: ProfileSpec) -> None:
    intro, game = read_image(FIXTURES / "01_presentacion.png"), read_image(FIXTURES / "04_fin.png")
    source = FileFrameSource([intro, intro, game])
    eyes = GameEyes(source, profile, DemoMarket(), money_reader=DemoReader())
    assert eyes.dismiss_intro() == ["presentacion"]
    ((fx, fy),) = source.clicks
    assert 0.40 < fx < 0.60 and 0.75 < fy < 0.87  # el botón CONTINUAR, localizado por su texto
