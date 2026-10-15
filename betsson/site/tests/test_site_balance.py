"""read_balance solo lee el botón de saldo de la cabecera: nunca un banner con "€".

Regresión del 15-oct: con sesión, leyó 5000,00 EUR del banner "¡5.000€ en juego con Money Train 5!".
Sin red: la página se sirve en local con route, con el mismo data-test-id que la web real.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import Browser

from betsson.market import load_market
from betsson.site import BetssonSite

BANNER = "<h2>¡5.000€ en juego con Money Train 5!</h2><p>1086,40 € Jugador acaba de ganar</p>"
BUTTON = "<header><button data-test-id='balance-button'><span>100,00 €</span></button></header>"


@pytest.fixture()
def site_with(browser: Browser, tmp_path: Path):
    market = load_market("es")
    context = browser.new_context()

    def _make(body: str) -> BetssonSite:
        page = context.new_page()
        page.route(f"{market.origin}/**", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8",
                                                                       body=f"<html><body>{body}</body></html>"))
        page.goto(f"{market.origin}/casino")
        return BetssonSite(page, market, evidence_dir=tmp_path)

    yield _make
    context.close()


def test_reads_header_button_not_banner(site_with) -> None:
    reading = site_with(BANNER + BUTTON).read_balance(timeout_ms=5_000)
    assert reading.money is not None
    assert reading.money.amount == Decimal("100.00")
    assert reading.money.currency == "EUR"
    assert reading.currency_seen


def test_banner_only_is_inconclusive(site_with) -> None:
    reading = site_with(BANNER).read_balance(timeout_ms=2_000)
    assert reading.money is None
    assert reading.reason and reading.reason.startswith("inconclusive")


def test_two_balance_buttons_is_inconclusive(site_with) -> None:
    reading = site_with(BANNER + BUTTON + BUTTON).read_balance(timeout_ms=2_000)
    assert reading.money is None
