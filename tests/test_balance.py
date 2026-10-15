"""Tests de la regla del saldo (pieza crítica): después = antes − apuesta + ganancia."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from betsson.checks.balance import reconcile, unchanged
from betsson.core import CheckId, FailureKind, Money, Reading

pytestmark = pytest.mark.unit

TOL = Decimal("0.01")
ID = CheckId.BETSSON_BALANCE_RECONCILES


def r(amount: str | None, currency: str = "EUR", evidence: str | None = None) -> Reading:
    if amount is None:
        return Reading(raw_text="??", reason="inconclusive: OCR dudoso")
    return Reading(
        raw_text=amount,
        money=Money(amount=Decimal(amount), currency=currency),
        confidence=0.99,
        evidence_path=Path(evidence) if evidence else None,
    )


@pytest.mark.parametrize(
    ("before", "wager", "payout", "after"),
    [
        ("100.00", "0.20", "0.00", "99.80"),  # pierde
        ("100.00", "0.20", "1.50", "101.30"),  # gana
        ("100.00", "0.20", "0.20", "100.00"),  # recupera la apuesta
        ("100.00", "0.20", "0.00", "99.81"),  # dentro de la tolerancia
    ],
)
def test_reconcile_passes(before: str, wager: str, payout: str, after: str) -> None:
    res = reconcile(ID, r(before), r(wager), r(payout), r(after), TOL)
    assert res.status == "PASS", res.reason


def test_reconcile_fails_outside_tolerance() -> None:
    res = reconcile(ID, r("100.00"), r("0.20"), r("0.00"), r("99.70"), TOL)
    assert res.status == "FAIL"
    assert res.failure_kind is FailureKind.INTEGRATION
    assert res.expected == "99.80 EUR" and res.observed == "99.70 EUR"


def test_reconcile_detects_wager_not_deducted() -> None:
    res = reconcile(ID, r("100.00"), r("0.20"), r("0.00"), r("100.00"), TOL)
    assert res.failure_kind is FailureKind.INTEGRATION


def test_reconcile_missing_reading_is_inconclusive() -> None:
    res = reconcile(ID, r("100.00"), r("0.20"), r(None), r("99.80"), TOL)
    assert res.status == "FAIL"
    assert res.failure_kind is FailureKind.INCONCLUSIVE
    assert "ganancia" in res.reason and "OCR dudoso" in res.reason


def test_reconcile_none_reading_is_inconclusive() -> None:
    res = reconcile(ID, None, r("0.20"), r("0.00"), r("99.80"), TOL)
    assert res.failure_kind is FailureKind.INCONCLUSIVE
    assert "saldo antes (sin lectura)" in res.reason


def test_reconcile_mixed_currency_is_inconclusive() -> None:
    res = reconcile(ID, r("100.00"), r("0.20", "PEN"), r("0.00"), r("99.80"), TOL)
    assert res.failure_kind is FailureKind.INCONCLUSIVE
    assert "EUR, PEN" in res.reason


def test_reconcile_keeps_evidence() -> None:
    res = reconcile(ID, r("100.00", evidence="a.png"), r("0.20"), r("0.00"), r("99.80", evidence="b.png"), TOL)
    assert res.evidence == (Path("a.png"), Path("b.png"))


def test_zero_tolerance_is_exact() -> None:
    assert reconcile(ID, r("100.00"), r("0.20"), r("0.00"), r("99.81"), Decimal(0)).status == "FAIL"


def test_negative_tolerance_rejected() -> None:
    with pytest.raises(ValueError):
        reconcile(ID, r("1"), r("1"), r("0"), r("0"), Decimal("-0.01"))


def test_unchanged_passes_and_fails() -> None:
    uid = CheckId.BETSSON_BALANCE_UNCHANGED
    assert unchanged(uid, r("0.05"), r("0.05"), TOL).status == "PASS"
    res = unchanged(uid, r("0.05"), r("0.00"), TOL)
    assert res.status == "FAIL" and res.failure_kind is FailureKind.INTEGRATION


def test_unchanged_missing_is_inconclusive() -> None:
    res = unchanged(CheckId.INGAME_BALANCE_UNCHANGED, r("0.05"), r(None), TOL)
    assert res.failure_kind is FailureKind.INCONCLUSIVE
