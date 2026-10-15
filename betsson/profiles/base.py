"""Contrato de un perfil de proveedor (copia provisional hasta que el área C publique betsson/core).

Un perfil son *datos*: alias de las etiquetas por idioma, pistas de zona en fracciones del canvas,
el botón de girar, las pantallas de inicio y los textos de saldo insuficiente.
El motor (betsson/vision, betsson/game) no conoce ningún proveedor: solo lee estos datos.

Cuando llegue betsson/core/interfaces.py, Rect, IntroScreen, SpinEndSignal y AmountField
se importarán de allí y este módulo solo mantendrá ProviderProfile (implementación de B).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AmountField = Literal["balance", "bet", "win"]
AMOUNT_FIELDS: tuple[AmountField, ...] = ("balance", "bet", "win")


class Rect(BaseModel):
    """Rectángulo en fracciones del canvas (0..1). Nunca píxeles absolutos."""

    model_config = ConfigDict(frozen=True)

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_canvas(self) -> "Rect":
        if self.x + self.w > 1.0001 or self.y + self.h > 1.0001:
            raise ValueError(f"el rectángulo se sale del canvas: {self}")
        return self

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) en píxeles para una imagen concreta."""
        return (
            int(self.x * width),
            int(self.y * height),
            int((self.x + self.w) * width),
            int((self.y + self.h) * height),
        )


class IntroScreen(BaseModel):
    """Pantalla de inicio que hay que cerrar antes de jugar (sonido, continuar, tutorial)."""

    model_config = ConfigDict(frozen=True)

    name: str
    match_texts: list[str] = []  # subcadenas que el OCR debe ver (se comparan sin tildes ni mayúsculas)
    click: Rect | None = None  # dónde pulsar si no se encuentra el botón (pista en fracción)
    click_text: str | None = None  # texto del botón que hay que pulsar (preferente)
    click_template: Path | None = None  # plantilla del botón si no tiene texto
    wait_only: bool = False  # pantalla de carga: no se pulsa, se espera a que cambie

    @model_validator(mode="after")
    def _has_action(self) -> "IntroScreen":
        if not self.match_texts:
            raise ValueError(f"intro '{self.name}': sin textos para reconocerla")
        if not (self.wait_only or self.click or self.click_text or self.click_template):
            raise ValueError(f"intro '{self.name}': no dice cómo cerrarla")
        return self


class SpinEndSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    diff_threshold: float = Field(default=0.004, gt=0)  # cambio medio mínimo para "se mueve"
    stable_frames: int = Field(default=4, ge=2)  # frames seguidos sin cambio = fin de la tirada
    start_timeout_s: float = Field(default=5.0, gt=0)
    timeout_s: float = Field(default=30.0, gt=0)


class ProviderProfile(BaseModel):
    """Perfil enchufable de un proveedor. Añadir un proveedor = añadir una carpeta con un PROFILE."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    url_patterns: list[str] = []  # regex sobre la URL del iframe del juego
    intro_screens: list[IntroScreen] = []
    labels: dict[AmountField, dict[str, list[str]]]  # campo -> idioma -> alias visibles
    hint_zones: dict[AmountField, Rect] = {}  # solo pista; el ancla real es la etiqueta
    spin_templates: list[Path] = []
    spin_hint: Rect | None = None
    spin_key: str | None = None  # tecla alternativa para girar
    insufficient_texts: dict[str, list[str]] = {}  # idioma -> textos de saldo insuficiente
    spin_end: SpinEndSignal = SpinEndSignal()
    network_pattern: str | None = None  # regex de la petición de tirada; solo confirma
    demo_url: str | None = None  # demo pública sin registro, para capturar fixtures

    @field_validator("labels")
    @classmethod
    def _all_fields_labelled(
        cls, value: dict[AmountField, dict[str, list[str]]]
    ) -> dict[AmountField, dict[str, list[str]]]:
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

    def label_aliases(self, field: AmountField, lang: str | None = None) -> list[str]:
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
