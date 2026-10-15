"""S1, tirada completada: de lo observado a las comprobaciones de PREPARACION §3."""
from __future__ import annotations

from dataclasses import dataclass

from betsson.checks.balance import evidence_of, read_amounts, reconcile
from betsson.checks.common import apply_ui_changed, currency_check, login_check, read_check, real_play_check
from betsson.core import CheckId, CheckResult, MarketContext, PlayMode, Reading, SpinEnd


@dataclass(frozen=True)
class S1Observation:
    """Lo que se vio durante S1. None = no se llegó a observar."""

    logged_in: bool | None = None
    play_mode: PlayMode | None = None
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


def _wager_is_used_wager(obs: S1Observation, market: MarketContext) -> CheckResult:
    """La apuesta mostrada es la descontada: antes + ganancia − después = apuesta, y no cambió."""
    cid = CheckId.WAGER_IS_USED_WAGER
    readings = {
        "saldo del juego antes": obs.game_before, "ganancia": obs.win,
        "saldo del juego después": obs.game_after, "apuesta": obs.bet, "apuesta tras la tirada": obs.bet_after,
    }
    evidence = evidence_of(readings)
    amounts, problem = read_amounts(readings)
    if problem:
        return CheckResult.inconclusive(cid, problem, evidence=evidence)
    bet, bet_after = amounts["apuesta"], amounts["apuesta tras la tirada"]
    deducted = amounts["saldo del juego antes"] + amounts["ganancia"] - amounts["saldo del juego después"]
    tol = market.money_tolerance
    detail = f"apuesta mostrada {bet}; descontado {deducted}; apuesta tras la tirada {bet_after}"
    ok = abs(deducted.amount - bet.amount) <= tol and abs(bet_after.amount - bet.amount) <= tol
    build = CheckResult.passed if ok else CheckResult.failed
    return build(cid, ("coincide: " if ok else "no coincide: ") + detail,
                 expected=str(bet), observed=str(deducted), evidence=evidence)


def evaluate_s1(obs: S1Observation, market: MarketContext) -> list[CheckResult]:
    tol = market.money_tolerance
    results = [
        login_check(obs.logged_in),
        real_play_check(obs.play_mode, obs.open_error),
        currency_check([obs.betsson_before, obs.game_before, obs.bet, obs.win, obs.game_after], market),
        read_check(CheckId.BETSSON_BALANCE_BEFORE, obs.betsson_before, "saldo de Betsson antes"),
        read_check(CheckId.WAGER_READ, obs.bet, "apuesta visible"),
        _spin_started(obs),
        _spin_completed(obs),
        read_check(CheckId.PAYOUT_READ, obs.win, "ganancia"),
        reconcile(CheckId.INGAME_BALANCE_CONSISTENT, obs.game_before, obs.bet, obs.win, obs.game_after, tol),
        reconcile(CheckId.BETSSON_BALANCE_RECONCILES, obs.betsson_before, obs.bet, obs.win, obs.betsson_after, tol),
        _wager_is_used_wager(obs, market),
    ]
    return apply_ui_changed(results, obs.ui_changed)
