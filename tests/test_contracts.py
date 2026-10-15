"""Tests del contrato de core: veredictos, Money, Rect y serialización de results.json."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from betsson.core import (
    SCENARIO_CHECKS,
    CheckId,
    CheckResult,
    CurrencyMismatch,
    FailureKind,
    Money,
    ProviderUIChanged,
    Reading,
    Rect,
    RunResult,
    Scenario,
)

pytestmark = pytest.mark.unit


def eur(amount: str) -> Money:
    return Money(amount=Decimal(amount), currency="EUR")


def all_pass(scenario: Scenario) -> tuple[CheckResult, ...]:
    return tuple(CheckResult.passed(c, "ok") for c in SCENARIO_CHECKS[scenario])


# --- Money ------------------------------------------------------------------


def test_money_normalises_currency_and_is_exact() -> None:
    m = Money(amount=Decimal("0.1"), currency="eur") + eur("0.2")
    assert m == eur("0.3")


def test_money_rejects_mixed_currencies() -> None:
    with pytest.raises(CurrencyMismatch):
        eur("1") - Money(amount=Decimal("1"), currency="PEN")


@pytest.mark.parametrize("code", ["EU", "EURO", "€", "S/"])
def test_money_rejects_non_iso_currency(code: str) -> None:
    with pytest.raises(ValidationError):
        Money(amount=Decimal("1"), currency=code)


def test_money_is_immutable() -> None:
    m = eur("1")
    with pytest.raises(ValidationError):
        m.amount = Decimal("2")  # type: ignore[misc]


# --- CheckResult --------------------------------------------------------------


def test_inconclusive_is_fail_with_prefix() -> None:
    r = CheckResult.inconclusive(CheckId.WAGER_READ, "OCR con confianza 0.4")
    assert r.status == "FAIL"
    assert r.failure_kind is FailureKind.INCONCLUSIVE
    assert r.reason == "inconclusive: OCR con confianza 0.4"


def test_ui_changed_is_not_integration_failure() -> None:
    r = CheckResult.ui_changed(CheckId.SPIN_STARTED, "no se encuentra el botón de girar")
    assert r.status == "FAIL"
    assert r.failure_kind is FailureKind.PROVIDER_UI_CHANGED
    assert r.reason.startswith("PROVIDER_UI_CHANGED")


def test_pass_cannot_carry_failure_kind() -> None:
    with pytest.raises(ValidationError):
        CheckResult(id=CheckId.LOGIN_OK, status="PASS", reason="ok", failure_kind=FailureKind.INTEGRATION)


def test_fail_needs_failure_kind() -> None:
    with pytest.raises(ValidationError):
        CheckResult(id=CheckId.LOGIN_OK, status="FAIL", reason="no entra")


def test_inconclusive_without_prefix_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CheckResult(id=CheckId.LOGIN_OK, status="FAIL", reason="dudoso", failure_kind=FailureKind.INCONCLUSIVE)


# --- RunResult ----------------------------------------------------------------


@pytest.mark.parametrize("scenario", list(Scenario))
def test_run_passes_only_with_every_check_passing(scenario: Scenario) -> None:
    run = RunResult(run_id="r1", market="es", scenario=scenario, results=all_pass(scenario))
    assert run.verdict == "PASS"
    assert run.missing_checks == []


def test_missing_check_fails_the_run() -> None:
    results = all_pass(Scenario.S1)[:-1]
    run = RunResult(run_id="r1", market="es", scenario=Scenario.S1, results=results)
    assert run.verdict == "FAIL"
    assert run.missing_checks == [SCENARIO_CHECKS[Scenario.S1][-1]]


def test_empty_run_is_fail() -> None:
    assert RunResult(run_id="r1", market="es", scenario=Scenario.S2).verdict == "FAIL"


def test_one_inconclusive_fails_the_run_and_flags_nothing_else() -> None:
    results = all_pass(Scenario.S2)[:-1] + (CheckResult.inconclusive(CheckId.INGAME_BALANCE_UNCHANGED, "sin lectura"),)
    run = RunResult(run_id="r1", market="es", scenario=Scenario.S2, results=results)
    assert run.verdict == "FAIL"
    assert run.provider_ui_changed is False


def test_ui_changed_is_flagged_on_run() -> None:
    results = all_pass(Scenario.S1)[:-1] + (CheckResult.ui_changed(CheckId.WAGER_IS_USED_WAGER, "zona BET no encontrada"),)
    run = RunResult(run_id="r1", market="es", scenario=Scenario.S1, results=results)
    assert run.provider_ui_changed is True


def test_duplicate_checks_rejected() -> None:
    dup = (CheckResult.passed(CheckId.LOGIN_OK, "ok"),) * 2
    with pytest.raises(ValidationError):
        RunResult(run_id="r1", market="es", scenario=Scenario.S1, results=dup)


def test_results_json_round_trip(tmp_path: Path) -> None:
    run = RunResult(
        run_id="r1",
        market="es",
        scenario=Scenario.S1,
        provider="generic-vision",
        results=(CheckResult.passed(CheckId.LOGIN_OK, "ok", evidence=(Path("login.png"),)),),
    )
    path = run.write_json(tmp_path / "es" / "S1" / "results.json")
    text = path.read_text(encoding="utf-8")
    assert '"verdict": "FAIL"' in text and '"login_ok"' in text
    assert RunResult.read_json(path) == run


# --- Interfaces -----------------------------------------------------------------


def test_rect_must_fit_in_canvas() -> None:
    Rect(x=0.5, y=0.5, w=0.5, h=0.5)
    with pytest.raises(ValidationError):
        Rect(x=0.6, y=0.1, w=0.5, h=0.1)
    with pytest.raises(ValidationError):
        Rect(x=10, y=10, w=100, h=20)  # píxeles, no fracciones


def test_reading_without_money_is_not_ok() -> None:
    assert not Reading(raw_text="1,2?", reason="inconclusive: OCR dudoso").ok
    assert Reading(raw_text="1,20 €", money=eur("1.20"), confidence=0.98).ok


def test_provider_ui_changed_carries_reason() -> None:
    err = ProviderUIChanged("ningún perfil supera 0.5", evidence=[Path("frame.png")])
    assert err.code == "PROVIDER_UI_CHANGED"
    assert err.reason == "ningún perfil supera 0.5"
