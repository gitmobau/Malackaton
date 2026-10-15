"""Sesión de jugador iniciada A MANO en un Chrome normal, reutilizada por CDP (decisión del 15-oct con un mentor).

- Una persona inicia sesión en un Chrome lanzado como proceso normal (betsson.site.login_asistido).
- Las ejecuciones se conectan a ese Chrome con connect_over_cdp. Si no hay sesión: no concluyente, y
  NUNCA se intenta un login automatizado de reserva.
- Los perfiles (<raíz>/.chrome-profiles/<mercado>-<cuenta>) están FUERA del repo y equivalen a una
  credencial. Junto a cada uno, un JSON con HORAS (no secretos): cuándo inició sesión la persona y
  cuándo se aceptaron los límites de sesión del regulador.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Browser, Page, Playwright

from betsson.market.schema import Market

# <raíz>/.chrome-profiles, al lado de los worktrees y fuera de cualquier repo. Se puede cambiar por entorno.
PROFILES_ROOT = Path(os.environ.get("CHROME_PROFILES_ROOT") or Path(__file__).resolve().parents[3] / ".chrome-profiles")
_CHROME_CANDIDATES = (
    Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
)


class SessionUnavailable(RuntimeError):
    """No hay un Chrome con sesión al que conectarse (no concluyente: repetir el login asistido)."""


@dataclass(frozen=True)
class BrowserSession:
    market: Market
    account: str

    @property
    def port(self) -> int:
        cfg = self.market.site.browser_session
        if cfg is None or self.account not in cfg.cdp_ports:
            raise SessionUnavailable(f"el mercado '{self.market.id}' no tiene puerto CDP para la cuenta '{self.account}'")
        return cfg.cdp_ports[self.account]  # type: ignore[index]

    @property
    def cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def profile_dir(self) -> Path:
        return PROFILES_ROOT / f"{self.market.id}-{self.account}"

    @property
    def _state_file(self) -> Path:
        return PROFILES_ROOT / f"{self.market.id}-{self.account}.state.json"

    # -- estado (solo horas) -------------------------------------------------------------

    def _read_state(self) -> dict[str, str]:
        try:
            return json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self, **values: str | None) -> None:
        PROFILES_ROOT.mkdir(parents=True, exist_ok=True)
        state = {**self._read_state(), **values}
        self._state_file.write_text(json.dumps(state, indent=1), encoding="utf-8")

    def record_login(self, when: datetime | None = None) -> None:
        self._write_state(logged_in_at=(when or datetime.now()).isoformat(timespec="minutes"), game_session_at=None)

    def record_game_session(self, when: datetime | None = None) -> None:
        self._write_state(game_session_at=(when or datetime.now()).isoformat(timespec="minutes"))

    def clear(self) -> None:
        self._write_state(logged_in_at=None, game_session_at=None)

    @property
    def logged_in_at(self) -> datetime | None:
        value = self._read_state().get("logged_in_at")
        return datetime.fromisoformat(value) if value else None

    @property
    def game_session_at(self) -> datetime | None:
        value = self._read_state().get("game_session_at")
        return datetime.fromisoformat(value) if value else None

    # -- Chrome ----------------------------------------------------------------------------

    def is_listening(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.cdp_url}/json/version", timeout=2) as resp:
                return resp.status == 200
        except OSError:
            return False

    def launch_chrome(self) -> None:
        """Chrome del sistema como PROCESO NORMAL (sin Playwright), que sigue abierto al terminar el script."""
        chrome = os.environ.get("CHROME_PATH") or next((str(c) for c in _CHROME_CANDIDATES if c.is_file()), None)
        if chrome is None:
            raise SessionUnavailable("no se encuentra chrome.exe (define CHROME_PATH)")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        subprocess.Popen(  # noqa: S603 - ejecutable y argumentos son nuestros, sin entrada externa
            [
                chrome,
                f"--user-data-dir={self.profile_dir}",
                f"--remote-debugging-port={self.port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1366,900",
                self.market.origin + self.market.site.casino_path,
            ],
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )

    def connect(self, playwright: Playwright) -> tuple[Browser, Page]:
        """Se conecta al Chrome ya autenticado y abre una pestaña propia para esta ejecución."""
        if not self.is_listening():
            raise SessionUnavailable(
                f"no hay Chrome escuchando en el puerto {self.port}: repetir el login asistido "
                f"(python -m betsson.site.login_asistido --market {self.market.id} --account {self.account})"
            )
        browser = playwright.chromium.connect_over_cdp(self.cdp_url)
        if not browser.contexts:
            raise SessionUnavailable("el Chrome de la sesión no tiene contexto de navegación")
        page = browser.contexts[0].new_page()
        # Una pestaña en segundo plano no se pinta y sus capturas se cuelgan: se trae al frente.
        page.bring_to_front()
        return browser, page
