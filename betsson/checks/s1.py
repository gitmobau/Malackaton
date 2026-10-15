"""S1, tirada completada: de lo observado a las comprobaciones de PREPARACION §3."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from pathlib import Path

from betsson.checks.balance import evidence_of, read_amounts, reconcile
from betsson.checks.common import (
    apply_ui_changed,
    currency_check,
    login_check,
    positive_read_check,
    read_check,
    real_play_check,
)
from betsson.core import CheckId, CheckResult, MarketContext, Money, PlayMode, Reading, SpinEnd


@dataclass(frozen=True)
class S1Observation:
    """Lo que se vio durante S1. None = no se llegó a observar."""

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
    spin_started: bool | None = None
    spin_end: SpinEnd | None = None
    win: Reading | None = None
    game_after: Reading | None = None
    bet_after: Reading | None = None
    betsson_after: Reading | None = None
    ui_changed: str | None = None  # motivo si el perfil dejó de reconocer el juego
    min_bet: Decimal | None = None  # apuesta mínima del mercado (S1 no gira por encima)
    bet_strategy: str | None = None  # "step" | "min" | "current"
    bet_initial: Reading | None = None  # apuesta visible ANTES de tocarla
    bet_step_requested: bool = False  # se pidió set_bet("one_step") a los ojos
    bet_fallback_min: bool = False  # se bajó a la mínima porque la apuesta no cabía en el saldo


def bet_not_minimum(bet: Reading | None, min_bet: Decimal | None, tolerance: Decimal) -> str | None:
    """Motivo para no girar si la apuesta visible no es la mínima (o no se pudo leer)."""
    if bet is None or bet.money is None:
        return "no se pudo leer la apuesta visible: no se gira"
    if min_bet is not None and bet.money.amount - min_bet > tolerance:
        return f"la apuesta visible {bet.money} no es la mínima del mercado ({min_bet}): no se gira"
    return None


def _wager_read(obs: S1Observation, market: MarketContext) -> CheckResult:
    result = positive_read_check(CheckId.WAGER_READ, obs.bet, "apuesta visible")
    problem = bet_not_minimum(obs.bet, obs.min_bet, market.money_tolerance)
    if result.status == "PASS" and problem:
        return CheckResult.inconclusive(CheckId.WAGER_READ, problem, observed=result.observed,
                                        expected=str(obs.min_bet), evidence=result.evidence)
    return result


def _spin_started(obs: S1Observation) -> CheckResult:
    cid = CheckId.SPIN_STARTED
    if obs.spin_started:
        return CheckResult.passed(cid, "se vio empezar la tirada (cambio visual tras pulsar)")
    if obs.spin_started is None:
        return CheckResult.inconclusive(cid, "no se llegó a intentar la tirada")
    return CheckResult.inconclusive(cid, "se pulsó girar pero no se vio empezar la tirada")


def _spin_completed(obs: S1Observation) -> CheckResult:
    cid = CheckId.SPIN_COMPLETED
    end = obs.spin_end
    if end is None:
        return CheckResult.inconclusive(cid, "no hay señal de fin de tirada")
    evidence = (end.evidence_path,) if end.evidence_path else ()
    if end.completed:
        return CheckResult.passed(cid, f"la tirada terminó en {end.duration_s:.1f} s (pantalla estable)", evidence=evidence)
    return CheckResult.inconclusive(cid, end.reason or "no se vio terminar la tirada", evidence=evidence)


def _bet_change(obs: S1Observation, initial: Money, bet: Money, tol: Decimal) -> str | None:
    """Motivo de no concluyente si el cambio de apuesta pedido no se vio; None si se vio (o no se pidió)."""
    if not (obs.bet_step_requested or obs.bet_fallback_min):
        return None
    if abs(bet.amount - initial.amount) <= tol:
        return f"se pidió cambiar la apuesta y sigue en {initial}: no se puede comprobar que la mostrada es la usada"
    if obs.bet_fallback_min and bet.amount > initial.amount:
        return f"se pidió bajarla a la mínima (no cabía en el saldo) y subió de {initial} a {bet}"
    return None


def _wager_is_used_wager(obs: S1Observation, market: MarketContext) -> CheckResult:
    """La apuesta mostrada es la usada, sin depender de la regla del saldo:
    1) si se cambió la apuesta (step o reserva a la mínima), el cambio se ve en pantalla;
    2) la apuesta que se lee después de girar es la misma con la que se giró.
    (Que el saldo baje en esa apuesta lo comprueban ingame/betsson_balance_*.)"""
    cid = CheckId.WAGER_IS_USED_WAGER
    readings = {"apuesta antes de cambiarla": obs.bet_initial, "apuesta con la que se giró": obs.bet,
                "apuesta tras la tirada": obs.bet_after}
    evidence = evidence_of(readings)
    amounts, problem = read_amounts(readings)
    if problem:
        return CheckResult.inconclusive(cid, problem, evidence=evidence)
    initial, bet, after = (amounts[k] for k in readings)
    tol = market.money_tolerance
    if bet.amount <= 0:
        return CheckResult.inconclusive(cid, f"apuesta no positiva: {bet}", evidence=evidence)
    if change_problem := _bet_change(obs, initial, bet, tol):
        return CheckResult.inconclusive(cid, change_problem, expected=f"≠ {initial}", observed=str(bet),
                                        evidence=evidence)
    if abs(after.amount - bet.amount) > tol:
        return CheckResult.failed(cid, f"la apuesta cambió durante la tirada: se giró con {bet} y después se ve {after}",
                                  expected=str(bet), observed=str(after), evidence=evidence)
    moved = "" if abs(bet.amount - initial.amount) <= tol else (
        f"cambiada de {initial} a {bet} ({'baja' if bet.amount < initial.amount else 'sube'}); ")
    how = {"step": "un paso", "min": "a la mínima", "current": "la visible"}.get(obs.bet_strategy or "", "")
    return CheckResult.passed(cid, f"apuesta {how}: {moved}se giró con {bet} y tras la tirada sigue en {after}",
                              expected=str(bet), observed=str(after), evidence=evidence)


def evaluate_s1(obs: S1Observation, market: MarketContext) -> list[CheckResult]:
    tol = market.money_tolerance
    results = [
        login_check(obs.logged_in, obs.login_assisted, obs.login_assisted_at),
        real_play_check(obs.play_mode, obs.open_error, obs.play_mode_reason, obs.open_evidence),
        currency_check([obs.game_before, obs.bet, obs.win, obs.game_after], [obs.betsson_before, obs.betsson_after], market),
        read_check(CheckId.BETSSON_BALANCE_BEFORE, obs.betsson_before, "saldo de Betsson antes"),
        _wager_read(obs, market),
        _spin_started(obs),
        _spin_completed(obs),
        read_check(CheckId.PAYOUT_READ, obs.win, "ganancia"),
        reconcile(CheckId.INGAME_BALANCE_CONSISTENT, obs.game_before, obs.bet, obs.win, obs.game_after, tol),
        reconcile(CheckId.BETSSON_BALANCE_RECONCILES, obs.betsson_before, obs.bet, obs.win, obs.betsson_after, tol),
        _wager_is_used_wager(obs, market),
    ]
    return apply_ui_changed(results, obs.ui_changed)
