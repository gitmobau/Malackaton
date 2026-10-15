"""Registro de perfiles (cumple betsson.core.ProviderRegistry).

Descubre cada carpeta de betsson/profiles/ que exponga `PROFILE` en su profile.py.
Añadir un proveedor = añadir una carpeta. No hay que tocar este archivo ni el núcleo.

Decisión del equipo (15-oct):
- Proveedor desconocido: resolve() devuelve generic-vision. No es un error.
- Proveedor conocido cuya pantalla ya no reconoce su perfil (deriva): ensure_recognized() lanza ProviderUIChanged.
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

import betsson.profiles as profiles_pkg
from betsson.core import ProviderUIChanged
from betsson.profiles.base import ProfileSpec
from betsson.vision.anchors import find_amount
from betsson.vision.ocr import read_text

FALLBACK_PROFILE = "generic-vision"
MIN_CONFIDENCE = 0.5
# Lo mínimo que tiene que verse para decir que el perfil reconoce el juego.
_REQUIRED_FIELDS = ("balance", "bet")
# Recalibración: si a tamaño real no se ven las etiquetas, se prueba ampliando.
_RECALIBRATION_UPSCALES = (1.0, 2.0)


@lru_cache(maxsize=1)
def all_profiles() -> dict[str, ProfileSpec]:
    found: dict[str, ProfileSpec] = {}
    for module in pkgutil.iter_modules(profiles_pkg.__path__):
        if not module.ispkg or module.name.startswith("_") or module.name == "tests":
            continue
        profile = getattr(importlib.import_module(f"{profiles_pkg.__name__}.{module.name}.profile"), "PROFILE", None)
        if not isinstance(profile, ProfileSpec):
            raise TypeError(f"betsson/profiles/{module.name}/profile.py debe exponer PROFILE: ProfileSpec")
        if profile.name in found:
            raise ValueError(f"perfil duplicado: {profile.name}")
        found[profile.name] = profile
    return found


def get_profile(name: str) -> ProfileSpec:
    try:
        return all_profiles()[name]
    except KeyError:
        raise KeyError(f"perfil desconocido '{name}'; hay: {sorted(all_profiles())}") from None


def resolve(iframe_url: str, frame: np.ndarray | None = None) -> ProfileSpec:
    """Perfil con más confianza; generic-vision si ninguno llega a MIN_CONFIDENCE. Nunca lanza."""
    scored = sorted(
        ((p.detect(iframe_url, frame), p) for p in all_profiles().values() if p.name != FALLBACK_PROFILE),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if scored and scored[0][0] >= MIN_CONFIDENCE:
        return scored[0][1]
    return get_profile(FALLBACK_PROFILE)


def missing_fields(profile: ProfileSpec, frame: np.ndarray) -> list[str]:
    """Campos imprescindibles (saldo y apuesta) cuya etiqueta con importe no se ve, ni ampliando."""
    missing = list(_REQUIRED_FIELDS)
    for upscale in _RECALIBRATION_UPSCALES:
        boxes = read_text(frame, upscale=upscale)
        missing = [f for f in missing if find_amount(boxes, profile.label_aliases(f)) is None]
        if not missing:
            break
    return missing


def ensure_recognized(
    profile: ProfileSpec, frame: np.ndarray | None, evidence_dir: Path | None = None
) -> None:
    """Lanza ProviderUIChanged si el perfil no reconoce la pantalla (ni recalibrando).

    `frame` es la captura del canvas en BGR (GameEyes) o RGB (GameHandle.capture): el OCR lee ambas.
    """
    if frame is None:
        raise ProviderUIChanged(f"sin captura del juego para comprobar el perfil '{profile.name}'")
    missing = missing_fields(profile, frame)
    if not missing:
        return
    evidence: list[Path] = []
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path = evidence_dir / "provider_ui_changed.png"
        cv2.imwrite(str(path), frame)
        evidence.append(path)
    raise ProviderUIChanged(
        f"el perfil '{profile.name}' no encuentra en pantalla las etiquetas de {missing}", evidence=evidence
    )


class Registry:
    """Implementación de betsson.core.ProviderRegistry para inyectar en run_scenario."""

    def __init__(self, evidence_dir: Path | None = None) -> None:
        self.evidence_dir = evidence_dir

    def resolve(self, iframe_url: str, frame: np.ndarray | None) -> ProfileSpec:
        return resolve(iframe_url, frame)

    def ensure_recognized(self, profile: ProfileSpec, frame: np.ndarray | None) -> None:
        ensure_recognized(profile, frame, self.evidence_dir)


REGISTRY = Registry()
