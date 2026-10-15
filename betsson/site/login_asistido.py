"""Login asistido: una PERSONA inicia sesión en un Chrome normal y las ejecuciones lo reutilizan por CDP.

    python -m betsson.site.login_asistido --market es --account main     # abre Chrome; la persona inicia sesión
    python -m betsson.site.login_asistido --market es --account main --check    # comprueba y anota la hora
    python -m betsson.site.login_asistido --market es --account main --logout   # al final del día

La persona SOLO escribe usuario y contraseña y pulsa "Iniciar sesión". Todo lo demás (límites de sesión
del regulador, saldo, juego) lo hace el comprobador. Por defecto el script no se engancha a Chrome
mientras la persona escribe (para no interferir con el antibot); --wait vigila la sesión y termina sola.
"""
from __future__ import annotations

import argparse
import logging
import re
import time
from datetime import datetime

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from betsson.market import load_market
from betsson.site import selectors as sel
from betsson.site.betsson_site import BetssonSite
from betsson.site.session import BrowserSession, SessionUnavailable

ACCOUNT_ALIASES = {"main": "funded", "funded": "funded", "empty": "empty"}
WAIT_TIMEOUT_S = 10 * 60
WAIT_POLL_S = 15  # comprobación espaciada: cada una abre y cierra una pestaña propia

log = logging.getLogger("login_asistido")


def _check(session: BrowserSession, *, record: bool) -> bool:
    """Se conecta, comprueba la sesión en una pestaña propia y la cierra. Chrome sigue abierto."""
    with sync_playwright() as p:
        _browser, page = session.connect(p)
        try:
            site = BetssonSite(page, session.market, account=session.account, login_mode="session", session=session)
            ok = site.login()  # en modo "session" solo comprueba; nunca escribe credenciales
        finally:
            page.close()
    previous = session.logged_in_at
    if ok and record and (previous is None or previous.date() != datetime.now().date()):
        session.record_login()  # login nuevo: también olvida la sesión de juego anterior
    return ok


def _peek(session: BrowserSession) -> bool:
    """Solo MIRA las pestañas abiertas (sin navegar ni abrir ninguna, para no robar el foco a quien escribe)."""
    market = session.market
    labels = "|".join(re.escape(label) for label in market.expected_texts.balance_labels)
    balance_button = re.compile(rf"^\s*({labels})\s*$", re.IGNORECASE)
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(session.cdp_url)
        for context in browser.contexts:
            for page in context.pages:
                if not page.url.startswith(market.origin):
                    continue
                try:
                    logged = page.get_by_role("button", name=balance_button).filter(visible=True).count() > 0
                    offered = page.get_by_text(sel.LOGIN_OPEN).filter(visible=True).count() > 0
                except PlaywrightError:  # la pestaña está navegando (p. ej. justo al entrar): se mira en la siguiente
                    continue
                if logged and not offered:
                    return True
    return False


def _logout(session: BrowserSession) -> bool:
    with sync_playwright() as p:
        _browser, page = session.connect(p)
        try:
            site = BetssonSite(page, session.market, account=session.account, login_mode="session", session=session)
            site.goto_lobby()
            ok = site.logout()
        finally:
            page.close()
    if ok:
        session.clear()
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default="es")
    parser.add_argument("--account", choices=sorted(ACCOUNT_ALIASES), default="main")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="comprueba que la sesión está iniciada y anota la hora")
    mode.add_argument("--wait", action="store_true", help="abre Chrome y espera a que la persona inicie sesión")
    mode.add_argument("--logout", action="store_true", help="cierra la sesión (al final del día)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    session = BrowserSession(load_market(args.market), ACCOUNT_ALIASES[args.account])
    try:
        if args.check:
            ok = _check(session, record=True)
            log.info("sesión %s", "VÁLIDA" if ok else "AUSENTE O CADUCADA: repetir el login asistido")
            return 0 if ok else 1
        if args.logout:
            ok = _logout(session)
            log.info("cierre de sesión %s", "hecho" if ok else "NO CONFIRMADO: ciérrala a mano en la ventana")
            return 0 if ok else 1

        if session.is_listening():
            log.info("ya hay un Chrome de esta cuenta en el puerto %d (perfil %s)", session.port, session.profile_dir)
        else:
            session.launch_chrome()
            log.info("Chrome abierto (perfil %s, puerto %d)", session.profile_dir, session.port)
        log.info(">>> En esa ventana: pulsa 'Iniciar sesión', escribe usuario y contraseña de la cuenta '%s' y entra.",
                 args.account)
        log.info(">>> NO toques el diálogo de límites de sesión: lo gestiona el comprobador. No cierres la ventana.")
        if not args.wait:
            log.info(">>> Cuando hayas entrado: python -m betsson.site.login_asistido --market %s --account %s --check",
                     args.market, args.account)
            return 0
        deadline = time.monotonic() + WAIT_TIMEOUT_S
        while time.monotonic() < deadline:
            time.sleep(WAIT_POLL_S)  # ritmo humano: no vigilar en bucle apretado
            if session.is_listening() and _peek(session):
                session.record_login()
                log.info("sesión VÁLIDA: puedes lanzar las ejecuciones (Chrome se queda abierto)")
                return 0
        log.error("no se detectó la sesión en %d min", WAIT_TIMEOUT_S // 60)
        return 1
    except SessionUnavailable as exc:
        log.error("%s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
