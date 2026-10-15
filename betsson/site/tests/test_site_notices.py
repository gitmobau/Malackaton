"""Avisos de Betsson al abrir el juego: GameHandle.notices = tuple[betsson.core.Notice] con su captura.

Reproduce en local los dos diálogos reales del 15-oct (sin red, con route):
- DGOJ con saldo 0: sin límite de pérdidas y con "No dispones de saldo, pero puedes crear la sesión…".
- Aviso previo: "Hace menos de 60 mins. que finalizaste tu sesión de juego."
"""
from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser

from betsson.core import Notice
from betsson.market import load_market
from betsson.site import BetssonSite

HIDE = "this.closest('[role=dialog]').hidden = true"
DGOJ_NO_BALANCE = f"""<div role='dialog'>
  <h2>Se ha sobrepasado el límite de tiempo de sesión</h2><p>Tiempo de juego:</p>
  <button>15 Min</button><button>5 Horas</button>
  <button onclick="{HIDE}">Iniciar sesión</button>
  <div><span>No dispones de saldo, pero puedes crear la sesión y jugar tiradas gratuitas en caso de tenerlas
  disponibles.</span></div>
</div>"""
PRE_NOTICE = f"""<div role='dialog'>
  <h2>Atención</h2><p>Hace menos de 60 mins. que finalizaste tu sesión de juego.</p>
  <button onclick="{HIDE}">Iniciar sesión</button><button>Volver a Casino</button>
</div>"""


@pytest.fixture()
def site_with(browser: Browser, tmp_path: Path):
    market = load_market("es")
    context = browser.new_context()

    def _make(body: str) -> BetssonSite:
        page = context.new_page()
        page.route(f"{market.origin}/**", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=f"<html><body>{body}</body></html>"))
        page.goto(f"{market.origin}/casino/tragaperras-slots/big-bass-splash")
        return BetssonSite(page, market, evidence_dir=tmp_path)

    yield _make
    context.close()


def test_dgoj_without_balance_is_accepted_and_noticed(site_with) -> None:
    site = site_with(DGOJ_NO_BALANCE)
    evidence: list[Path] = []
    assert site._accept_session_limits(evidence)  # solo tiempo: no hay bloque de pérdidas con saldo 0
    [notice] = site.launch_notices
    assert isinstance(notice, Notice)
    assert notice.text.startswith("No dispones de saldo")
    assert notice.evidence_path is not None and notice.evidence_path.is_file()


def test_pre_session_notice_is_accepted_and_noticed(site_with) -> None:
    site = site_with(PRE_NOTICE)
    evidence: list[Path] = []
    assert site._accept_pre_session_notice(evidence)
    [notice] = site.launch_notices
    assert "Hace menos de 60 mins" in notice.text
    assert notice.evidence_path is not None and notice.evidence_path.is_file()
