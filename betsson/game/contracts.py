"""Copia provisional de los contratos que publicará el área C en betsson/core/.

Acordado con C (15-oct): Money vive en core/money.py; Reading, SpinEnd y Message son modelos
pydantic inmutables en core; ProviderUIChanged es la excepción de "el perfil no reconoce el juego".
Cuando core exista, este módulo se sustituye por imports de core.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict

PROVIDER_UI_CHANGED = "provider_ui_changed"


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal
    currency: str


class Reading(BaseModel):
    """Lectura visible de un importe. Si es dudosa, money=None y reason='inconclusive: …'."""

    model_config = ConfigDict(frozen=True)

    raw_text: str
    money: Money | None
    confidence: float
    evidence_path: Path | None = None
    reason: str | None = None


class SpinEnd(BaseModel):
    model_config = ConfigDict(frozen=True)

    completed: bool
    duration_s: float
    reason: str | None = None


class Message(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    lang_detected: str | None
    matches_insufficient: bool


class ProviderUIChanged(Exception):
    """El perfil no reconoce el juego: aviso de mantenimiento, no FAIL de integración."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
