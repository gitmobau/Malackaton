"""read_balance solo lee el botón de saldo de la cabecera: nunca un banner con "€".

Regresión del 15-oct: con sesión, leyó 5000,00 EUR del banner "¡5.000€ en juego con Money Train 5!".
Sin red: la página se sirve en local con route, con el mismo data-test-id que la web real.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest
from playwright.sync_api import Browser

from betsson.market import load_market
from betsson.site import BetssonSite

BANNER = "<h2>¡5.000€ en juego con Money Train 5!</h2><p>1086,40 € Jugador acaba de ganar</p>"
BUTTON = "<header><button data-test-id='balance-button'><span>100,00 €</span></button></header>"
# Página del juego: "Saldo ▾" abre un resumen; el total es user-summary-balance (no bonus/bloqueado/retirable).
IN_GAME = """<header><button data-test-id='in-game-balance-button'
  onclick="document.getElementById('sum').hidden = !document.getElementById('sum').hidden">Saldo</button></header>
<section id='sum' hidden>
  <span data-test-id='user-summary-balance'>12,50 €</span>
  <span data-test-id='user-summary-bonus'>5,00 €</span>
  <span data-test-id='user-summary-withdrawable'>7,50 €</span>
</section>"""


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


def test_in_game_header_opens_summary_and_reads_total(site_with) -> None:
    site = site_with(BANNER + IN_GAME)
    reading = site.read_balance(timeout_ms=8_000)
    assert reading.money is not None
    assert reading.money.amount == Decimal("12.50")
    assert site.page.locator("#sum").is_hidden()  # el desplegable se cierra para no tapar el juego
    assert site.is_logged_in()


# Página del juego real (15-oct): la primera fila del resumen muestra el NOMBRE del titular junto al total.
HOLDER = "TESTJugador Ejemplo"
IN_GAME_WITH_HOLDER = f"""<header><button data-test-id='in-game-balance-button'
  onclick="document.getElementById('sum').hidden = !document.getElementById('sum').hidden">Saldo</button></header>
<main><div class='overlay'><div class='panel'>
<section id='sum' hidden style='font: 20px sans-serif; padding: 12px; width: 420px'>
  <div style='display: flex; justify-content: space-between'>
    <span>{HOLDER}</span><span data-test-id='user-summary-balance'>12,50 €</span>
  </div>
  <div>Bono <span data-test-id='user-summary-bonus'>5,00 €</span></div>
  <div>Disponible para retirar <span data-test-id='user-summary-withdrawable'>7,50 €</span></div>
</section></div></div></main>"""


def _ocr(path: Path) -> list[str]:
    import cv2

    from betsson.vision.ocr import read_text

    return [box.text for box in read_text(cv2.imread(str(path)), upscale=2.0)]


def test_balance_evidence_shows_only_the_amount(site_with) -> None:
    """Privacidad: la captura del saldo solo puede contener el importe, nunca el nombre del titular."""
    reading = site_with(IN_GAME_WITH_HOLDER).read_balance(timeout_ms=8_000)
    assert reading.money is not None and reading.money.amount == Decimal("12.50")
    assert reading.evidence_path is not None
    texts = _ocr(reading.evidence_path)
    assert texts, "la captura del saldo debe mostrar el importe"
    for text in texts:  # cada texto leído es el importe (cifras, separadores y moneda), nada más
        assert re.fullmatch(r"[\d.,\s€EUR]+", text), f"texto ajeno al importe en la captura del saldo: {text!r}"


def test_page_screenshot_hides_open_balance_summary(site_with) -> None:
    """Si alguien captura la página con el resumen abierto, el titular queda tapado."""
    site = site_with(IN_GAME_WITH_HOLDER)
    site.page.locator("[data-test-id='in-game-balance-button']").click()
    path = site.screenshot("con_resumen_abierto")
    joined = " ".join(_ocr(path)).upper()
    assert "SALDO" in joined, "control: el OCR debe leer la cabecera, si no la prueba no demuestra nada"
    assert "TESTJUGADOR" not in joined and "EJEMPLO" not in joined
