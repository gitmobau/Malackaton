"""Regla del saldo: después = antes − apuesta + ganancia (con tolerancia del mercado).

Trabaja con lecturas (Reading) para conservar el texto visto y la evidencia.
Si falta un dato o las monedas no coinciden, el resultado es no concluyente:
nunca se da un PASS sin poder verificarlo.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from betsson.core import CheckId, CheckResult, Money, Reading


def _evidence(readings: dict[str, Reading | None]) -> tuple[Path, ...]:
    return tuple(r.evidence_path for r in readings.values() if r is not None and r.evidence_path is not None)


def _amounts(readings: dict[str, Reading | None]) -> tuple[dict[str, Money], str | None]:
    """Importes leídos y, si alguno falta o difiere la moneda, el motivo de no concluyente."""
    missing = []
    for name, r in readings.items():
        if r is None or r.money is None:
            detail = r.reason if r is not None and r.reason else "sin lectura"
            missing.append(f"{name} ({detail})")
    if missing:
        return {}, "no se pudo leer " + ", ".join(missing)
    amounts = {name: r.money for name, r in readings.items() if r is not None and r.money is not None}
    currencies = sorted({m.currency for m in amounts.values()})
    if len(currencies) > 1:
        return {}, "monedas distintas en las lecturas: " + ", ".join(currencies)
    return amounts, None


def _verdict(check_id: CheckId, ok: bool, ok_text: str, ko_text: str, detail: str,
             expected: Money, observed: Money, evidence: tuple[Path, ...]) -> CheckResult:
    build = CheckResult.passed if ok else CheckResult.failed
    text = ok_text if ok else ko_text
    return build(check_id, f"{text}: {detail}", expected=str(expected), observed=str(observed), evidence=evidence)


def _check_tolerance(tolerance: Decimal) -> None:
    if tolerance < 0:
        raise ValueError("la tolerancia no puede ser negativa")


def reconcile(
    check_id: CheckId,
    before: Reading | None,
    wager: Reading | None,
    payout: Reading | None,
    after: Reading | None,
    tolerance: Decimal,
) -> CheckResult:
    """Comprueba que after = before − wager + payout, dentro de la tolerancia."""
    _check_tolerance(tolerance)
    readings = {"saldo antes": before, "apuesta": wager, "ganancia": payout, "saldo después": after}
    evidence = _evidence(readings)
    amounts, problem = _amounts(readings)
    if problem:
        return CheckResult.inconclusive(check_id, problem, evidence=evidence)

    b, w, p, a = (amounts[k] for k in readings)
    expected = b - w + p
    diff = abs(a.amount - expected.amount)
    detail = f"{b} − {w} + {p} = {expected}; leído {a}; diferencia {diff} (tolerancia {tolerance})"
    return _verdict(check_id, diff <= tolerance, "cuadra", "no cuadra", detail, expected, a, evidence)


def unchanged(
    check_id: CheckId,
    before: Reading | None,
    after: Reading | None,
    tolerance: Decimal,
) -> CheckResult:
    """Comprueba que el saldo no ha cambiado (S2), dentro de la tolerancia."""
    _check_tolerance(tolerance)
    readings = {"saldo antes": before, "saldo después": after}
    evidence = _evidence(readings)
    amounts, problem = _amounts(readings)
    if problem:
        return CheckResult.inconclusive(check_id, problem, evidence=evidence)

    b, a = amounts["saldo antes"], amounts["saldo después"]
    diff = abs(a.amount - b.amount)
    detail = f"antes {b}; después {a}; diferencia {diff} (tolerancia {tolerance})"
    return _verdict(check_id, diff <= tolerance, "sin cambios", "el saldo cambió", detail, b, a, evidence)
