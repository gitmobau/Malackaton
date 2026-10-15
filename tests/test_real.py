"""Validación real: A (web de Betsson) + B (ojos y perfiles) + C (escenarios e informe).

Solo en el runner propio en España: `pytest -m real --market es --headed`.
- El juego se elige con GAME_SLUG (variable de entorno o secreto de la CI): ningún
  proveedor ni juego fijo en el código.
- Los mercados con real_execution_enabled=false (sin cuenta) se saltan con motivo.
- S1 usa la cuenta con saldo y S2 la cuenta sin saldo (account="empty").
- La traza la gestiona A por trozos y se pausa durante el login; por eso el contexto
  se crea aquí y no con el fixture `context` de pytest-playwright (que grabaría el login).
- Deja results.json y report.html en outputs/runs/<runId>/<market>/<S1|S2>/ y el índice
  del run en outputs/runs/<runId>/report.html.
- Compara cada juego con su huella de la última ejecución buena (outputs/baselines/ o
  BASELINE_DIR) y avisa si el juego del proveedor ha cambiado.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from betsson.checks.scenario import run_scenario
from betsson.core import RunResult, Scenario
from betsson.report.fingerprint import BaselineStore
from betsson.report.html import render_index

pytestmark = pytest.mark.real

site_mod = pytest.importorskip("betsson.site", reason="falta la web de Betsson (área A)")
loader = pytest.importorskip("betsson.market.loader", reason="faltan los mercados (área A)")
factory_mod = pytest.importorskip("betsson.game.factory", reason="faltan los ojos (área B)")
registry_mod = pytest.importorskip("betsson.profiles.registry", reason="falta el registro de perfiles (área B)")

VIEWPORT = {"width": 1366, "height": 768}
ACCOUNTS = {Scenario.S1: "funded", Scenario.S2: "empty"}
# Huellas de referencia por juego: en el runner propio persisten entre ejecuciones.
BASELINES = BaselineStore(Path(os.getenv("BASELINE_DIR", "outputs/baselines")) / "game")


@pytest.fixture(scope="module")
def market(market_id: str) -> Any:
    m = loader.load_market(market_id)
    if not getattr(m, "real_execution_enabled", False):
        pytest.skip(f"mercado {market_id} configurado; ejecución real desactivada: sin cuenta")
    return m


@pytest.fixture(scope="module")
def slug() -> str:
    value = os.getenv("GAME_SLUG", "").strip()
    if not value:
        pytest.skip("define GAME_SLUG con el slug del juego de Betsson que se va a validar")
    return value


def _scenario_dir(evidence_dir: Path, scenario: Scenario) -> Path:
    # evidence_dir = outputs/runs/<runId>/<market>/<test>/ (conftest de D)
    out = evidence_dir.parent / scenario.value
    out.mkdir(parents=True, exist_ok=True)
    return out


@pytest.fixture
def player(browser: Any, market: Any) -> Iterator[Any]:
    """Contexto de navegador como un jugador, con traza por trozos (A la pausa en el login)."""
    context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1, locale=market.locale,
                                  timezone_id=market.timezone)
    context.tracing.start(screenshots=True, snapshots=True)
    holder: dict[str, Any] = {"context": context, "out": None}
    yield holder
    out = holder["out"]
    if out is not None:
        context.tracing.stop(path=out / "trace-final.zip")
    else:
        context.tracing.stop()
    context.close()


def _run(scenario: Scenario, player: dict[str, Any], market: Any, slug: str, run_id: str,
         evidence_dir: Path) -> RunResult:
    out = _scenario_dir(evidence_dir, scenario)
    player["out"] = out
    context = player["context"]
    page = context.new_page()
    trace = site_mod.ChunkedTrace(context, out)
    site = site_mod.BetssonSite(page, market, account=ACCOUNTS[scenario], evidence_dir=out, trace=trace)
    site.goto_lobby()
    run = run_scenario(
        market=market, scenario=scenario, site=site,
        registry=registry_mod.Registry(evidence_dir=out),
        eyes_factory=factory_mod.GameEyesFactory(evidence_dir=out),
        slug=slug, out_dir=out, run_id=run_id, baselines=BASELINES,
    )
    render_index(out.parent.parent)
    return run


def _summary(run: RunResult) -> str:
    bad = [f"{r.id.value}: {r.reason}" for r in run.results if r.status == "FAIL"]
    head = f"{run.scenario.value}/{run.market} → {run.outcome}" + (f" (error: {run.error})" if run.error else "")
    return "\n".join([head, *bad])


def test_real_s1_spin_completed(player: dict[str, Any], market: Any, slug: str, run_id: str,
                                evidence_dir: Path) -> None:
    run = _run(Scenario.S1, player, market, slug, run_id, evidence_dir)
    assert run.verdict == "PASS", _summary(run)


def test_real_s2_insufficient_funds(player: dict[str, Any], market: Any, slug: str, run_id: str,
                                    evidence_dir: Path) -> None:
    run = _run(Scenario.S2, player, market, slug, run_id, evidence_dir)
    assert run.verdict == "PASS", _summary(run)
