"""run_scenario: ejecuta S1 o S2 con las piezas inyectadas y escribe results.json + report.html.

No conoce ningún proveedor ni mercado concreto: todo llega por las interfaces de core.
Orden: login → saldo de Betsson → abrir juego → perfil (resolve + ensure_recognized)
→ ojos → jugar → saldo de Betsson después. Cada paso que no se llega a hacer queda
como None y su comprobación sale no concluyente (nunca PASS).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from betsson.checks.s1 import S1Observation, evaluate_s1
from betsson.checks.s2 import S2Observation, evaluate_s2
from betsson.core import (
    BetssonSite,
    CheckResult,
    GameEyes,
    GameEyesFactory,
    GameOpenError,
    MarketContext,
    ProviderRegistry,
    ProviderUIChanged,
    RunResult,
    Scenario,
)
from betsson.report.html import render_run

log = logging.getLogger(__name__)

RESULTS_FILE = "results.json"


def _prepare(
    site: BetssonSite, registry: ProviderRegistry, eyes_factory: GameEyesFactory,
    market: MarketContext, slug: str, obs: dict[str, Any],
) -> tuple[GameEyes | None, str | None]:
    """Login, saldo inicial, apertura del juego y perfil. Devuelve (ojos, nombre del perfil)."""
    obs["logged_in"] = site.login()
    if not obs["logged_in"]:
        return None, None
    obs["betsson_before"] = site.read_balance()
    try:
        handle = site.open_game(slug)
    except GameOpenError as exc:
        obs["open_error"] = str(exc)
        return None, None
    obs["play_mode"] = handle.play_mode
    profile = registry.resolve(handle.iframe_url, handle.capture())
    try:
        registry.ensure_recognized(profile, handle.capture())
    except ProviderUIChanged as exc:
        obs["ui_changed"] = exc.reason
        return None, profile.name
    return eyes_factory(handle, profile, market), profile.name


def _play_s1(eyes: GameEyes, site: BetssonSite, obs: dict[str, Any]) -> None:
    obs["bet"] = eyes.set_bet("min")
    obs["game_before"] = eyes.read_balance()
    obs["spin_started"] = eyes.spin()
    if obs["spin_started"]:
        obs["spin_end"] = eyes.wait_spin_end()
    obs["win"] = eyes.read_win()
    obs["game_after"] = eyes.read_balance()
    obs["bet_after"] = eyes.read_bet()
    obs["betsson_after"] = site.read_balance()


def _play_s2(eyes: GameEyes, site: BetssonSite, obs: dict[str, Any]) -> None:
    # Con la cuenta sin saldo basta la mínima; con saldo, el caller elige "above_balance" vía bet_target.
    obs["bet"] = eyes.set_bet(obs.pop("bet_target", "min"))
    obs["game_before"] = eyes.read_balance()
    obs["spin_started"] = eyes.spin()
    obs["message"] = eyes.read_message()
    obs["game_after"] = eyes.read_balance()
    obs["betsson_after"] = site.read_balance()


def _evaluate(scenario: Scenario, obs: dict[str, Any], market: MarketContext) -> list[CheckResult]:
    if scenario is Scenario.S1:
        return evaluate_s1(S1Observation(**obs), market)
    obs.pop("bet_target", None)
    return evaluate_s2(S2Observation(**obs), market)


def _relative(path: Path, base: Path) -> Path:
    try:
        return path.resolve().relative_to(base.resolve()) if path.is_absolute() else path
    except ValueError:
        return Path(path.name)  # fuera de la carpeta del run: solo el nombre, nunca rutas locales


def _with_relative_evidence(run: RunResult, base: Path) -> RunResult:
    results = tuple(r.model_copy(update={"evidence": tuple(_relative(p, base) for p in r.evidence)}) for r in run.results)
    evidence = tuple(_relative(p, base) for p in run.evidence)
    return run.model_copy(update={"results": results, "evidence": evidence})


def run_scenario(
    *,
    market: MarketContext,
    scenario: Scenario,
    site: BetssonSite,
    registry: ProviderRegistry,
    eyes_factory: GameEyesFactory,
    slug: str,
    out_dir: Path,
    run_id: str,
    bet_target: str = "min",
) -> RunResult:
    """Ejecuta un escenario en un mercado y deja results.json y report.html en out_dir."""
    started = datetime.now(timezone.utc)
    obs: dict[str, Any] = {"bet_target": bet_target} if scenario is Scenario.S2 else {}
    provider: str | None = None
    error: str | None = None
    warnings: list[str] = []
    try:
        eyes, provider = _prepare(site, registry, eyes_factory, market, slug, obs)
        if eyes is not None:
            (_play_s1 if scenario is Scenario.S1 else _play_s2)(eyes, site, obs)
    except ProviderUIChanged as exc:
        obs["ui_changed"] = exc.reason
    except Exception as exc:  # el run se corta, pero deja results.json con el motivo
        log.exception("run_scenario %s/%s se cortó", market.id, scenario.value)
        error = f"{type(exc).__name__}: {exc}"
    if obs.get("ui_changed"):
        warnings.append(f"PROVIDER_UI_CHANGED: {obs['ui_changed']}")

    run = RunResult(
        run_id=run_id, market=market.id, scenario=scenario, provider=provider, game=slug,
        started_at=started, finished_at=datetime.now(timezone.utc),
        results=tuple(_evaluate(scenario, obs, market)), warnings=tuple(warnings), error=error,
    )
    run = _with_relative_evidence(run, out_dir)
    run.write_json(out_dir / RESULTS_FILE)
    render_run(run, out_dir)
    return run
