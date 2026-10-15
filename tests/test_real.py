"""Validación real: A (web de Betsson) + B (ojos y perfiles) + C (escenarios e informe).

Solo en el runner propio en España: `pytest -m real --market es --headed`.
- El juego se elige con GAME_SLUG (variable de entorno o de la CI): ningún proveedor ni
  juego fijo en el código.
- Los mercados con real_execution_enabled=false (sin cuenta) se saltan con motivo.
- S1 usa la cuenta con saldo y S2 la cuenta sin saldo (account="empty"). Solo S2:
  `pytest -m real -k s2`. Plan B sin cuenta vacía: S2_ACCOUNT=funded S2_BET_TARGET=above_balance
  (run_scenario comprueba la precondición: apuesta visible > saldo visible).
- Modo de login (LOGIN_MODE):
  - "session" (por defecto si el mercado tiene site.browser_session): login asistido por
    una persona, autorizado por los mentores. El comprobador se conecta por CDP al Chrome
    con la sesión iniciada a mano (un puerto por cuenta), abre su propia pestaña y al
    terminar la cierra; nunca cierra el navegador ni hace logout. Sin Chrome escuchando o
    con la sesión caducada → skip con motivo.
  - "auto": login automatizado.
- NUNCA traza de red, HAR ni vídeo de Playwright: con la sesión iniciada la web descarga el
  perfil completo del cliente (datos personales). Las evidencias son capturas de pantalla.
  El contexto se crea aquí, no con los fixtures `context`/`page` de pytest-playwright, para
  que no les afecte --tracing/--video de pytest.ini.
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
from betsson.core import CheckId, FailureKind, RunResult, Scenario
from betsson.report.fingerprint import BaselineStore
from betsson.report.html import render_index

pytestmark = pytest.mark.real

site_mod = pytest.importorskip("betsson.site", reason="falta la web de Betsson (área A)")
loader = pytest.importorskip("betsson.market.loader", reason="faltan los mercados (área A)")
factory_mod = pytest.importorskip("betsson.game.factory", reason="faltan los ojos (área B)")
registry_mod = pytest.importorskip("betsson.profiles.registry", reason="falta el registro de perfiles (área B)")

VIEWPORT = {"width": 1366, "height": 768}
ACCOUNTS = {Scenario.S1: "funded", Scenario.S2: "empty"}
# S2 por defecto: cuenta sin saldo y apuesta mínima. Plan B si la cuenta vacía no está lista:
# S2_ACCOUNT=funded y S2_BET_TARGET=above_balance (apuesta por encima del saldo visible).
S2_ACCOUNT = os.getenv("S2_ACCOUNT", "empty").strip().lower()
S2_BET_TARGET = os.getenv("S2_BET_TARGET", "min").strip().lower()
# Estrategia de apuesta: "min" (por defecto, CLAUDE.md: apuesta mínima siempre) o "current"
# (juega con la apuesta visible; más rápido, solo si el equipo lo autoriza).
BET_STRATEGY = os.getenv("BET_STRATEGY", "").strip().lower() or None
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


@pytest.fixture(scope="module")
def login_mode(market: Any) -> str:
    has_session = getattr(getattr(market, "site", None), "browser_session", None) is not None
    mode = os.getenv("LOGIN_MODE", "session" if has_session else "auto").strip().lower()
    if mode not in {"session", "auto"}:
        pytest.fail(f"LOGIN_MODE desconocido: {mode!r} (session | auto)")
    return mode


def _scenario_dir(evidence_dir: Path, scenario: Scenario) -> Path:
    # evidence_dir = outputs/runs/<runId>/<market>/<test>/ (conftest de D)
    out = evidence_dir.parent / scenario.value
    out.mkdir(parents=True, exist_ok=True)
    return out


class _Player:
    """Abre la web de Betsson para una cuenta y la cierra bien al terminar."""

    def __init__(self, request: pytest.FixtureRequest, market: Any, mode: str) -> None:
        self.request, self.market, self.mode = request, market, mode
        self._close: list[Any] = []

    def site(self, account: str, out: Path) -> Any:
        if self.mode == "session":
            playwright = self.request.getfixturevalue("playwright")
            try:
                site, _browser = site_mod.BetssonSite.attach_cdp(playwright, self.market, account=account,
                                                                 evidence_dir=out)
            except site_mod.SessionUnavailable as exc:
                pytest.skip(f"login asistido: no hay sesión de jugador disponible para '{account}' ({exc})")
            self._close.append(site.page.close)  # solo nuestra pestaña: nunca browser.close() ni logout
            return site
        browser = self.request.getfixturevalue("browser")
        # Sin traza de red ni HAR ni vídeo: con la sesión iniciada la web descarga el perfil
        # completo del cliente (datos personales). Las evidencias son capturas de pantalla.
        context = browser.new_context(viewport=VIEWPORT, device_scale_factor=1, locale=self.market.locale,
                                      timezone_id=self.market.timezone)
        self._close.append(context.close)
        return site_mod.BetssonSite(context.new_page(), self.market, account=account, evidence_dir=out)

    def close(self) -> None:
        for fn in reversed(self._close):
            try:
                fn()
            except Exception:  # cerrar no debe tapar el resultado del test
                pass


@pytest.fixture
def player(request: pytest.FixtureRequest, market: Any, login_mode: str) -> Iterator[_Player]:
    p = _Player(request, market, login_mode)
    yield p
    p.close()


def _run(scenario: Scenario, player: _Player, market: Any, slug: str, run_id: str, evidence_dir: Path) -> RunResult:
    out = _scenario_dir(evidence_dir, scenario)
    account = S2_ACCOUNT if scenario is Scenario.S2 else ACCOUNTS[scenario]
    bet_target = S2_BET_TARGET if scenario is Scenario.S2 else "min"
    if account not in {"funded", "empty"} or bet_target not in {"min", "above_balance"}:
        pytest.fail(f"configuración de S2 no válida: S2_ACCOUNT={account!r}, S2_BET_TARGET={bet_target!r}")
    if scenario is Scenario.S2 and account == "funded" and bet_target != "above_balance":
        pytest.fail("S2 con la cuenta con saldo necesita S2_BET_TARGET=above_balance")
    site = player.site(account, out)
    site.goto_lobby()
    run = run_scenario(
        market=market, scenario=scenario, site=site,
        registry=registry_mod.Registry(evidence_dir=out),
        eyes_factory=factory_mod.GameEyesFactory(evidence_dir=out),
        slug=slug, out_dir=out, run_id=run_id, baselines=BASELINES, bet_target=bet_target,
        **({"bet_strategy": BET_STRATEGY} if BET_STRATEGY else {}),
    )
    render_index(out.parent.parent)
    login = next((r for r in run.results if r.id is CheckId.LOGIN_OK), None)
    if run.results and login is not None and login.failure_kind is FailureKind.INCONCLUSIVE and site.login_assisted:
        pytest.skip(f"login asistido: {login.reason} (results.json escrito en {out.name}/)")
    return run


def _summary(run: RunResult) -> str:
    bad = [f"{r.id.value}: {r.reason}" for r in run.results if r.status == "FAIL"]
    head = f"{run.scenario.value}/{run.market} → {run.outcome}" + (f" (error: {run.error})" if run.error else "")
    return "\n".join([head, *bad])


def test_real_s1_spin_completed(player: _Player, market: Any, slug: str, run_id: str, evidence_dir: Path) -> None:
    run = _run(Scenario.S1, player, market, slug, run_id, evidence_dir)
    assert run.verdict == "PASS", _summary(run)


def test_real_s2_insufficient_funds(player: _Player, market: Any, slug: str, run_id: str, evidence_dir: Path) -> None:
    run = _run(Scenario.S2, player, market, slug, run_id, evidence_dir)
    assert run.verdict == "PASS", _summary(run)
