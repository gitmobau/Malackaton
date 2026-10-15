"""Test de contrato de perfiles: todo perfil registrado cumple ProviderProfile.

Añadir un proveedor = añadir su carpeta en betsson/profiles/ y pasar este test, sin
tocar el núcleo. Cubre también el multimercado: cada idioma de mercado configurado
tiene etiquetas y textos de saldo insuficiente en el perfil (o el perfil es el de respaldo).
"""
from __future__ import annotations

import inspect
import re
from typing import Any

import numpy as np
import pytest

from betsson.core import ProviderProfile, Rect, SpinEndSignal

pytestmark = pytest.mark.unit

registry = pytest.importorskip("betsson.profiles.registry", reason="falta el registro de perfiles (área B)")

PROFILES: dict[str, Any] = registry.all_profiles()
FALLBACK = getattr(registry, "FALLBACK_PROFILE", "generic-vision")
FIELDS = ("balance", "bet", "win")
PROTOCOL_METHODS = ("detect",)


def _market_languages() -> list[str]:
    try:
        from betsson.market.loader import list_markets, load_market
    except ImportError:
        return ["es", "en"]
    return sorted({load_market(m).language for m in list_markets()})


LANGUAGES = _market_languages()


@pytest.fixture(params=sorted(PROFILES), ids=sorted(PROFILES))
def profile(request: pytest.FixtureRequest) -> Any:
    return PROFILES[request.param]


def test_there_is_a_fallback_profile() -> None:
    assert FALLBACK in PROFILES, "falta el perfil de respaldo para proveedores desconocidos"


def test_profile_matches_protocol(profile: Any) -> None:
    assert isinstance(profile, ProviderProfile)
    assert isinstance(profile.name, str) and profile.name.strip()
    for name in PROTOCOL_METHODS:
        expected = list(inspect.signature(getattr(ProviderProfile, name)).parameters)[1:]
        actual = list(inspect.signature(getattr(profile, name)).parameters)
        assert actual[: len(expected)] == expected, f"{profile.name}.{name}{actual} no sigue {expected}"


def test_zones_are_canvas_fractions(profile: Any) -> None:
    assert isinstance(profile.spin_hint, Rect)
    assert all(isinstance(r, Rect) for r in profile.hint_zones.values())
    assert all(isinstance(s.click, Rect) for s in profile.intro_screens)
    assert isinstance(profile.spin_end, SpinEndSignal)


def test_detect_returns_confidence(profile: Any) -> None:
    blank = np.zeros((768, 1366, 3), dtype=np.uint8)
    for frame in (blank, None):
        score = profile.detect("https://games.example.test/unknown/slot", frame)
        assert isinstance(score, float) and 0.0 <= score <= 1.0


def test_unknown_game_is_not_claimed_by_a_specific_profile(profile: Any) -> None:
    if profile.name == FALLBACK:
        pytest.skip("el perfil de respaldo acepta cualquier juego")
    blank = np.zeros((768, 1366, 3), dtype=np.uint8)
    assert profile.detect("https://games.example.test/unknown/slot", blank) < getattr(registry, "MIN_CONFIDENCE", 0.5)


def test_texts_cover_every_market_language(profile: Any) -> None:
    for lang in LANGUAGES:
        assert profile.insufficient_texts.get(lang), f"{profile.name}: sin textos de saldo insuficiente en '{lang}'"
        for field in ("balance", "bet"):
            assert profile.labels.get(field, {}).get(lang), f"{profile.name}: sin etiqueta {field} en '{lang}'"


def test_network_pattern_is_valid_regex(profile: Any) -> None:
    if profile.network_pattern is not None:
        re.compile(profile.network_pattern)


def test_unknown_provider_resolves_to_fallback() -> None:
    blank = np.zeros((768, 1366, 3), dtype=np.uint8)
    assert registry.resolve("https://games.example.test/unknown/slot", blank).name == FALLBACK
