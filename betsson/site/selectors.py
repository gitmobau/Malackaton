"""Selectores de la web de Betsson (plataforma común a todos los mercados).

Verificados en betsson.es el 15-oct. Los localizadores CSS de Playwright atraviesan
el Shadow DOM abierto (componentes Stencil). Los textos visibles van como regex con
alternativas por idioma, para que un mercado nuevo no obligue a tocar el código.
"""
from __future__ import annotations

import re

# --- Cookies (OneTrust). El banner puede aparecer tarde: se maneja con add_locator_handler.
COOKIE_BANNER = "#onetrust-banner-sdk"
COOKIE_REJECT_DIRECT = "#onetrust-reject-all-handler"
COOKIE_SETTINGS_BUTTON = "#onetrust-pc-btn-handler"
COOKIE_REFUSE_ALL = ".ot-pc-refuse-all-handler"

# --- Lobby y búsqueda --------------------------------------------------------
SCROLL_CONTAINER = "div.content-wrapper"
GAME_THUMBNAIL = '[data-test-id^="gaming-game-thumbnail-"]'
GAME_THUMBNAIL_PREFIX = "gaming-game-thumbnail-"
SEARCH_OPEN = re.compile(r"^\s*(buscar juegos|search games?)\s*$", re.I)
SEARCH_OPEN_TRIGGER = "[data-test-id='gaming-search-text']"  # independiente del idioma
SEARCH_INPUT_PLACEHOLDER = re.compile(r"búsqueda|buscar|search", re.I)
SEARCH_MODAL = "[data-test-id='search-modal-container']"
# Cada resultado enlaza a /casino/<categoría>/<slug>: se identifica por el slug, no por el texto.
SEARCH_RESULT_LINK = "a[data-test-id='game-thumbnail-title']"

# --- Página del juego --------------------------------------------------------
LOGIN_TO_PLAY = re.compile(r"ingresar y jugar|log ?in and play|login to play", re.I)
# Contenedores de diálogos modales (el de límites de sesión del regulador, por ejemplo).
DIALOG_CONTAINERS = "[role='dialog'], dialog, [aria-modal='true'], [class*='modal' i], [class*='dialog' i]"
# Parámetro con el que la web lanza el juego en Real Play desde su página.
GAME_PLAY_QUERY = "gameAction=play"
# Botón de la página del juego que lo lanza (con sesión iniciada).
PLAY_BUTTON = re.compile(r"^\s*(jugar|jugar ahora|play|play now)\s*$", re.I)
# Iframes de terceros que nunca son el juego.
NON_GAME_IFRAME_HOSTS = ("group-ib.com", "onetrust", "fullstory", "google", "doubleclick", "facebook")
GAME_IFRAME_MIN_SIZE = (300, 200)  # px CSS: el juego es el iframe grande

# --- Login (página /inicio?returnUrl=...) ---------------------------------------
LOGIN_OPEN = re.compile(r"^\s*(iniciar sesión|log ?in|sign in)\s*$", re.I)
LOGIN_USERNAME = "[data-test-id='email-input']"
LOGIN_PASSWORD = "[data-test-id='password-input']"
LOGIN_SUBMIT = "[data-test-id='account-login-btn-1-button']"
LOGIN_DIALOG_CLOSE = "[data-test-id='dialog-close-button']"

LOGOUT = re.compile(r"^\s*(cerrar sesión|salir|log ?out|sign out)\s*$", re.I)
USER_MENU = "[data-test-id='user-icon']"
WAF_COOKIE = "aws-waf-token"  # la deja el desafío del WAF al terminar solo

# --- Saldo (cabecera, con sesión iniciada) -------------------------------------
# Botón de saldo de la cabecera de la cuenta (verificado el 15-oct con sesión: "100,00 €"). SOLO de aquí se
# lee el saldo: un texto con "€" cualquiera puede ser un banner ("¡5.000€ en juego…!").
BALANCE_BUTTON = "[data-test-id='balance-button']"
# En la página del juego la cabecera es otra: "Saldo ▾" (in-game-balance-button) abre un resumen cuyo
# total es user-summary-balance (también hay bonus, bloqueado y retirable: NO son el saldo).
IN_GAME_BALANCE_BUTTON = "[data-test-id='in-game-balance-button']"
SUMMARY_BALANCE = "[data-test-id='user-summary-balance']"

# --- API pública de juegos (la pide la propia página) -----------------------------
GAME_API_FRAGMENT = "/api/v2/games/"
