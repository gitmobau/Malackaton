"""Interfaces entre áreas. Los escenarios (C) solo hablan con esto.

- BetssonSite: lo implementa A (betsson/site/). Leer el DOM de Betsson es legítimo.
- GameEyes: lo implementa B (betsson/game/, betsson/vision/). Solo mira el canvas.
- ProviderProfile y ProviderRegistry: los implementa B (betsson/profiles/<proveedor>/).
- MarketContext: lo cumple el esquema de config/markets de A.

Ningún nombre de proveedor aparece aquí. Las zonas van en fracciones del canvas.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator

from betsson.core.money import Money

INCONCLUSIVE_PREFIX = "inconclusive: "

if TYPE_CHECKING:  # numpy solo para las firmas: core no depende de él en ejecución
    import numpy as np

GameField = Literal["balance", "bet", "win"]
PlayMode = Literal["real", "demo", "unknown"]
BetTarget = Literal["min", "above_balance"]  # S1: apuesta mínima; S2: por encima del saldo

# Rutas de evidencia: se guardan con "/" (portables entre el runner Windows y Linux).
# run_scenario las escribe relativas a la carpeta del run.
EvidencePath = Annotated[Path, PlainSerializer(lambda p: p.as_posix(), return_type=str)]


# --- Modelos de datos compartidos -------------------------------------------


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Rect(_Frozen):
    """Rectángulo en fracciones del canvas (0 a 1). Nunca píxeles absolutos."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside(self) -> Rect:
        eps = 1e-9
        if self.x + self.w > 1 + eps or self.y + self.h > 1 + eps:
            raise ValueError("el rectángulo se sale del canvas")
        return self


class IntroScreen(_Frozen):
    """Pantalla de inicio que hay que cerrar antes de jugar."""

    name: str
    match_texts: tuple[str, ...] = ()  # OCR, en minúsculas, por subcadena
    template: Path | None = None
    click: Rect  # dónde pulsar (pista)


class SpinEndSignal(_Frozen):
    diff_threshold: float = Field(default=0.01, gt=0, le=1)  # cambio mínimo entre frames para "se mueve"
    stable_frames: int = Field(default=4, ge=1)  # frames seguidos sin cambio = fin de la tirada
    timeout_s: float = Field(default=30.0, gt=0)


class Reading(_Frozen):
    """Lectura de un importe visible. Si es dudosa: money=None y reason="inconclusive: …".

    currency_seen=True solo si el símbolo o código de la moneda aparecía en el texto
    leído. Si no, money.currency es la del mercado por defecto y no prueba nada para
    currency_matches_market.

    ok solo dice que hay importe; el umbral de confianza lo aplica quien lee (perfil).
    """

    raw_text: str = ""
    money: Money | None = None
    currency_seen: bool = False
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_path: EvidencePath | None = None
    reason: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _doubtful_has_reason(cls, data: Any) -> Any:
        # Sin importe siempre hay un motivo "inconclusive: …" (nunca un hueco silencioso).
        if isinstance(data, dict) and data.get("money") is None:
            reason = (data.get("reason") or "").strip() or "sin lectura"
            if not reason.startswith(INCONCLUSIVE_PREFIX):
                reason = INCONCLUSIVE_PREFIX + reason
            data = {**data, "reason": reason}
        return data

    @property
    def ok(self) -> bool:
        return self.money is not None


class SpinEnd(_Frozen):
    completed: bool
    duration_s: float = Field(default=0.0, ge=0)
    reason: str | None = None
    evidence_path: EvidencePath | None = None


class Message(_Frozen):
    """Mensaje visible en el juego (p. ej. saldo insuficiente).

    matches_insufficient: True = se ve el texto de saldo insuficiente; False = se leyó
    la pantalla y no está; None = no se pudo leer (no concluyente, nunca False).
    """

    text: str = ""
    lang_detected: str | None = None  # "es", "en"…
    matches_insufficient: bool | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_path: EvidencePath | None = None
    reason: str | None = None


# --- Mercado (lo mínimo que necesita core; el esquema completo es de A) -------


@runtime_checkable
class MarketContext(Protocol):
    id: str  # "es", "com", "pe"
    currency_code: str  # ISO 4217 ("EUR", "PEN")
    language: str  # "es", "en"
    money_tolerance: Decimal  # diferencia máxima admitida al cuadrar saldos


