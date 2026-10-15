"""Tests de parse_money y de la configuración de mercados (EUR y PEN)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from betsson.market import Market, MoneyParseError, list_markets, load_market, parse_money


@pytest.fixture(scope="module")
def es() -> Market:
    return load_market("es")


@pytest.fixture(scope="module")
def com() -> Market:
    return load_market("com")


@pytest.fixture(scope="module")
def pe() -> Market:
    return load_market("pe")


# --- Configuración -----------------------------------------------------------

def test_all_market_files_validate() -> None:
    ids = list_markets()
    assert {"es", "com", "pe"} <= set(ids)
    for market_id in ids:
        assert load_market(market_id).id == market_id


def test_incomplete_market_is_rejected(es: Market) -> None:
    data = json.loads(es.model_dump_json())
    del data["currency"]
    with pytest.raises(ValidationError):
        Market.model_validate(data)


def test_language_must_match_locale(es: Market) -> None:
    data = json.loads(es.model_dump_json())
    data["language"] = "en"
    with pytest.raises(ValidationError):
        Market.model_validate(data)


def test_credentials_are_env_names_not_values(es: Market) -> None:
    data = json.loads(es.model_dump_json())
    data["credentials_env"]["password"] = "mi contraseña"
    with pytest.raises(ValidationError):
        Market.model_validate(data)


# --- EUR (es: 1.234,56 €) -----------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56 €", "1234.56"),
        ("1.234,56€", "1234.56"),
        ("12,34 €", "12.34"),
        ("0,10 €", "0.10"),
        ("SALDO 99,90 €", "99.90"),
        ("1 234,56 €", "1234.56"),
        ("1 234,56 €", "1234.56"),
        ("1.234.567,89 EUR", "1234567.89"),
        ("100 €", "100"),
        ("1.000 €", "1000"),
        ("-0,20 €", "-0.20"),
        # Formato "inglés" visto dentro del juego en un mercado de coma decimal.
        ("€1,234.56", "1234.56"),
        ("€12.34", "12.34"),
    ],
)
def test_parse_eur_es(es: Market, text: str, expected: str) -> None:
    money = parse_money(text, es)
    assert money.amount == Decimal(expected)
    assert money.currency == "EUR"


@pytest.mark.parametrize(
    ("text", "expected"),
    [("€1,234.56", "1234.56"), ("€ 0.10", "0.10"), ("BALANCE €1,000", "1000"), ("€1,000.00", "1000.00")],
)
def test_parse_eur_com(com: Market, text: str, expected: str) -> None:
    money = parse_money(text, com)
    assert money.amount == Decimal(expected)
    assert money.currency == "EUR"


# --- PEN (pe: S/ 1,234.50) ----------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("S/ 1,234.50", "1234.50"),
        ("S/. 1234.5", "1234.5"),
        ("S/1,234.50", "1234.50"),
        ("S/ 0.20", "0.20"),
        ("SALDO: S/ 50.00", "50.00"),
        ("1,000 soles", "1000"),
        ("PEN 1,234,567.00", "1234567.00"),
    ],
)
def test_parse_pen(pe: Market, text: str, expected: str) -> None:
    money = parse_money(text, pe)
    assert money.amount == Decimal(expected)
    assert money.currency == "PEN"


# --- Moneda y errores ---------------------------------------------------------

def test_currency_none_when_no_market_symbol(pe: Market) -> None:
    """Un '€' en el mercado peruano no se da por PEN: la comprobación de moneda fallará."""
    money = parse_money("€ 12.50", pe)
    assert money.amount == Decimal("12.50")
    assert money.currency is None


def test_currency_none_without_symbol(es: Market) -> None:
    assert parse_money("12,50", es).currency is None


@pytest.mark.parametrize("text", ["", "   ", "SALDO", "€"])
def test_no_number_raises(es: Market, text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_money(text, es)


def test_bad_grouping_raises(es: Market) -> None:
    with pytest.raises(MoneyParseError):
        parse_money("1.23.4 €", es)
