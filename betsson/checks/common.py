"""Comprobaciones comunes a S1 y S2. Funciones puras: lecturas -> CheckResult."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from betsson.core import CheckId, CheckResult, FailureKind, MarketContext, PlayMode, Reading

# Comprobaciones que no dependen de leer el canvas del juego: no pasan a
# PROVIDER_UI_CHANGED aunque el perfil deje de reconocer el juego.
NOT_SCREEN_CHECKS = frozenset({CheckId.LOGIN_OK, CheckId.REAL_PLAY, CheckId.BETSSON_BALANCE_BEFORE})


LOGIN_ASSISTED_WARNING = "login asistido por una persona: el resto de la ejecución es automática"


def login_check(logged_in: bool | None, assisted: bool = False, assisted_at: datetime | None = None) -> CheckResult:
    if logged_in is None:
        return CheckResult.inconclusive(CheckId.LOGIN_OK, "no se llegó a intentar el login")
    if assisted and not logged_in:
        # Sin sesión humana válida no se puede juzgar la integración de Betsson.
        return CheckResult.inconclusive(CheckId.LOGIN_OK, "sesión caducada o ausente en el login asistido",
                                        observed="sin sesión")
    if logged_in and assisted:
        when = f" a las {assisted_at.astimezone().strftime('%H:%M')}" if assisted_at else ""
        return CheckResult.passed(CheckId.LOGIN_OK, f"sesión de jugador válida (login asistido por una persona{when})",
                                  observed="asistido")
    if logged_in:
        return CheckResult.passed(CheckId.LOGIN_OK, "sesión iniciada")
    return CheckResult.failed(CheckId.LOGIN_OK, "no se pudo iniciar sesión")


def real_play_check(play_mode: PlayMode | None, open_error: str | None = None, why: str | None = None,
                    evidence: tuple[Path, ...] = ()) -> CheckResult:
    cid = CheckId.REAL_PLAY
    suffix = f" ({why})" if why else ""
    if open_error:
        return CheckResult.failed(cid, f"no se pudo abrir el juego: {open_error}", evidence=evidence)
    if play_mode == "real":
        return CheckResult.passed(cid, f"juego abierto en Real Play{suffix}", observed="real", evidence=evidence)
    if play_mode == "demo":
        return CheckResult.failed(cid, f"el juego se abrió en modo demo{suffix}", expected="real", observed="demo",
                                  evidence=evidence)
    return CheckResult.inconclusive(cid, f"no se pudo confirmar el modo de juego{suffix}", observed=str(play_mode),
                                    evidence=evidence)


def positive_read_check(check_id: CheckId, reading: Reading | None, what: str) -> CheckResult:
    """Como read_check, pero un importe 0 o negativo no vale (p. ej. la apuesta)."""
    result = read_check(check_id, reading, what)
    if result.status == "PASS" and reading is not None and reading.money is not None and reading.money.amount <= 0:
        return CheckResult.inconclusive(check_id, f"{what} no positivo: {reading.money}", observed=str(reading.money),
                                        evidence=result.evidence)
    return result


def read_check(check_id: CheckId, reading: Reading | None, what: str) -> CheckResult:
    if reading is None:
        return CheckResult.inconclusive(check_id, f"{what}: sin lectura")
    evidence = (reading.evidence_path,) if reading.evidence_path else ()
    if reading.money is None:
        return CheckResult.inconclusive(check_id, f"{what}: {reading.reason}", observed=reading.raw_text, evidence=evidence)
    return CheckResult.passed(
        check_id, f"{what} leído: {reading.money} («{reading.raw_text}»)", observed=str(reading.money), evidence=evidence
    )


def _seen(readings: Iterable[Reading | None]) -> list[Reading]:
    return [r for r in readings if r is not None and r.money is not None and r.currency_seen]


def currency_check(game: Iterable[Reading | None], betsson: Iterable[Reading | None],
                   market: MarketContext) -> CheckResult:
    """La moneda VISTA es la del mercado. Hace falta verla al menos en el juego; lo no visto no cuenta."""
    cid = CheckId.CURRENCY_MATCHES_MARKET
    game_seen = _seen(game)
    seen = game_seen + _seen(betsson)
    evidence = tuple(r.evidence_path for r in seen if r.evidence_path)
    if not game_seen:
        return CheckResult.inconclusive(cid, "no se vio el símbolo o código de moneda en el juego",
                                        expected=market.currency_code, evidence=evidence)
    wrong = sorted({r.money.currency for r in seen if r.money and r.money.currency != market.currency_code})
    if wrong:
        texts = ", ".join(f"«{r.raw_text}»" for r in seen)
        return CheckResult.failed(
            cid, f"moneda visible {', '.join(wrong)} en {texts}", expected=market.currency_code,
            observed=", ".join(wrong), evidence=evidence,
        )
    return CheckResult.passed(
        cid, f"{len(seen)} importes visibles en {market.currency_code}", expected=market.currency_code,
        observed=market.currency_code, evidence=evidence,
    )


def apply_ui_changed(results: list[CheckResult], ui_changed: str | None) -> list[CheckResult]:
    """Si el perfil no reconoce el juego, lo no concluyente de pantalla pasa a PROVIDER_UI_CHANGED."""
    if not ui_changed:
        return results
    return [
        CheckResult.ui_changed(r.id, ui_changed, evidence=r.evidence)
        if r.failure_kind is FailureKind.INCONCLUSIVE and r.id not in NOT_SCREEN_CHECKS
        else r
        for r in results
    ]