# --- Proveedor -----------------------------------------------------------------


@runtime_checkable
class ProviderProfile(Protocol):
    """Lo específico de un proveedor. Añadir uno = una carpeta en betsson/profiles/."""

    name: str  # p. ej. "generic-vision"
    intro_screens: list[IntroScreen]
    labels: dict[GameField, dict[str, list[str]]]  # campo → idioma → alias visibles
    hint_zones: dict[GameField, Rect]  # solo pista; el ancla real es la etiqueta
    spin_templates: list[Path]
    spin_hint: Rect
    insufficient_texts: dict[str, list[str]]  # idioma → textos de saldo insuficiente
    spin_end: SpinEndSignal
    network_pattern: str | None  # regex de la petición de tirada; solo confirma

    def detect(self, iframe_url: str, frame: np.ndarray | None) -> float:
        """Confianza de 0 a 1 de que este perfil corresponde al juego."""
        ...


@runtime_checkable
class ProviderRegistry(Protocol):
    def resolve(self, iframe_url: str, frame: np.ndarray | None) -> ProviderProfile:
        """Perfil con mayor detect(); generic-vision si ninguno pasa de 0,5.

        Nunca lanza: un proveedor desconocido no es un error, se juega con generic-vision.
        """
        ...

    def ensure_recognized(self, profile: ProviderProfile, frame: np.ndarray | None) -> None:
        """Comprueba que el perfil (de un proveedor conocido) aún reconoce la pantalla.

        Lanza ProviderUIChanged si no la reconoce ni recalibrando (deriva del proveedor).
        """
        ...


# --- Juego abierto y ojos ---------------------------------------------------------


@runtime_checkable
class GameHandle(Protocol):
    """Juego abierto en la web de Betsson (lo devuelve BetssonSite.open_game)."""

    iframe_url: str
    play_mode: PlayMode  # leído de la web de Betsson o de la pantalla, nunca supuesto
    play_mode_reason: str | None  # por qué se decidió play_mode (p. ej. "Betsson pidió los límites de sesión")
    evidence: tuple[Path, ...]  # pasos del jugador al abrir el juego (diálogo de límites, juego abierto…)

    def capture(self) -> np.ndarray:
        """Captura actual del canvas del juego (RGB)."""
        ...


@runtime_checkable
class GameEyes(Protocol):
    """Mira el canvas como un jugador. Un clic nunca es prueba."""

    profile: ProviderProfile

    def read_balance(self) -> Reading: ...

    def read_bet(self) -> Reading: ...

    def read_win(self) -> Reading: ...

    def set_bet(self, target: BetTarget) -> Reading:
        """Ajusta la apuesta ("min" en S1, "above_balance" en S2) y devuelve la apuesta visible."""
        ...

    def spin(self) -> bool:
        """Pulsa girar y devuelve True solo si se ve que la tirada empezó."""
        ...

    def wait_spin_end(self) -> SpinEnd: ...

    def read_message(self) -> Message: ...

    def screenshot(self, name: str) -> Path:
        """Guarda una captura del juego para el informe (sin datos sensibles)."""
        ...


@runtime_checkable
class GameEyesFactory(Protocol):
    """Construye los ojos para un juego abierto (B). run_scenario la recibe inyectada."""

    def __call__(self, handle: GameHandle, profile: ProviderProfile, market: MarketContext) -> GameEyes: ...


# --- Web de Betsson ---------------------------------------------------------------


@runtime_checkable
class BetssonSite(Protocol):
    """La web de Betsson. Las credenciales se leen del entorno dentro de A, nunca llegan aquí."""

    def login(self) -> bool:
        """Inicia sesión con la cuenta de prueba (traza pausada, campos tapados)."""
        ...

    def is_logged_in(self) -> bool: ...

    def read_balance(self) -> Reading:
        """Saldo de Betsson leído del DOM (raw_text, money, currency_seen, captura)."""
        ...

    def open_game(self, slug: str) -> GameHandle:
        """Abre el juego en Real Play. Lanza GameOpenError si no se puede abrir."""
        ...

    def screenshot(self, name: str) -> Path:
        """Captura de la web (campos sensibles tapados)."""
        ...
