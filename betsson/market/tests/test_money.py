"""Tests de parse_money y de la configuración de mercados (EUR y PEN)."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from betsson.market import Market, MoneyParseError, detect_currency, list_markets, load_market, parse_money

pytestmark = pytest.mark.unit


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

def test_foreign_symbol_is_detected_as_its_currency(pe: Market) -> None:
    """Un '€' en el mercado peruano es EUR, no PEN: currency_matches_market fallará con motivo."""
    money = parse_money("€ 12.50", pe)
    assert money.amount == Decimal("12.50")
    assert money.currency == "EUR"
    assert detect_currency("€ 12.50", pe) == "EUR"


def test_no_symbol_defaults_to_market_currency(es: Market) -> None:
    assert parse_money("12,50", es).currency == "EUR"
    assert detect_currency("12,50", es) is None


def test_no_symbol_with_require_currency_raises(es: Market) -> None:
    with pytest.raises(MoneyParseError):
        parse_money("12,50", es, require_currency=True)


def test_market_exposes_currency_code(pe: Market) -> None:
    assert pe.currency_code == "PEN"


# --- Regresiones de la revisión (importes erróneos en silencio) -----------------

@pytest.mark.parametrize("text", [",50 €", ".50 €", "Saldo: ,50"])
def test_h1_leading_separator_raises(es: Market, text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_money(text, es)


def test_h1_symbol_ending_in_dot_is_not_a_lost_zero(pe: Market) -> None:
    assert parse_money("S/.50.00", pe).amount == Decimal("50.00")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0,20 200 giros", "0.20"), ("12,50" + chr(10) + "100", "12.50"), ("Ganancia 1 000 € 5", "1000"), ("1 234,56 €", "1234.56")],
)
def test_h2_space_does_not_merge_numbers(es: Market, text: str, expected: str) -> None:
    assert parse_money(text, es).amount == Decimal(expected)


@pytest.mark.parametrize("text", ["0.100 €", "1,23.456 €", "1.2345 €", "1,234 €", "0,123 €", "12,345.678 €"])
def test_h3_ambiguous_or_malformed_es_raises(es: Market, text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_money(text, es)


@pytest.mark.parametrize("text", ["S/ 12.345", "S/ 1.2345"])
def test_h3_ambiguous_pe_raises(pe: Market, text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_money(text, pe)


def test_h3_es_thousands_dot_still_reads(es: Market) -> None:
    assert parse_money("1.234 €", es).amount == Decimal("1234")


@pytest.mark.parametrize(("text", "market_id"), [("Europa 2024", "es"), ("Open 5", "pe"), ("Pending 3", "pe")])
def test_h4_currency_alias_inside_word_is_not_currency(text: str, market_id: str) -> None:
    assert detect_currency(text, load_market(market_id)) is None


@pytest.mark.parametrize("text", ["", "   ", "SALDO", "€"])
def test_no_number_raises(es: Market, text: str) -> None:
    with pytest.raises(MoneyParseError):
        parse_money(text, es)


def test_bad_grouping_raises(es: Market) -> None:
    with pytest.raises(MoneyParseError):
        parse_money("1.23.4 €", es)
