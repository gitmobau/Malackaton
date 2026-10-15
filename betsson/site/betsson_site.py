"""BetssonSite: la web de Betsson vista como un jugador (DOM legítimo de Betsson).

cookies · login · saldo de Betsson · buscar y abrir un juego en Real Play -> iframe y canvas.
Cumple el Protocol betsson.core.BetssonSite. No conoce ningún proveedor: el proveedor del
juego lo dice la API pública de Betsson.
"""
from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, urlparse

import numpy as np
from PIL import Image
from playwright.sync_api import ElementHandle, Frame, Locator, Page, Response
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from betsson.core import GameOpenError, PlayMode, Reading
from betsson.market.money import MoneyParseError, detect_currency, parse_money
from betsson.market.schema import Market
from betsson.site import selectors as sel
from betsson.site.credentials import Credentials, credentials_for
from betsson.site.pacing import Pacer
from betsson.site.tracing import NoTrace, TraceControl, trace_paused

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MS = 30_000
GAME_LAUNCH_TIMEOUT_MS = 60_000
_POLL_MS = 1_000  # tope de cada espera a un evento o elemento, no una pausa fija
BALANCE_STABLE_WINDOW_MS = 3_000  # el saldo es estable si su texto no cambia en esta ventana
BALANCE_SETTLE_TIMEOUT_MS = 30_000  # si sigue cambiando pasado esto: "saldo no estable" (no concluyente)

# Cabeceras que la web manda a su API (marketcode, brandid, x-obg-*). Se copian de sus propias peticiones.
_API_HEADER_PREFIXES = ("marketcode", "brandid", "x-obg-", "accept-language")

# Pistas genéricas de modo de juego en las URL (página de Betsson e iframe del proveedor).
_DEMO_TOKENS = {"demo", "fun", "free", "practice", "playforfun", "freeplay"}
_REAL_TOKENS = {"real", "realmoney", "real_money", "money", "cash"}

# Cuenta de prueba: "funded" (con saldo, S1) o "empty" (sin saldo, S2: BETSSON_<MERCADO>_EMPTY_*).
Account = Literal["funded", "empty"]


class SiteError(RuntimeError):
    """Fallo de integración con la web de Betsson."""


class LoginError(SiteError):
    pass


class GameNotFoundError(SiteError, GameOpenError):
    pass


class GameLaunchError(SiteError, GameOpenError):
    pass


@dataclass(frozen=True)
class GameInfo:
    game_id: str
    slug: str
    name: str
    provider: str
    primary_type: str | None
    provider_source: Literal["betsson_api", "fallback"] = "betsson_api"

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GameInfo:
        return cls(
            game_id=str(data["id"]),
            slug=str(data["slug"]),
            name=str(data.get("name") or data["slug"]),
            provider=str(data.get("provider") or "unknown"),
            primary_type=data.get("primaryType"),
        )


@dataclass(frozen=True)
class GameHandle:
    """Juego abierto (cumple betsson.core.GameHandle). info/iframe/frame/canvas son para el área B."""

    info: GameInfo
    iframe: ElementHandle  # el <iframe> del proveedor en la página de Betsson
    frame: Frame  # el frame que contiene el canvas (puede ir anidado dentro del iframe)
    canvas: Locator  # el canvas del juego
    iframe_url: str
    play_mode: PlayMode
    play_mode_reason: str = ""
    evidence: tuple[Path, ...] = field(default_factory=tuple)

    def capture(self) -> np.ndarray:
        """Captura actual del canvas del juego, en RGB."""
        png = self.canvas.screenshot()
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


