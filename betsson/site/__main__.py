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

from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from betsson.market import load_market
from betsson.core import GameOpenError
from betsson.site import BetssonSite, MissingCredentialsError, SegmentedTrace, SiteError

VIEWPORT = {"width": 1366, "height": 768}
# Perfil propio del comprobador (un "dispositivo habitual"), FUERA del repo: nunca va a git.
PROFILES_ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default="es")
    parser.add_argument("--slug", default="big-bass-splash")
    parser.add_argument("--query", default=None, help="texto de búsqueda si no coincide con el slug")
    parser.add_argument("--no-login", action="store_true")
    parser.add_argument("--account", choices=["funded", "empty"], default="funded",
                        help="funded: cuenta con saldo (S1); empty: cuenta sin saldo (S2)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-game", action="store_true", help="solo login y saldo, sin abrir el juego")
    parser.add_argument("--profile-dir", type=Path, default=None,
                        help="perfil persistente de Chrome (por defecto ../.chrome-profile-<mercado>)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    market = load_market(args.market)
    out = Path("outputs/smoke") / market.id / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        profile = args.profile_dir or PROFILES_ROOT / f".chrome-profile-{market.id}"
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile,
            channel="chrome",
            headless=args.headless,
            viewport=VIEWPORT,
            device_scale_factor=1,
            locale=market.locale,
            timezone_id=market.timezone,
        )
        trace = SegmentedTrace(context, out)  # se detiene del todo durante el login
        page = context.pages[0] if context.pages else context.new_page()
        site = BetssonSite(page, market, account=args.account, evidence_dir=out, trace=trace)
        status = 0
        logged_in = False
        try:
            site.goto_lobby()
            page.screenshot(path=out / "01_lobby.png")
            if not args.no_login:
                if not site.login():
                    logging.error("login rechazado: %s", site.last_login_error)
                    return 1
                logged_in = True
                site.screenshot("02_after_login")
                balance = site.read_balance()
                logging.info("saldo Betsson: %s | moneda vista: %s | %s", balance.money, balance.currency_seen,
                             balance.reason or "ok")
            if args.no_game:
                return status
            game = site.open_game(args.slug, args.query)
            logging.info("proveedor (API Betsson): %s | modo: %s (%s)", game.info.provider, game.play_mode,
                         game.play_mode_reason)
            logging.info("iframe: %s", game.iframe_url[:120])
            Image.fromarray(game.capture()).save(out / "03_canvas.png")
        except MissingCredentialsError as exc:
            logging.error("%s", exc)
            status = 2
        except (SiteError, GameOpenError, PlaywrightTimeoutError) as exc:
            logging.error("%s: %s", type(exc).__name__, exc)
            site.screenshot("error")
            status = 1
        finally:
            if logged_in:  # no dejar abierta la sesión de juego del regulador
                logging.info("cierre de sesión: %s", "ok" if site.logout() else "NO CONFIRMADO, revisar a mano")
            trace.close()
            context.close()
        logging.info("evidencias en %s", out)
        return status


if __name__ == "__main__":
    raise SystemExit(main())
