"""Único punto de contacto de B con la lectura de importes del área A (parse_money, detect_currency).

GameEyes solo conoce el Protocol MoneyReader. Si el módulo de A todavía no está en la rama,
el lector devuelve None (lectura no concluyente) en vez de inventar un formato numérico.
"""
from __future__ import annotations

import logging
from typing import Any, Protocol

from betsson.core import MarketContext, Money


class MoneyReader(Protocol):
    def parse(self, text: str) -> Money | None:
        """Importe del texto visible en el formato del mercado, o None si no se puede leer."""
        ...

    def currency_seen(self, text: str) -> bool:
        """True si el símbolo o código de la moneda del mercado aparece en el texto."""
        ...


class MarketMoneyReader:
    """Adaptador sobre betsson.market (área A). El mercado es el objeto Market de A."""

    def __init__(self, market: Any) -> None:
        from betsson.market import MoneyParseError, detect_currency, parse_money

        self._market = market
        self._parse_money = parse_money
        self._detect_currency = detect_currency
        self._parse_error = MoneyParseError

    def parse(self, text: str) -> Money | None:
        try:
            parsed = self._parse_money(text, self._market)
        except (self._parse_error, ValueError, ArithmeticError):  # decimal.InvalidOperation es ArithmeticError
            return None
        return Money(amount=parsed.amount, currency=parsed.currency)

    def currency_seen(self, text: str) -> bool:
        return self._detect_currency(text, self._market) is not None


class UnavailableMoneyReader:
    """Sin parse_money de A: ninguna lectura es concluyente."""

    def parse(self, text: str) -> Money | None:
        return None

    def currency_seen(self, text: str) -> bool:
        return False


def money_reader_for(market: MarketContext) -> MoneyReader:
    try:
        return MarketMoneyReader(market)
    except ImportError as exc:
        # Sin el módulo de A todas las lecturas salen "importe ilegible": se deja dicho por qué.
        logging.getLogger(__name__).warning("parse_money (área A) no disponible: %s", exc)
        return UnavailableMoneyReader()
