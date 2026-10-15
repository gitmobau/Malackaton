"""S2, saldo insuficiente: de lo observado a las comprobaciones de PREPARACION §3."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from pathlib import Path

from betsson.checks.balance import unchanged
from betsson.checks.common import apply_ui_changed, currency_check, login_check, real_play_check
from betsson.core import CheckId, CheckResult, MarketContext, Message, PlayMode, Reading


@dataclass(frozen=True)
class S2Observation:
    """Lo que se vio durante S2. None = no se llegó a observar."""

    logged_in: bool | None = None
    login_assisted: bool = False
    login_assisted_at: datetime | None = None
    play_mode: PlayMode | None = None
    play_mode_reason: str | None = None
    open_evidence: tuple[Path, ...] = ()  # pasos del jugador al abrir el juego
    open_error: str | None = None
    betsson_before: Reading | None = None
    game_before: Reading | None = None
    bet: Reading | None = None
    spin_started: bool | None = None  # hubo cambio visual tras pulsar (puede ser solo la ventana del aviso)
    spin_completed: bool | None = None  # se vio una tirada completa (solo si no hubo aviso)
    message: Message | None = None
    game_after: Reading | None = None
    betsson_after: Reading | None = None
    ui_changed: str | None = None


def _evidence(msg: Message | None) -> tuple[Path, ...]:
    return (msg.evidence_path,) if msg is not None and msg.evidence_path else ()


def _precondition_problem(obs: S2Observation) -> str | None:
    """S2 solo prueba algo si la apuesta visible supera el saldo visible del juego."""
    bet, bal = obs.bet, obs.game_before
    if bet is None or bet.money is None or bal is None or bal.money is None:
        return "no se pudo leer la apuesta o el saldo para confirmar que el saldo es insuficiente"
    if bet.money.currency != bal.money.currency:
        return f"monedas distintas en apuesta ({bet.money.currency}) y saldo ({bal.money.currency})"
    if bet.money.amount <= bal.money.amount:
        return f"precondición de S2 no cumplida: la apuesta {bet.money} no supera el saldo {bal.money}"
    return None


def _game_balance_change(obs: S2Observation, tolerance: Decimal) -> Decimal | None:
    """Diferencia del saldo del juego (después − antes); None si no se pudo leer o la moneda difiere."""
    b, a = obs.game_before, obs.game_after
    if b is None or a is None or b.money is None or a.money is None or b.money.currency != a.money.currency:
        return None
    diff = a.money.amount - b.money.amount
    return Decimal(0) if abs(diff) <= tolerance else diff


def _spin_rejected(obs: S2Observation, market: MarketContext) -> CheckResult:
    """Rechazada = aviso de saldo insuficiente visible Y saldo del juego sin cambios Y ninguna
    tirada completada. El "cambio visual" tras pulsar no basta: suele ser la ventana del aviso."""
    cid = CheckId.SPIN_REJECTED
    msg, ev = obs.message, _evidence(obs.message)
    if obs.spin_started is None:
        return CheckResult.inconclusive(cid, "no se llegó a intentar la tirada")
    if problem := _precondition_problem(obs):
        return CheckResult.inconclusive(cid, problem, evidence=ev)
    change = _game_balance_change(obs, market.money_tolerance)
    if obs.spin_completed or (change is not None and change < 0):
        what = "se completó una tirada" if obs.spin_completed else f"el saldo del juego bajó {-change}"
        return CheckResult.failed(cid, f"la tirada no se rechazó con saldo insuficiente: {what}",
                                  expected="rechazo", observed="tirada", evidence=ev)
    if msg is not None and msg.matches_insufficient and change == 0:
        seen = "aunque hubo cambio visual (la ventana del aviso)" if obs.spin_started else "sin cambio visual"
        return CheckResult.passed(cid, f"tirada rechazada: aviso «{msg.text}» y saldo del juego sin cambios, {seen}",
                                  evidence=ev)
    if msg is not None and msg.matches_insufficient:
        return CheckResult.inconclusive(cid, "aviso visible, pero no se pudo confirmar que el saldo del juego no cambió",
                                        evidence=ev)
    return CheckResult.inconclusive(cid, "no se vio el mensaje de rechazo", evidence=ev)


def _message_language(obs: S2Observation, market: MarketContext) -> CheckResult:
    cid = CheckId.INSUFFICIENT_MESSAGE_LANGUAGE
    msg = obs.message
    if msg is None or msg.matches_insufficient is None:
        why = msg.reason if msg is not None and msg.reason else "no se pudo leer el mensaje"
        return CheckResult.inconclusive(cid, why, expected=market.language, evidence=_evidence(msg))
    ev = _evidence(msg)
    if not msg.matches_insufficient:
        return CheckResult.failed(cid, f"no aparece el mensaje de saldo insuficiente (leído «{msg.text}»)",
                                  expected=market.language, evidence=ev)
    if msg.lang_detected is None:
        return CheckResult.inconclusive(cid, f"mensaje visible pero sin idioma detectado: «{msg.text}»",
                                        expected=market.language, evidence=ev)
    if msg.lang_detected.split("-")[0].lower() != market.language.split("-")[0].lower():
        return CheckResult.failed(cid, f"mensaje en {msg.lang_detected}, se esperaba {market.language}: «{msg.text}»",
                                  expected=market.language, observed=msg.lang_detected, evidence=ev)
    return CheckResult.passed(cid, f"mensaje en {msg.lang_detected}: «{msg.text}»",
                              expected=market.language, observed=msg.lang_detected, evidence=ev)


def evaluate_s2(obs: S2Observation, market: MarketContext) -> list[CheckResult]:
    tol = market.money_tolerance
    results = [
        login_check(obs.logged_in, obs.login_assisted, obs.login_assisted_at),
        real_play_check(obs.play_mode, obs.open_error, obs.play_mode_reason, obs.open_evidence),
        currency_check([obs.game_before, obs.bet, obs.game_after], [obs.betsson_before, obs.betsson_after], market),
        _spin_rejected(obs, market),
        _message_language(obs, market),
        unchanged(CheckId.BETSSON_BALANCE_UNCHANGED, obs.betsson_before, obs.betsson_after, tol),
        unchanged(CheckId.INGAME_BALANCE_UNCHANGED, obs.game_before, obs.game_after, tol),
    ]
    return apply_ui_changed(results, obs.ui_changed)

