"""Prueba de humo del área A contra la web real.

    python -m betsson.site --session [--account funded|empty]   # recomendado: sesión iniciada a mano
    python -m betsson.site --no-login                           # sin cuenta: lobby, búsqueda y página del juego

--session se conecta por CDP al Chrome de `python -m betsson.site.login_asistido` (una persona inició sesión).
No cierra la sesión al terminar (se perdería): eso se hace con `login_asistido --logout` al final del día.
Sin --session ni --no-login se intenta el login automatizado (Betsson lo rechaza a día de hoy: ver handoff).
Evidencias en outputs/smoke/<market>/<fecha>/ (outputs/ no se sube a git). La traza se detiene en el login.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from PIL import Image
from playwright.sync_api import Playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from betsson.core import GameOpenError
from betsson.market import load_market
from betsson.market.schema import Market
from betsson.site import (
    BetssonSite,
    BrowserSession,
    MissingCredentialsError,
    SegmentedTrace,
    SessionUnavailable,
    SiteError,
)

VIEWPORT = {"width": 1366, "height": 768}
# Perfil propio del modo automatizado (un "dispositivo habitual"), FUERA del repo: nunca va a git.
PROFILES_ROOT = Path(__file__).resolve().parents[3]


def _run(site: BetssonSite, out: Path, args: argparse.Namespace) -> int:
    site.goto_lobby()
    site.screenshot("01_lobby")
    if not args.no_login:
        if not site.login():
            logging.error("login_ok FAIL: %s", site.last_login_error)
            return 1
        logging.info("login_ok: %s", site.login_note or "sesión iniciada (login automatizado)")
        site.screenshot("02_after_login")
        balance = site.read_balance()
        logging.info("saldo Betsson: %s | moneda vista: %s | %s", balance.money, balance.currency_seen,
                     balance.reason or "ok")
    if args.no_game:
        return 0
    game = site.open_game(args.slug, args.query)
    logging.info("proveedor (API Betsson): %s | modo: %s (%s)", game.info.provider, game.play_mode,
                 game.play_mode_reason)
    logging.info("evidencias del lanzamiento: %s", [p.name for p in game.evidence])
    Image.fromarray(game.capture()).save(out / "03_canvas.png")
    return 0


def _guarded(site: BetssonSite, out: Path, args: argparse.Namespace) -> int:
    try:
        return _run(site, out, args)
    except MissingCredentialsError as exc:
        logging.error("%s", exc)
        return 2
    except (SiteError, GameOpenError, PlaywrightTimeoutError) as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        site.screenshot("error")
        return 1


def _automated(p: Playwright, market: Market, out: Path, args: argparse.Namespace) -> int:
    profile = args.profile_dir or PROFILES_ROOT / f".chrome-profile-{market.id}"
    context = p.chromium.launch_persistent_context(
        user_data_dir=profile, channel="chrome", headless=args.headless, viewport=VIEWPORT,
        device_scale_factor=1, locale=market.locale, timezone_id=market.timezone,
    )
    trace = SegmentedTrace(context, out)  # se detiene del todo durante el login
    page = context.pages[0] if context.pages else context.new_page()
    site = BetssonSite(page, market, account=args.account, evidence_dir=out, trace=trace)
    try:
        return _guarded(site, out, args)
    finally:
        if site.is_logged_in():  # no dejar abierta la sesión de juego del regulador
            logging.info("cierre de sesión: %s", "ok" if site.logout() else "NO CONFIRMADO, revisar a mano")
        trace.close()
        context.close()


def _session(p: Playwright, market: Market, out: Path, args: argparse.Namespace) -> int:
    session = BrowserSession(market, args.account)
    _browser, page = session.connect(p)
    trace = SegmentedTrace(page.context, out)
    site = BetssonSite(page, market, account=args.account, login_mode="session", session=session,
                       evidence_dir=out, trace=trace)
    try:
        return _guarded(site, out, args)
    finally:
        trace.close()
        page.close()  # solo nuestra pestaña: Chrome y la sesión siguen vivos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default="es")
    parser.add_argument("--slug", default="big-bass-splash")
    parser.add_argument("--query", default=None, help="texto de búsqueda si no coincide con el slug")
    parser.add_argument("--account", choices=["funded", "empty"], default="funded",
                        help="funded: cuenta con saldo (S1); empty: cuenta sin saldo (S2)")
    parser.add_argument("--session", action="store_true", help="usar la sesión iniciada a mano (login asistido)")
    parser.add_argument("--no-login", action="store_true")
    parser.add_argument("--no-game", action="store_true", help="solo login y saldo, sin abrir el juego")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--profile-dir", type=Path, default=None,
                        help="perfil persistente del modo automatizado (por defecto ../.chrome-profile-<mercado>)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    market = load_market(args.market)
    out = Path("outputs/smoke") / market.id / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            status = _session(p, market, out, args) if args.session else _automated(p, market, out, args)
        except SessionUnavailable as exc:
            logging.error("login_ok inconclusive: %s", exc)
            status = 1
    logging.info("evidencias en %s", out)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
