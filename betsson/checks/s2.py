"""S2, saldo insuficiente: de lo observado a las comprobaciones de PREPARACION §3."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from betsson.checks.balance import unchanged
from betsson.checks.common import apply_ui_changed, currency_check, login_check, real_play_check
from betsson.core import CheckId, CheckResult, MarketContext, Message, PlayMode, Reading


@dataclass(frozen=True)
class S2Observation:
    """Lo que se vio durante S2. None = no se llegó a observar."""

    logged_in: bool | None = None
    play_mode: PlayMode | None = None
    play_mode_reason: str | None = None
    open_evidence: tuple[Path, ...] = ()  # pasos del jugador al abrir el juego
    open_error: str | None = None
    betsson_before: Reading | None = None
    game_before: Reading | None = None
    bet: Reading | None = None
    spin_started: bool | None = None
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


def _spin_rejected(obs: S2Observation) -> CheckResult:
    """Rechazada = no se vio empezar la tirada Y se ve el mensaje de saldo insuficiente."""
    cid = CheckId.SPIN_REJECTED
    msg, ev = obs.message, _evidence(obs.message)
    if obs.spin_started is not None and (problem := _precondition_problem(obs)):
        return CheckResult.inconclusive(cid, problem, evidence=ev)
    if obs.spin_started:
        return CheckResult.failed(cid, "la tirada empezó con saldo insuficiente", expected="rechazo", observed="tirada", evidence=ev)
    if obs.spin_started is None:
        return CheckResult.inconclusive(cid, "no se llegó a intentar la tirada")
    if msg is not None and msg.matches_insufficient:
        return CheckResult.passed(cid, f"tirada no iniciada y mensaje visible: «{msg.text}»", evidence=ev)
    return CheckResult.inconclusive(cid, "no se vio empezar la tirada, pero tampoco el mensaje de rechazo", evidence=ev)


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
        login_check(obs.logged_in),
        real_play_check(obs.play_mode, obs.open_error, obs.play_mode_reason, obs.open_evidence),
        currency_check([obs.game_before, obs.bet, obs.game_after], [obs.betsson_before, obs.betsson_after], market),
        _spin_rejected(obs),
        _message_language(obs, market),
        unchanged(CheckId.BETSSON_BALANCE_UNCHANGED, obs.betsson_before, obs.betsson_after, tol),
        unchanged(CheckId.INGAME_BALANCE_UNCHANGED, obs.game_before, obs.game_after, tol),
    ]
    return apply_ui_changed(results, obs.ui_changed)

