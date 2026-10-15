"""Importe con moneda. Lo construye parse_money (área A) a partir del texto visible."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class CurrencyMismatch(ValueError):
    """Operación entre importes de monedas distintas."""


class Money(BaseModel):
    """Importe exacto (Decimal, nunca float) en una moneda ISO 4217 ("EUR", "PEN"…)."""

    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str

    @field_validator("currency")
    @classmethod
    def _iso_code(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not (code.isascii() and code.isalpha()):
            raise ValueError(f"moneda ISO 4217 no válida: {value!r}")
        return code

    @field_validator("amount", mode="before")
    @classmethod
    def _no_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            raise ValueError("usa Decimal o str para importes, nunca float")
        return value

    @field_validator("amount")
    @classmethod
    def _finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("el importe debe ser finito")
        return value

    def _same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"{self.currency} frente a {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    @field_serializer("amount")
    def _plain(self, value: Decimal) -> str:
        return format(value, "f")

    def __str__(self) -> str:
        return f"{format(self.amount, 'f')} {self.currency}"
