"""Capturas de Real Play en betsson.es (es-ES, EUR), con el parse_money real del mercado.

- s1/: una tirada real con la apuesta mínima (15-oct). 100,00 - 0,10 + 0 = 99,90 leído en pantalla.
  Se tapó la franja inferior izquierda (hora e identificador de la jugada).
- s2/: cuenta sin saldo (capturas del área A): el juego rechaza la tirada con "Fondos insuficientes…".
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.market import load_market
from betsson.profiles.base import ProfileSpec
from betsson.profiles.registry import ensure_recognized, get_profile, resolve

REAL = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic" / "real-es"
# (captura, crédito, apuesta, ganancia) leídos con parse_money del mercado es
S1 = [
    ("01_reposo_apuesta_2.png", "100.00", "2.00", "0"),
    ("02_apuesta_min.png", "100.00", "0.10", "0"),
    ("04_fin_sin_premio.png", "99.90", "0.10", "0"),
]

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def profile() -> ProfileSpec:
    return get_profile("pragmatic")


def eyes_for(profile: ProfileSpec, path: Path):  # noqa: ANN201 - (GameEyes, frame)
    frame = read_image(path)
    return GameEyes(FileFrameSource([frame]), profile, load_market("es")), frame


@pytest.mark.parametrize(("name", "balance", "bet", "win"), S1)
def test_s1_lecturas_reales_en_eur(profile: ProfileSpec, name: str, balance: str, bet: str, win: str) -> None:
    eyes, frame = eyes_for(profile, REAL / "s1" / name)
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    assert tuple(str(r.money.amount) if r.money else None for r in readings) == (balance, bet, win), readings
    assert all(r.money.currency == "EUR" for r in readings)
    assert readings[0].currency_seen and readings[1].currency_seen  # la moneda se VE en pantalla


def test_s1_regla_del_saldo_en_pantalla(profile: ProfileSpec) -> None:
    before_eyes, before = eyes_for(profile, REAL / "s1" / "02_apuesta_min.png")
    after_eyes, after = eyes_for(profile, REAL / "s1" / "04_fin_sin_premio.png")
    start, bet = before_eyes.read_balance(before).money, before_eyes.read_bet(before).money
    end, win = after_eyes.read_balance(after).money, after_eyes.read_win(after).money
    assert start - bet + win == end
    assert end.amount == Decimal("99.90")


def test_se_reconoce_por_la_imagen_aunque_la_url_sea_otra(profile: ProfileSpec) -> None:
    """En betsson.es el iframe del juego no lleva la URL de la demo: el proveedor se reconoce por su botón."""
    frame = read_image(REAL / "s1" / "01_reposo_apuesta_2.png")
    assert resolve("srcdoc", frame).name == "pragmatic"
    ensure_recognized(profile, frame)


def test_s2_mensaje_real_de_fondos_insuficientes(profile: ProfileSpec) -> None:
    s2 = REAL / "s2"
    if not (s2 / "02_mensaje_fondos_insuficientes.png").exists():
        pytest.skip("capturas del S2 real (área A) aún no fusionadas")
    before_eyes, before = eyes_for(profile, s2 / "01_principal_credito_0.png")
    eyes, frame = eyes_for(profile, s2 / "02_mensaje_fondos_insuficientes.png")
    assert before_eyes.read_message(before).matches_insufficient is False
    message = eyes.read_message(frame)
    assert message.matches_insufficient is True and message.lang_detected == "es"
    assert eyes.read_balance(frame).money.amount == Decimal("0.00")  # el saldo no cambia
