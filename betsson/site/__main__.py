"""Prueba de humo del área A contra la web real.

    python -m betsson.site --market es --slug big-bass-splash [--no-login]

Lobby -> cookies -> login (si hay credenciales en .env) -> saldo -> abrir juego -> captura del canvas.
Evidencias en outputs/smoke/<market>/ (outputs/ no se sube a git). La traza se pausa durante el login.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from betsson.market import load_market
from betsson.site import BetssonSite, ChunkedTrace, MissingCredentialsError, SiteError

VIEWPORT = {"width": 1366, "height": 768}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default="es")
    parser.add_argument("--slug", default="big-bass-splash")
    parser.add_argument("--query", default=None, help="texto de búsqueda si no coincide con el slug")
    parser.add_argument("--no-login", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    market = load_market(args.market)
    out = Path("outputs/smoke") / market.id / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=args.headless)
        context = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=1, locale=market.locale, timezone_id=market.timezone
        )
        context.tracing.start(screenshots=True, snapshots=True)
        trace = ChunkedTrace(context, out)
        page = context.new_page()
        site = BetssonSite(page, market, trace=trace)
        status = 0
        try:
            site.goto_lobby()
            page.screenshot(path=out / "01_lobby.png")
            if not args.no_login:
                site.login()
                page.screenshot(path=out / "02_after_login.png")
                logging.info("saldo Betsson: %s", site.read_balance())
            game = site.open_game(args.slug, args.query)
            logging.info("iframe: %s | proveedor (API Betsson): %s", game.iframe_url[:120], game.info.provider)
            game.canvas.screenshot(path=out / "03_canvas.png")
            page.screenshot(path=out / "04_game_page.png")
        except MissingCredentialsError as exc:
            logging.error("%s", exc)
            status = 2
        except (SiteError, PlaywrightTimeoutError) as exc:
            logging.error("%s: %s", type(exc).__name__, exc)
            page.screenshot(path=out / "error.png")
            status = 1
        finally:
            context.tracing.stop(path=out / "trace-final.zip")
            browser.close()
        logging.info("evidencias en %s", out)
        return status


if __name__ == "__main__":
    raise SystemExit(main())