class BetssonSite:
    def __init__(
        self,
        page: Page,
        market: Market,
        *,
        account: Account = "funded",
        evidence_dir: Path | None = None,
        trace: TraceControl | None = None,
        pacer: Pacer | None = None,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ) -> None:
        self.page = page
        self.market = market
        self.account = account
        self.evidence_dir = evidence_dir or Path("outputs") / "site" / market.id
        self.last_login_error: str | None = None
        self._trace = trace or NoTrace()
        self._pacer = pacer or Pacer()
        self._games: dict[str, GameInfo] = {}
        self._api_headers: dict[str, str] = {}
        self.cookies_rejected = False
        page.set_default_timeout(timeout_ms)
        page.on("response", self._capture_game_api)
        page.add_locator_handler(page.locator(sel.COOKIE_BANNER), self._reject_cookies)

    # ------------------------------------------------------------------ evidencias

    def screenshot(self, name: str) -> Path:
        """Captura de la página con los campos del login tapados."""
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f"{name}.png"
        self.page.screenshot(
            path=path, mask=[self.page.locator(sel.LOGIN_USERNAME), self.page.locator(sel.LOGIN_PASSWORD)]
        )
        return path

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
        """Hay sesión si ya no se ofrece "Iniciar sesión" en la cabecera y se ve el acceso al saldo."""
        login_offered = self.page.get_by_text(sel.LOGIN_OPEN).filter(visible=True).count() > 0
        return not login_offered and (self._balance_toggle() is not None or self._find_balance_locator() is not None)

    def login(self, credentials: Credentials | None = None) -> bool:
        """Inicia sesión con la cuenta del mercado (traza pausada, campos tapados). False si Betsson la rechaza.

        Faltar las variables de entorno no es un rechazo: lanza MissingCredentialsError.
        """
        creds = credentials or credentials_for(self.market, insufficient_funds=self.account == "empty")
        self.last_login_error = None
        if not self.page.url.startswith(self.market.origin):
            self.goto_lobby()
        if self.page.locator(sel.LOGIN_PASSWORD).filter(visible=True).count() == 0:
            self._pacer.wait_turn()
            self.page.get_by_text(sel.LOGIN_OPEN).filter(visible=True).first.click()
        username = self.page.locator(sel.LOGIN_USERNAME)
        password = self.page.locator(sel.LOGIN_PASSWORD)
        username.wait_for(state="visible")
        self._mask(username)
        self._mask(password)

        # La traza solo se reanuda con el formulario fuera del DOM o con los campos vacíos, falle lo que falle.
        with trace_paused(self._trace):
            try:
                username.fill(creds.username)
                password.fill(creds.password)
                self.page.locator(sel.LOGIN_SUBMIT).click()
                password.wait_for(state="detached", timeout=DEFAULT_TIMEOUT_MS)
            except PlaywrightError:
                error = self._visible_error().replace(creds.username, "<usuario>")
                self.last_login_error = f"login rechazado o sin respuesta en {self.market.id}: {error}"
            finally:
                self._clear_fields(username, password)
        if self.last_login_error:
            log.warning("%s", self.last_login_error)
            self.screenshot("login_rejected")
            return False
        log.info("sesión iniciada en %s (cuenta %s)", self.market.id, self.account)
        return True

    @staticmethod
    def _clear_fields(*fields: Locator) -> None:
        """Vacía los campos que sigan en la página. Si ya no están (login correcto), no hay nada que vaciar."""
        for fld in fields:
            try:
                if fld.count():
                    fld.fill("", timeout=2_000)
            except PlaywrightError:
                log.warning("no se pudo vaciar un campo del login")

    def _mask(self, fld: Locator) -> None:
        """Tapa el campo en capturas y vídeo (se aplica antes de escribir)."""
        fld.evaluate(
            "e => { e.style.setProperty('filter', 'blur(6px)', 'important');"
            " e.style.setProperty('-webkit-text-security', 'disc', 'important'); }"
        )

    def _visible_error(self) -> str:
        alert = self.page.locator("[role='alert'], [class*='error' i]").filter(visible=True)
        texts = [t.strip() for t in alert.all_inner_texts() if t.strip()]
        return " | ".join(texts)[:300] if texts else "sin mensaje visible"

    # ------------------------------------------------------------------ saldo

    def _balance_label_regex(self) -> re.Pattern[str]:
        labels = "|".join(re.escape(label) for label in self.market.expected_texts.balance_labels)
        return re.compile(rf"^\s*({labels})\s*$", re.IGNORECASE)

    def _balance_toggle(self) -> Locator | None:
        """Botón de la cabecera que muestra el saldo ("Saldo ▾" en es): su texto es una etiqueta de saldo."""
        toggle = self.page.get_by_role("button", name=self._balance_label_regex()).filter(visible=True)
        return toggle.first if toggle.count() else None

    def _money_text_regex(self) -> re.Pattern[str]:
        symbols = "|".join(re.escape(s) for s in self.market.currency.symbols)
        number = r"-?\d[\d.,   ]*"
        return re.compile(rf"({symbols})\s*{number}|{number}\s*({symbols})", re.IGNORECASE)

    def _find_balance_locator(self) -> Locator | None:
        """Elemento visible con un importe legible y la moneda del mercado a la vista."""
        candidates = [self.page.locator(css) for css in sel.BALANCE_CANDIDATES]
        candidates.append(self.page.get_by_text(self._money_text_regex()))  # p. ej. dentro del desplegable de "Saldo"
        for loc in candidates:
            loc = loc.filter(visible=True)
            for i in range(min(loc.count(), 20)):
                try:
                    text = loc.nth(i).inner_text().strip()
                except PlaywrightError:
                    continue
                if not text or len(text) > 80 or detect_currency(text, self.market) != self.market.currency_code:
                    continue
                try:
                    parse_money(text, self.market, require_currency=True)
                except MoneyParseError:
                    continue
                return loc.nth(i)
        return None

    def read_balance(self, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Reading:
        """Saldo de Betsson leído del DOM, con captura. Si no se puede leer: Reading no concluyente, sin excepción."""
        deadline = time.monotonic() + timeout_ms / 1000
        toggled = False
        while time.monotonic() < deadline:
            loc = self._find_balance_locator()
            if loc is not None:
                return self._balance_reading(loc)
            toggle = self._balance_toggle()
            if toggle is not None and not toggled:
                toggle.click()
                toggled = True
                continue
            try:
                self.page.get_by_text(self._money_text_regex()).first.wait_for(state="visible", timeout=_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        return Reading(
            reason=f"saldo de Betsson no visible en {self.market.id}", evidence_path=self.screenshot("betsson_balance")
        )

    def _balance_reading(self, loc: Locator) -> Reading:
        """Lee el saldo cuando deja de cambiar: el monedero puede tardar en reflejar la liquidación de una tirada."""
        deadline = time.monotonic() + BALANCE_SETTLE_TIMEOUT_MS / 1000
        try:
            text = loc.inner_text().strip()
            while True:
                if time.monotonic() >= deadline:
                    return Reading(
                        raw_text=text, reason="saldo no estable", evidence_path=self.screenshot("betsson_balance")
                    )
                handle = loc.element_handle()
                try:  # señal: el texto del elemento cambia dentro de la ventana; si no cambia, está estable
                    self.page.wait_for_function(
                        "([el, t]) => !el.isConnected || el.innerText.trim() !== t",
                        arg=[handle, text],
                        timeout=BALANCE_STABLE_WINDOW_MS,
                    )
                except PlaywrightTimeoutError:
                    break
                text = loc.inner_text().strip()
            money = parse_money(text, self.market, require_currency=True)
        except (PlaywrightError, MoneyParseError) as exc:
            return Reading(reason=f"saldo de Betsson ilegible: {exc}", evidence_path=self.screenshot("betsson_balance"))
        return Reading(
            raw_text=text,
            money=money,
            currency_seen=True,
            confidence=1.0,
            evidence_path=self.screenshot("betsson_balance"),
        )

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
                    "response", predicate=lambda r: sel.GAME_API_FRAGMENT in r.url, timeout=_POLL_MS
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
            if not trigger.count():
                raise GameNotFoundError("no hay buscador de juegos en esta página")
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
        on_lobby = urlparse(self.page.url).path.rstrip("/").endswith(self.market.site.casino_path.rstrip("/"))
        if not on_lobby or not self.page.locator(sel.SEARCH_OPEN_TRIGGER).count():
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
        """Abre el juego en Real Play y devuelve su iframe y su canvas. Lanza GameOpenError si no se puede."""
        link = self.find_game(slug, query)
        self._pacer.wait_turn()
        link.click()
        self.page.wait_for_url(f"**/{slug}**")
        info = self.game_info_by_slug(slug)
        if info is None:
            log.warning("la API de Betsson no dio la info de '%s': proveedor desconocido", slug)
            info = GameInfo(slug, slug, slug, "unknown", None, provider_source="fallback")
        evidence: list[Path] = []
        iframe, launch_notes = self._launch(evidence)
        frame, canvas = self._wait_canvas(iframe)
        play_mode, reason = self._play_mode(frame.url or iframe.content_frame().url, launch_notes)
        evidence.append(self.screenshot("game_opened"))
        log.info("juego %s (%s) abierto; modo %s (%s)", info.slug, info.provider, play_mode, reason)
        return GameHandle(
            info=info,
            iframe=iframe,
            frame=frame,
            canvas=canvas,
            iframe_url=frame.url,
            play_mode=play_mode,
            play_mode_reason=reason,
            evidence=tuple(evidence),
        )

    # -- lanzamiento: botón "Jugar", diálogo de límites del regulador e iframe -------------

    def _launch(self, evidence: list[Path]) -> tuple[ElementHandle, set[str]]:
        """Pulsa "Jugar", acepta los límites de sesión si se piden y espera al iframe del juego."""
        notes: set[str] = set()
        deadline = time.monotonic() + GAME_LAUNCH_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            if self.page.get_by_text(sel.LOGIN_TO_PLAY).filter(visible=True).count():
                raise GameLaunchError("el juego pide iniciar sesión: llama a login() antes de open_game()")
            if "session_limits" not in notes and self._accept_session_limits(evidence):
                notes.add("session_limits")
                continue
            play = self.page.get_by_role("button", name=sel.PLAY_BUTTON).filter(visible=True)
            if "play_clicked" not in notes and play.count():
                play.first.click()
                notes.add("play_clicked")
                continue
            iframe = self._find_game_iframe()
            if iframe is not None:
                return iframe, notes
            try:
                self.page.wait_for_event("framenavigated", timeout=_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        self.screenshot("game_launch_failed")
        raise GameLaunchError(f"no aparece el iframe del juego (pasos: {sorted(notes) or 'ninguno'})")

    def _accept_session_limits(self, evidence: list[Path]) -> bool:
        """Si aparece el diálogo de límites de sesión, elige lo más prudente y lo confirma."""
        cfg = self.market.site.session_limits
        if cfg is None:
            return False
        title = self.page.get_by_text(re.compile(cfg.title_pattern, re.I)).filter(visible=True)
        if not title.count():
            return False
        evidence.append(self.screenshot("session_limits_dialog"))
        for pattern in (cfg.time_option_pattern, cfg.loss_option_pattern):
            option = self.page.get_by_role("button", name=re.compile(pattern, re.I)).filter(visible=True)
            if not option.count():
                raise GameLaunchError(f"diálogo de límites de sesión sin la opción '{pattern}'")
            option.first.click()
        evidence.append(self.screenshot("session_limits_chosen"))
        self.page.get_by_role("button", name=re.compile(cfg.submit_pattern, re.I)).filter(visible=True).first.click()
        title.first.wait_for(state="hidden", timeout=DEFAULT_TIMEOUT_MS)
        log.info("límites de sesión aceptados (los más prudentes de la configuración)")
        return True

    def _find_game_iframe(self) -> ElementHandle | None:
        """El iframe de primer nivel más grande que no es de terceros conocidos."""
        best: tuple[float, ElementHandle] | None = None
        for frame in self.page.frames:
            if frame == self.page.main_frame or frame.parent_frame != self.page.main_frame:
                continue
            host = urlparse(frame.url).hostname or ""
            if not host or any(bad in host for bad in sel.NON_GAME_IFRAME_HOSTS):
                continue
            try:
                element = frame.frame_element()
                box = element.bounding_box()
            except PlaywrightError:  # el frame se ha recreado mientras mirábamos
                continue
            min_w, min_h = sel.GAME_IFRAME_MIN_SIZE
            if box and box["width"] >= min_w and box["height"] >= min_h:
                area = box["width"] * box["height"]
                if best is None or area > best[0]:
                    best = (area, element)
        return best[1] if best else None

    def _wait_canvas(self, iframe: ElementHandle) -> tuple[Frame, Locator]:
        """El canvas visible más grande dentro del iframe del juego (o de sus frames anidados)."""
        deadline = time.monotonic() + GAME_LAUNCH_TIMEOUT_MS / 1000
        while time.monotonic() < deadline:
            root = iframe.content_frame()
            if root is not None:
                best: tuple[float, Frame, Locator] | None = None
                for frame in [root, *self._descendants(root)]:
                    try:
                        canvases = frame.locator("canvas").filter(visible=True)
                        for i in range(canvases.count()):
                            box = canvases.nth(i).bounding_box()
                            area = box["width"] * box["height"] if box else 0
                            if area and (best is None or area > best[0]):
                                best = (area, frame, canvases.nth(i))
                    except PlaywrightError:
                        continue
                if best is not None:
                    return best[1], best[2]
            try:
                self.page.wait_for_event("framenavigated", timeout=_POLL_MS)
            except PlaywrightTimeoutError:
                pass
        self.screenshot("game_canvas_missing")
        raise GameLaunchError("el juego no muestra ningún canvas")

    @staticmethod
    def _descendants(frame: Frame) -> list[Frame]:
        out: list[Frame] = []
        for child in frame.child_frames:
            out.append(child)
            out.extend(BetssonSite._descendants(child))
        return out

    def _play_mode(self, iframe_url: str, notes: set[str]) -> tuple[PlayMode, str]:
        """Modo de juego a partir de la web, nunca supuesto: URL del iframe y de la página, y pasos del lanzamiento."""
        tokens: set[str] = set()
        for url in (iframe_url, self.page.url):
            for key, value in parse_qsl(urlparse(url).query):
                tokens.update({key.lower(), value.lower()})
        if tokens & _DEMO_TOKENS:
            return "demo", f"la URL indica demo ({sorted(tokens & _DEMO_TOKENS)})"
        if tokens & _REAL_TOKENS:
            return "real", f"la URL indica dinero real ({sorted(tokens & _REAL_TOKENS)})"
        if "session_limits" in notes:
            return "real", "Betsson pidió límites de sesión del regulador antes de lanzar (solo se piden con dinero real)"
        return "unknown", "ni la URL ni el lanzamiento indican el modo"
