"""BetssonSite: la web de Betsson vista como un jugador (DOM legítimo de Betsson).

cookies · login · saldo de Betsson · buscar y abrir un juego en Real Play -> iframe y canvas.
No conoce ningún proveedor: el proveedor del juego lo dice la API pública de Betsson.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import ElementHandle, Frame, Locator, Page, Response
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from betsson.market.money import Money, MoneyParseError, detect_currency, parse_money
from betsson.market.schema import Market
from betsson.site import selectors as sel
from betsson.site.credentials import Credentials, credentials_for
from betsson.site.pacing import Pacer
from betsson.site.tracing import NoTrace, TraceControl, trace_paused

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30_000
GAME_LAUNCH_TIMEOUT_MS = 60_000
_FRAME_POLL_MS = 1_000  # tope de cada espera a un evento de frame, no una pausa fija

# Cabeceras que la web manda a su API (marketcode, brandid, x-obg-*). Se copian de sus propias peticiones.
_API_HEADER_PREFIXES = ("marketcode", "brandid", "x-obg-", "accept-language")

class SiteError(RuntimeError):
    """Fallo de integración con la web de Betsson."""


class LoginError(SiteError):
    pass


class GameNotFoundError(SiteError):
    pass


class GameLaunchError(SiteError):
    pass


class BalanceNotFoundError(SiteError):
    pass


@dataclass(frozen=True)
class GameInfo:
    game_id: str
    slug: str
    name: str
    provider: str
    primary_type: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "GameInfo":
        return cls(
            game_id=str(data["id"]),
            slug=str(data["slug"]),
            name=str(data.get("name") or data["slug"]),
            provider=str(data.get("provider") or "unknown"),
            primary_type=data.get("primaryType"),
        )


@dataclass(frozen=True)
class GameHandle:
    """Lo que necesita el área B para "mirar" el juego."""

    info: GameInfo
    iframe: ElementHandle  # el <iframe> del proveedor en la página de Betsson
    frame: Frame  # el frame que contiene el canvas (puede ir anidado dentro del iframe)
    canvas: Locator  # el canvas del juego
    iframe_url: str


class BetssonSite:
    def __init__(
        self,
        page: Page,
        market: Market,
        *,
        trace: TraceControl | None = None,
        pacer: Pacer | None = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.page = page
        self.market = market
        self._trace = trace or NoTrace()
        self._pacer = pacer or Pacer()
        self._games: dict[str, GameInfo] = {}
        self._api_headers: dict[str, str] = {}
        self.cookies_rejected = False
        page.set_default_timeout(timeout_ms)
        page.on("response", self._capture_game_api)
        page.add_locator_handler(page.locator(sel.COOKIE_BANNER), self._reject_cookies)

    # ------------------------------------------------------------------ navegación

    def _goto(self, path: str) -> None:
        self._pacer.wait_turn()
        # "commit" y después una señal concreta: DOMContentLoaded tarda mucho con tanto script de terceros.
        self.page.goto(self.market.origin + path, wait_until="commit", timeout=GAME_LAUNCH_TIMEOUT_MS)

    def goto_lobby(self) -> None:
        self._goto(self.market.site.casino_path)
        self.page.locator(sel.GAME_THUMBNAIL).first.wait_for(state="visible", timeout=GAME_LAUNCH_TIMEOUT_MS)

    # ------------------------------------------------------------------ cookies

    def _reject_cookies(self, _banner: Locator | None = None) -> None:
        """Rechaza todas las cookies opcionales. Se dispara solo cuando aparece el banner."""
        direct = self.page.locator(sel.COOKIE_REJECT_DIRECT)
        if direct.is_visible():
            direct.click()
        else:
            self.page.locator(sel.COOKIE_SETTINGS_BUTTON).click()
            self.page.locator(sel.COOKIE_REFUSE_ALL).filter(visible=True).first.click()
        self.page.locator(sel.COOKIE_BANNER).wait_for(state="hidden", timeout=10_000)
        self.cookies_rejected = True
        log.info("cookies opcionales rechazadas")

    # ------------------------------------------------------------------ login

    def is_logged_in(self) -> bool:
        return self._find_balance_locator() is not None

    def login(self, credentials: Credentials | None = None, *, insufficient_funds: bool = False) -> None:
        """Inicia sesión con la cuenta de prueba del mercado. La traza se pausa y los campos se tapan."""
        creds = credentials or credentials_for(self.market, insufficient_funds=insufficient_funds)
        if "/inicio" not in self.page.url:
            if not self.page.url.startswith(self.market.origin):
                self.goto_lobby()
            self._pacer.wait_turn()
            self.page.get_by_text(sel.LOGIN_OPEN).filter(visible=True).first.click()
        username = self.page.locator(sel.LOGIN_USERNAME)
        password = self.page.locator(sel.LOGIN_PASSWORD)
        username.wait_for(state="visible")
        self._mask(username)
        self._mask(password)

        with trace_paused(self._trace):
            username.fill(creds.username)
            password.fill(creds.password)
            self.page.locator(sel.LOGIN_SUBMIT).click()
            # Seguimos en pausa hasta que el formulario desaparece: sus valores van en las instantáneas del DOM.
            try:
                password.wait_for(state="detached", timeout=DEFAULT_TIMEOUT_MS)
            except PlaywrightTimeoutError as exc:
                password.fill("")
                username.fill("")
                raise LoginError(f"login rechazado o sin respuesta en {self.market.id}: {self._visible_error()}") from exc
        log.info("sesión iniciada en %s", self.market.id)

    def _mask(self, field: Locator) -> None:
        """Tapa el campo en capturas y vídeo (se aplica antes de escribir)."""
        field.evaluate(
            "e => { e.style.setProperty('filter', 'blur(6px)', 'important');"
            " e.style.setProperty('-webkit-text-security', 'disc', 'important'); }"
        )

    def _visible_error(self) -> str:
        alert = self.page.locator("[role='alert'], [class*='error' i]").filter(visible=True)
        if alert.count():
            return alert.first.inner_text().strip()[:200]
        return "sin mensaje visible"

    # ------------------------------------------------------------------ saldo

    def _find_balance_locator(self) -> Locator | None:
        for css in sel.BALANCE_CANDIDATES:
            loc = self.page.locator(css).filter(visible=True)
            for i in range(loc.count()):
                text = loc.nth(i).inner_text().strip()
                if not text:
                    continue
                # Saldo = importe legible CON la moneda del mercado visible (no la de por defecto).
                if detect_currency(text, self.market) != self.market.currency_code:
                    continue
                try:
                    parse_money(text, self.market, require_currency=True)
                except MoneyParseError:
                    continue
                return loc.nth(i)
        return None

    def read_balance(self, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Money:
        """Saldo de Betsson visible en la cabecera, leído con parse_money del mercado."""
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            loc = self._find_balance_locator()
            if loc is not None:
                return parse_money(loc.inner_text(), self.market)
            try:
                self.page.locator(sel.BALANCE_CANDIDATES[0]).first.wait_for(state="visible", timeout=_FRAME_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        raise BalanceNotFoundError(f"no se ve el saldo de Betsson en {self.market.id}")

    # ------------------------------------------------------------------ juegos

    def _capture_game_api(self, response: Response) -> None:
        """Guarda los juegos y las cabeceras de mercado que la propia web pide a su API."""
        if sel.GAME_API_FRAGMENT not in response.url or response.status != 200:
            return
        try:
            if not self._api_headers:
                self._api_headers = {
                    k: v for k, v in response.request.headers.items() if k.lower().startswith(_API_HEADER_PREFIXES)
                }
            data = response.json()
        except Exception:  # respuestas que no son JSON o ya liberadas: no son de juego
            return
        if isinstance(data, dict) and "id" in data and "slug" in data:
            info = GameInfo.from_api(data)
            self._games[info.game_id] = info

    def game_info_by_slug(self, slug: str, timeout_ms: int = 10_000) -> GameInfo | None:
        """Info del juego que la web ya pidió a su API (lo hace al pintar sus tarjetas y su página)."""
        deadline = time.monotonic() + timeout_ms / 1000
        while True:
            for info in self._games.values():
                if info.slug == slug:
                    return info
            if time.monotonic() >= deadline:
                return None
            try:
                self.page.wait_for_event(
                    "response", predicate=lambda r: sel.GAME_API_FRAGMENT in r.url, timeout=_FRAME_POLL_MS
                )
            except PlaywrightTimeoutError:
                pass

    def _open_search(self, query: str, attempts: int = 3) -> None:
        """Abre el buscador. Si la página aún no está hidratada el clic no hace nada: se reintenta."""
        box = self.page.get_by_placeholder(sel.SEARCH_INPUT_PLACEHOLDER).filter(visible=True).first
        for attempt in range(1, attempts + 1):
            trigger = self.page.locator(sel.SEARCH_OPEN_TRIGGER).filter(visible=True)
            if not trigger.count():
                trigger = self.page.get_by_text(sel.SEARCH_OPEN).filter(visible=True)
            trigger.first.click()
            try:
                box.wait_for(state="visible", timeout=5_000)
                break
            except PlaywrightTimeoutError:
                if attempt == attempts:
                    raise GameNotFoundError("el buscador del casino no se abre") from None
        box.fill(query)

    def find_game(self, slug: str, query: str | None = None) -> Locator:
        """Busca el juego con el buscador del casino, como un jugador. Devuelve el enlace del resultado."""
        query = query or self.market.site.search_terms.get(slug) or slug.replace("-", " ")
        if not self.page.locator(sel.GAME_THUMBNAIL).count():
            self.goto_lobby()
        self._open_search(query)
        modal = self.page.locator(sel.SEARCH_MODAL)
        link = modal.locator(f"{sel.SEARCH_RESULT_LINK}[href$='/{slug}']")
        try:
            link.first.wait_for(state="visible")
        except PlaywrightTimeoutError:
            found = modal.locator(sel.SEARCH_RESULT_LINK).evaluate_all("as => as.map(a => a.getAttribute('href'))")
            raise GameNotFoundError(f"'{slug}' no aparece al buscar '{query}' en {self.market.id}: {found}") from None
        return link.first

    def open_game(self, slug: str, query: str | None = None) -> GameHandle:
        """Abre el juego en Real Play (requiere sesión) y devuelve su iframe y su canvas."""
        link = self.find_game(slug, query)
        self._pacer.wait_turn()
        link.click()
        self.page.wait_for_url(f"**/{slug}**")
        info = self.game_info_by_slug(slug) or GameInfo(slug, slug, slug, "unknown", None)
        if self.page.get_by_text(sel.LOGIN_TO_PLAY).filter(visible=True).count():
            raise GameLaunchError(f"'{slug}' pide iniciar sesión: llama a login() antes de open_game()")
        iframe, iframe_url = self._wait_game_iframe()
        frame, canvas = self._wait_canvas(iframe.content_frame())
        log.info("juego %s (%s) abierto", info.slug, info.provider)
        return GameHandle(info=info, iframe=iframe, frame=frame, canvas=canvas, iframe_url=iframe_url)

    def _is_game_frame(self, frame: Frame) -> ElementHandle | None:
        if frame == self.page.main_frame or frame.parent_frame != self.page.main_frame:
            return None
        host = urlparse(frame.url).hostname or ""
        if not host or any(bad in host for bad in sel.NON_GAME_IFRAME_HOSTS):
            return None
        element = frame.frame_element()
        box = element.bounding_box()
        min_w, min_h = sel.GAME_IFRAME_MIN_SIZE
        if box and box["width"] >= min_w and box["height"] >= min_h:
            return element
        return None

    def _wait_game_iframe(self) -> tuple[ElementHandle, str]:
        deadline = time.monotonic() + GAME_LAUNCH_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            for frame in self.page.frames:
                element = self._is_game_frame(frame)
                if element is not None:
                    return element, frame.url
            try:
                self.page.wait_for_event("framenavigated", timeout=_FRAME_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        raise GameLaunchError("no aparece el iframe del juego")

    def _wait_canvas(self, root: Frame | None) -> tuple[Frame, Locator]:
        if root is None:
            raise GameLaunchError("el iframe del juego no tiene documento")
        deadline = time.monotonic() + GAME_LAUNCH_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            for frame in [root, *self._descendants(root)]:
                canvas = frame.locator("canvas").filter(visible=True)
                if canvas.count():
                    return frame, canvas.first
            try:
                root.locator("canvas").first.wait_for(state="visible", timeout=_FRAME_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        raise GameLaunchError("el juego no muestra ningún canvas")

    @staticmethod
    def _descendants(frame: Frame) -> list[Frame]:
        out: list[Frame] = []
        for child in frame.child_frames:
            out.append(child)
            out.extend(BetssonSite._descendants(child))
        return out
