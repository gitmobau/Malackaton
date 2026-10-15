"""Ids de escenarios y comprobaciones (docs/PREPARACION.md §3).

Son la clave de cada resultado en results.json. Para añadir uno nuevo, PR al área C.
"""
from __future__ import annotations

from enum import Enum


class Scenario(str, Enum):
    S1 = "S1"  # tirada completada en Real Play
    S2 = "S2"  # saldo insuficiente


class CheckId(str, Enum):
    # S1 y S2
    LOGIN_OK = "login_ok"
    REAL_PLAY = "real_play"
    CURRENCY_MATCHES_MARKET = "currency_matches_market"
    # S1
    BETSSON_BALANCE_BEFORE = "betsson_balance_before"
    WAGER_READ = "wager_read"
    SPIN_STARTED = "spin_started"
    SPIN_COMPLETED = "spin_completed"
    PAYOUT_READ = "payout_read"
    INGAME_BALANCE_CONSISTENT = "ingame_balance_consistent"
    BETSSON_BALANCE_RECONCILES = "betsson_balance_reconciles"
    WAGER_IS_USED_WAGER = "wager_is_used_wager"
    # S2
    SPIN_REJECTED = "spin_rejected"
    INSUFFICIENT_MESSAGE_LANGUAGE = "insufficient_message_language"
    BETSSON_BALANCE_UNCHANGED = "betsson_balance_unchanged"
    INGAME_BALANCE_UNCHANGED = "ingame_balance_unchanged"


_COMMON = (CheckId.LOGIN_OK, CheckId.REAL_PLAY, CheckId.CURRENCY_MATCHES_MARKET)

SCENARIO_CHECKS: dict[Scenario, tuple[CheckId, ...]] = {
    Scenario.S1: _COMMON
    + (
        CheckId.BETSSON_BALANCE_BEFORE,
        CheckId.WAGER_READ,
        CheckId.SPIN_STARTED,
        CheckId.SPIN_COMPLETED,
        CheckId.PAYOUT_READ,
        CheckId.INGAME_BALANCE_CONSISTENT,
        CheckId.BETSSON_BALANCE_RECONCILES,
        CheckId.WAGER_IS_USED_WAGER,
    ),
    Scenario.S2: _COMMON
    + (
        CheckId.SPIN_REJECTED,
        CheckId.INSUFFICIENT_MESSAGE_LANGUAGE,
        CheckId.BETSSON_BALANCE_UNCHANGED,
        CheckId.INGAME_BALANCE_UNCHANGED,
    ),
}
