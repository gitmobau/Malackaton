"""Esquema de configuración de un mercado (config/markets/<id>.json).

Un mercado nuevo = un archivo JSON que pase esta validación. Nada de mercado,
moneda, idioma ni formato numérico vive fijo en el código.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

_ENV_NAME = r"^[A-Z][A-Z0-9_]*$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CurrencyConfig(_Strict):
    code: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217, p. ej. EUR, PEN")
    symbols: list[str] = Field(min_length=1, description="Símbolos y alias visibles: '€', 'EUR', 'S/'…")
    symbol_position: Literal["before", "after"]

    @field_validator("symbols")
    @classmethod
    def _no_empty_symbols(cls, v: list[str]) -> list[str]:
        if any(not s.strip() for s in v):
            raise ValueError("los símbolos no pueden estar vacíos")
        return v


class NumberFormat(_Strict):
    thousands_sep: str = Field(min_length=1, max_length=1)
    decimal_sep: Literal[",", "."]
    decimals: int = Field(ge=0, le=4)

    @model_validator(mode="after")
    def _different_separators(self) -> "NumberFormat":
        if self.thousands_sep == self.decimal_sep:
            raise ValueError("el separador de miles y el decimal deben ser distintos")
        return self


class ExpectedTexts(_Strict):
    """Textos visibles esperados en el idioma del mercado (se comparan sin distinguir mayúsculas)."""

    insufficient_funds: list[str] = Field(min_length=1)
    balance_labels: list[str] = Field(min_length=1)
    bet_labels: list[str] = Field(min_length=1)
    win_labels: list[str] = Field(min_length=1)


class CredentialsEnv(_Strict):
    """Nombres de las variables de entorno (.env / GitHub Secrets). Nunca los valores."""

    username: str = Field(pattern=_ENV_NAME)
    password: str = Field(pattern=_ENV_NAME)
    username_insufficient: str | None = Field(default=None, pattern=_ENV_NAME)
    password_insufficient: str | None = Field(default=None, pattern=_ENV_NAME)


class SessionLimitsConfig(_Strict):
    """Diálogo de límites de sesión que exige el regulador antes de jugar (p. ej. la DGOJ en es).

    Las opciones a pulsar salen de aquí (nada fijo en el código). Textos como regex.
    """

    title_pattern: str = Field(min_length=1, description="Detecta el diálogo por su título visible.")
    time_option_pattern: str = Field(min_length=1, description="Botón de tiempo de juego a pulsar.")
    loss_option_pattern: str = Field(min_length=1, description="Botón de límite de pérdidas a pulsar.")
    submit_pattern: str = Field(min_length=1, description="Botón que confirma e inicia la sesión de juego.")
    session_hours: float = Field(
        default=0.25, gt=0, le=24, description="Duración de la sesión de juego que se elige (para saber si sigue activa)."
    )
    existing_session_pattern: str | None = Field(
        default=None, description="Aviso de que ya hay una sesión de juego activa: se anota como motivo, no es FAIL."
    )


class BrowserSessionConfig(_Strict):
    """Sesión de jugador iniciada A MANO en un Chrome normal, que el comprobador reutiliza por CDP.

    Un puerto de depuración por cuenta ("funded" con saldo, "empty" sin saldo). El perfil de Chrome
    vive fuera del repo (<raíz>/.chrome-profiles/<mercado>-<cuenta>) y equivale a una credencial.
    """

    cdp_ports: dict[Literal["funded", "empty"], int] = Field(min_length=1)

    @field_validator("cdp_ports")
    @classmethod
    def _valid_ports(cls, v: dict[str, int]) -> dict[str, int]:
        if any(not 1024 <= port <= 65535 for port in v.values()) or len(set(v.values())) != len(v):
            raise ValueError("puertos CDP no válidos o repetidos")
        return v


class SiteConfig(_Strict):
    """Lo de la web de Betsson que puede cambiar por mercado. Lo común está en betsson/site/selectors.py."""

    casino_path: str = "/casino"
    browser_session: BrowserSessionConfig | None = Field(
        default=None, description="None si en este mercado no se usa la sesión iniciada a mano."
    )
    session_limits: SessionLimitsConfig | None = Field(
        default=None, description="None si el mercado no pide límites de sesión antes de jugar."
    )
    search_terms: dict[str, str] = Field(
        default_factory=dict,
        description="Término de búsqueda por slug de juego, si en este mercado el nombre visible difiere.",
    )


class Market(_Strict):
    id: str = Field(pattern=r"^[a-z]{2,5}$")
    name: str
    base_url: HttpUrl
    locale: str = Field(pattern=r"^[a-z]{2}-[A-Z]{2}$")
    language: str = Field(pattern=r"^[a-z]{2}$")
    timezone: str
    currency: CurrencyConfig
    number_format: NumberFormat
    min_bet: Decimal = Field(gt=0)
    money_tolerance: Decimal = Field(
        default=Decimal("0.01"), ge=0, description="Diferencia máxima admitida al cuadrar saldos (redondeos)."
    )
    expected_texts: ExpectedTexts
    credentials_env: CredentialsEnv
    site: SiteConfig = Field(default_factory=SiteConfig)
    real_execution_enabled: bool = Field(
        description="False si no hay cuenta: el informe lo muestra como 'mercado configurado; ejecución real desactivada'."
    )
    verified: bool = Field(description="True si la estructura del sitio se ha comprobado en real.")

    @model_validator(mode="after")
    def _language_matches_locale(self) -> "Market":
        if not self.locale.startswith(self.language + "-"):
            raise ValueError(f"language '{self.language}' no casa con locale '{self.locale}'")
        return self

    @property
    def currency_code(self) -> str:
        """ISO 4217 (lo pide el Protocol MarketContext de core)."""
        return self.currency.code

    @property
    def origin(self) -> str:
        return str(self.base_url).rstrip("/")
