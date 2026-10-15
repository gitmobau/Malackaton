"""Lectura genérica de importes: parse_money(texto, mercado) -> Money.

Pensado para texto de OCR o del DOM: tolera espacios raros, símbolo delante o
detrás y separadores de miles del propio mercado o de otro formato habitual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from betsson.market.schema import Market

_SPACES = re.compile(r"[\s   ]+")
# Un importe: signo opcional, dígitos con separadores . , o espacio entre grupos.
_NUMBER = re.compile(r"[-−]?\d(?:[\d.,]|\s(?=\d{3}\b))*")


class MoneyParseError(ValueError):
    """El texto no contiene un importe legible."""


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str | None  # código ISO si se vio un símbolo del mercado; None si no se vio ninguno
    raw: str

    def __str__(self) -> str:
        return f"{self.amount} {self.currency or '?'}"


def _find_currency(text: str, market: Market) -> str | None:
    lowered = text.lower()
    # Los alias más largos primero: "S/." antes que "S/".
    for symbol in sorted(market.currency.symbols, key=len, reverse=True):
        if symbol.lower() in lowered:
            return market.currency.code
    return None


def _normalize_number(token: str, market: Market) -> Decimal:
    negative = token[0] in "-−"
    digits = _SPACES.sub("", token.lstrip("-−"))
    fmt = market.number_format
    seps = [c for c in digits if c in ".,"]

    if not seps:
        integer, fraction = digits, ""
    elif len(set(seps)) == 2:
        # Los dos separadores: el último es el decimal, sea cual sea el mercado.
        dec = seps[-1]
        integer, _, fraction = digits.rpartition(dec)
        integer = integer.replace("," if dec == "." else ".", "")
        if dec in integer:
            raise MoneyParseError(f"separadores incoherentes en '{token}'")
    else:
        sep = seps[0]
        head, _, tail = digits.rpartition(sep)
        groups = digits.split(sep)
        looks_like_thousands = len(seps) > 1 or (len(tail) == 3 and sep != fmt.decimal_sep)
        if looks_like_thousands:
            if any(len(g) != 3 for g in groups[1:]):
                raise MoneyParseError(f"agrupación de miles no válida en '{token}'")
            integer, fraction = "".join(groups), ""
        else:
            integer, fraction = head, tail

    try:
        value = Decimal(f"{integer or '0'}.{fraction or '0'}")
    except InvalidOperation as exc:
        raise MoneyParseError(f"importe no válido en '{token}'") from exc
    return -value if negative else value


def parse_money(text: str, market: Market) -> Money:
    """Extrae el primer importe de `text` según el formato de `market`.

    Ejemplos (es): '1.234,56 €' -> 1234.56 EUR. (pe): 'S/ 1,234.50' -> 1234.50 PEN.
    Lanza MoneyParseError si no hay ningún número.
    """
    if not text or not text.strip():
        raise MoneyParseError("texto vacío")
    match = _NUMBER.search(text)
    if not match:
        raise MoneyParseError(f"no hay ningún importe en '{text}'")
    token = match.group(0).rstrip(".,")
    return Money(amount=_normalize_number(token, market), currency=_find_currency(text, market), raw=text)
