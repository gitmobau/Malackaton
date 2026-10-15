"""Modelo de un perfil de proveedor (área B). Cumple el Protocol betsson.core.ProviderProfile.

Un perfil son *datos*: alias de las etiquetas por idioma, pistas de zona en fracciones del canvas,
el botón de girar, los controles de apuesta, las pantallas de inicio y los textos de saldo insuficiente.
El motor (betsson/vision, betsson/game) no conoce ningún proveedor: solo lee estos datos.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from betsson.core import GameField, IntroScreen, Rect, SpinEndSignal

AMOUNT_FIELDS: tuple[GameField, ...] = ("balance", "bet", "win")


class IntroStep(IntroScreen):
    """IntroScreen de core más cómo cerrarla: por texto, por plantilla (`template`), por pista o esperando."""

    click_text: str | None = None  # texto del botón que hay que pulsar (preferente)
    wait_only: bool = False  # pantalla de carga: no se pulsa, se espera a que cambie

    @model_validator(mode="after")
    def _recognizable(self) -> IntroStep:
        if not self.match_texts:
            raise ValueError(f"intro '{self.name}': sin textos para reconocerla")
        return self


class SpinTiming(SpinEndSignal):
    """SpinEndSignal de core más el tiempo máximo para ver que la tirada empieza."""

    start_timeout_s: float = Field(default=5.0, gt=0)


class Control(BaseModel):
    """Un botón del juego: plantilla (preferente) y pista de zona en fracciones."""

    model_config = ConfigDict(frozen=True)

    templates: list[Path] = []
    hint: Rect


class ProfileSpec(BaseModel):
    """Perfil enchufable de un proveedor. Añadir un proveedor = añadir una carpeta con un PROFILE."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # --- Protocol de core ---
    name: str
    intro_screens: list[IntroStep] = []
    labels: dict[GameField, dict[str, list[str]]]  # campo -> idioma -> alias visibles
    hint_zones: dict[GameField, Rect] = {}  # solo pista; el ancla real es la etiqueta
    spin_templates: list[Path] = []
    spin_hint: Rect
    insufficient_texts: dict[str, list[str]] = {}  # idioma -> textos de saldo insuficiente
    spin_end: SpinTiming = SpinTiming()
    network_pattern: str | None = None  # regex de la petición de tirada; solo confirma
    # --- propio de B ---
    url_patterns: list[str] = []  # regex sobre la URL del iframe del juego
    spin_key: str | None = None  # tecla alternativa para girar
    bet_down: Control | None = None
    bet_up: Control | None = None
    # True si el juego no muestra la etiqueta de ganancia cuando la tirada no gana:
    # entonces "sin etiqueta tras una tirada" se lee como ganancia 0.
    win_hidden_when_zero: bool = False
    demo_url: str | None = None  # demo pública sin registro, para capturar fixtures

    @field_validator("labels")
    @classmethod
    def _all_fields_labelled(
        cls, value: dict[GameField, dict[str, list[str]]]
    ) -> dict[GameField, dict[str, list[str]]]:
        missing = [f for f in AMOUNT_FIELDS if not any(value.get(f, {}).values())]
        if missing:
            raise ValueError(f"faltan alias de etiqueta para: {missing}")
        return value

    @field_validator("url_patterns")
    @classmethod
    def _patterns_compile(cls, value: list[str]) -> list[str]:
        for pattern in value:
            re.compile(pattern)
        return value

    def label_aliases(self, field: GameField, lang: str | None = None) -> list[str]:
        """Alias de la etiqueta: primero los del idioma pedido y después el resto (los juegos mezclan idiomas)."""
        by_lang = self.labels[field]
        ordered = list(by_lang.get(lang, [])) if lang else []
        for aliases in by_lang.values():
            ordered.extend(a for a in aliases if a not in ordered)
        return ordered

    def detect(self, iframe_url: str, frame: np.ndarray | None = None) -> float:
        """Confianza 0..1 de que este perfil corresponde al juego abierto."""
        if any(re.search(p, iframe_url or "", re.IGNORECASE) for p in self.url_patterns):
            return 1.0
        return 0.0
