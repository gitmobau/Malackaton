"""Registro de perfiles: descubre cada carpeta de betsson/profiles/ que exponga `PROFILE` en su profile.py.

Añadir un proveedor = añadir una carpeta. No hay que tocar este archivo ni el núcleo.
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

import numpy as np

import betsson.profiles as profiles_pkg
from betsson.profiles.base import ProviderProfile

FALLBACK_PROFILE = "generic-vision"
MIN_CONFIDENCE = 0.5


@lru_cache(maxsize=1)
def all_profiles() -> dict[str, ProviderProfile]:
    found: dict[str, ProviderProfile] = {}
    for module in pkgutil.iter_modules(profiles_pkg.__path__):
        if not module.ispkg or module.name.startswith("_") or module.name == "tests":
            continue
        profile = getattr(importlib.import_module(f"{profiles_pkg.__name__}.{module.name}.profile"), "PROFILE", None)
        if not isinstance(profile, ProviderProfile):
            raise TypeError(f"betsson/profiles/{module.name}/profile.py debe exponer PROFILE: ProviderProfile")
        if profile.name in found:
            raise ValueError(f"perfil duplicado: {profile.name}")
        found[profile.name] = profile
    return found


def get_profile(name: str) -> ProviderProfile:
    try:
        return all_profiles()[name]
    except KeyError:
        raise KeyError(f"perfil desconocido '{name}'; hay: {sorted(all_profiles())}") from None


def resolve(iframe_url: str, frame: np.ndarray | None = None) -> ProviderProfile:
    """Perfil con más confianza. Si ninguno llega a MIN_CONFIDENCE se usa el genérico.

    Si el genérico tampoco reconoce la pantalla, GameEyes.ensure_recognized() lanza ProviderUIChanged.
    """
    scored = sorted(
        ((p.detect(iframe_url, frame), p) for p in all_profiles().values() if p.name != FALLBACK_PROFILE),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if scored and scored[0][0] >= MIN_CONFIDENCE:
        return scored[0][1]
    return get_profile(FALLBACK_PROFILE)
