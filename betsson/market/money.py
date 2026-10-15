"""Lectura genérica de importes: parse_money(texto, mercado) -> Money.

Pensado para texto de OCR o del DOM. Regla de oro: ante la duda, MoneyParseError
(la comprobación queda "inconclusive"), nunca un importe dudoso devuelto en silencio.

Formato aceptado:
- El del mercado (`number_format`): separador de miles, decimal y nº de decimales.
- El formato contrario solo cuando no es ambiguo (p. ej. "€1,234.56" o "€12.34" en es:
  dentro de algunos juegos se ve así).
- Miles con espacio (normal o fino) solo delante de la parte decimal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from betsson.market.loader import MARKETS_DIR, list_markets, load_market
from betsson.market.schema import Market, NumberFormat

_HSPACE = "    "  # espacios horizontales; nunca saltos de línea
# Dos formas de número: miles con espacio (+ decimal opcional) o dígitos con . y ,
_NUMBER = re.compile(rf"[-−]?(?:\d{{1,3}}(?:[{_HSPACE}]\d{{3}}(?!\d))+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)")
_SPACE_GROUPED = re.compile(rf"([\d{_HSPACE}]+)(?:([.,])(\d+))?")
_MINUS = "-−"


class MoneyParseError(ValueError):
    """El texto no contiene un importe legible sin ambigüedad."""


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str  # ISO 4217

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"


# --------------------------------------------------------------------------- moneda

@lru_cache(maxsize=None)
def _known_symbols(markets_dir: Path = MARKETS_DIR) -> tuple[tuple[str, str], ...]:
    """(alias, código ISO) de todas las monedas configuradas, del alias más largo al más corto."""
    pairs = {
        (symbol, load_market(mid, markets_dir).currency.code)
        for mid in list_markets(markets_dir)
        for symbol in load_market(mid, markets_dir).currency.symbols
    }
    return tuple(sorted(pairs, key=lambda p: len(p[0]), reverse=True))


@lru_cache(maxsize=None)
def _symbol_pattern(symbol: str) -> re.Pattern[str]:
    # Un alias con letras no puede ir pegado a otras letras: "pen" no casa en "open" ni "eur" en "Europa".
    left = r"(?<![^\W\d_])" if symbol[0].isalpha() else ""
    right = r"(?![^\W\d_])" if symbol[-1].isalpha() else ""
    return re.compile(left + re.escape(symbol) + right, re.IGNORECASE)


def detect_currency(text: str, market: Market) -> str | None:
    """Código ISO de la moneda que se VE en el texto, o None si no aparece ninguna conocida.

    Primero los alias del mercado; después los de cualquier otro mercado configurado
    (así un "€" leído en Perú es EUR y la comprobación de moneda falla con motivo).
    """
    own = sorted(((s, market.currency.code) for s in market.currency.symbols), key=lambda p: len(p[0]), reverse=True)
    for symbol, code in (*own, *_known_symbols()):
        if _symbol_pattern(symbol).search(text):
            return code
    return None


def _ends_with_symbol(prefix: str, market: Market) -> bool:
    prefix = prefix.rstrip(_HSPACE).lower()
    symbols = [s for s, _ in _known_symbols()] + list(market.currency.symbols)
    return any(prefix.endswith(s.lower()) for s in symbols)


# --------------------------------------------------------------------------- número

def _check_thousands(groups: list[str], token: str) -> None:
    head, rest = groups[0], groups[1:]
    if not 1 <= len(head) <= 3 or (rest and head.startswith("0")) or any(len(g) != 3 for g in rest):
        raise MoneyParseError(f"agrupación de miles no válida en '{token}'")


def _split(body: str, fmt: NumberFormat, token: str) -> tuple[str, str]:
    """(entero, fracción) en dígitos, validando el formato. Lanza si es ambiguo."""
    if any(c in _HSPACE for c in body):
        match = _SPACE_GROUPED.fullmatch(body)
        if not match:
            raise MoneyParseError(f"importe no válido en '{token}'")
        grouped, sep, fraction = match.group(1), match.group(2), match.group(3) or ""
        if sep and sep != fmt.decimal_sep:
            raise MoneyParseError(f"miles con espacio y decimal '{sep}' que no es el del mercado en '{token}'")
        _check_thousands(re.split(rf"[{_HSPACE}]", grouped), token)
        return re.sub(rf"[{_HSPACE}]", "", grouped), fraction

    seps = [c for c in body if c in ".,"]
    if not seps:
        return body, ""

    if len(set(seps)) == 2:  # los dos separadores: el último es el decimal y aparece una sola vez
        dec = seps[-1]
        if seps.count(dec) != 1:
            raise MoneyParseError(f"separadores incoherentes en '{token}'")
        integer, _, fraction = body.rpartition(dec)
        thousands = "," if dec == "." else "."
        _check_thousands(integer.split(thousands), token)
        return integer.replace(thousands, ""), fraction

    sep = seps[0]
    groups = body.split(sep)
    if len(groups) > 2:  # 1.234.567: solo pueden ser miles
        _check_thousands(groups, token)
        return "".join(groups), ""

    head, tail = groups
    if sep == fmt.decimal_sep:
        if len(tail) <= fmt.decimals:
            return head, tail
        raise MoneyParseError(f"'{token}' es ambiguo: ¿{len(tail)} decimales o miles en otro formato?")
    if len(tail) == 3:  # separador de miles del mercado
        _check_thousands(groups, token)
        return head + tail, ""
    if len(tail) <= fmt.decimals:  # decimal en el formato contrario: "€12.34" en es
        return head, tail
    raise MoneyParseError(f"'{token}' no encaja con el formato del mercado")


def _to_decimal(token: str, market: Market) -> Decimal:
    negative = token[0] in _MINUS
    integer, fraction = _split(token.lstrip(_MINUS), market.number_format, token)
    if len(fraction) > market.number_format.decimals:
        raise MoneyParseError(f"'{token}' tiene más decimales de los que usa el mercado")
    try:
        value = Decimal(f"{integer or '0'}.{fraction or '0'}")
    except InvalidOperation as exc:
        raise MoneyParseError(f"importe no válido en '{token}'") from exc
    return -value if negative else value


def parse_money(text: str, market: Market, *, require_currency: bool = False) -> Money:
    """Extrae el primer importe de `text` según el formato de `market`.

    Ejemplos (es): '1.234,56 €' -> 1234.56 EUR. (pe): 'S/ 1,234.50' -> 1234.50 PEN.
    Moneda: la que se ve en el texto, aunque sea de otro mercado. Si no se ve ninguna:
    MoneyParseError con require_currency=True; si no, la del mercado (para saber si se
    vio, usa detect_currency). Lanza MoneyParseError si no hay importe o si es ambiguo.
    """
    if not text or not text.strip():
        raise MoneyParseError("texto vacío")
    match = _NUMBER.search(text)
    if not match:
        raise MoneyParseError(f"no hay ningún importe en '{text}'")
    before = text[: match.start()]
    if before.endswith((".", ",")) and not _ends_with_symbol(before, market):
        raise MoneyParseError(f"separador sin parte entera en '{text}'")  # ",50 €": ¿se perdió el 0?
    currency = detect_currency(text, market)
    if currency is None:
        if require_currency:
            raise MoneyParseError(f"no se ve la moneda en '{text}'")
        currency = market.currency.code
    return Money(amount=_to_decimal(match.group(0), market), currency=currency)
