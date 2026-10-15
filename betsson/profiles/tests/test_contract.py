"""Test de contrato: cualquier perfil de betsson/profiles/<proveedor>/ tiene que pasarlo.

Añadir un proveedor = añadir su carpeta y que este archivo siga en verde, sin tocar el núcleo.
"""
from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from betsson.core import ProviderProfile, ProviderRegistry
from betsson.profiles.base import AMOUNT_FIELDS, ProfileSpec
from betsson.profiles.registry import FALLBACK_PROFILE, MIN_CONFIDENCE, all_profiles, resolve

PROFILES = sorted(all_profiles().values(), key=lambda p: p.name)
REPO = Path(__file__).resolve().parents[3]


def test_hay_perfil_de_respaldo() -> None:
    assert FALLBACK_PROFILE in all_profiles()
    assert len(all_profiles()) >= 2, "además del respaldo tiene que haber al menos un proveedor real"


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
class TestContrato:
    def test_etiquetas_de_todos_los_importes(self, profile: ProfileSpec) -> None:
        for field in AMOUNT_FIELDS:
            assert profile.label_aliases(field), f"{profile.name}: sin alias para {field}"
            assert profile.label_aliases(field, "es"), f"{profile.name}: sin alias en algún idioma para {field}"

    def test_textos_de_saldo_insuficiente(self, profile: ProfileSpec) -> None:
        assert profile.insufficient_texts, f"{profile.name}: sin textos de saldo insuficiente"
        assert all(texts for texts in profile.insufficient_texts.values())

    def test_hay_forma_de_girar(self, profile: ProfileSpec) -> None:
        assert profile.spin_templates or profile.spin_hint or profile.spin_key

    def test_plantillas_legibles(self, profile: ProfileSpec) -> None:
        for path in profile.spin_templates:
            image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            assert image is not None and min(image.shape) >= 12, f"plantilla ilegible o diminuta: {path}"

    def test_detect_devuelve_confianza(self, profile: ProfileSpec) -> None:
        blank = np.zeros((768, 1366, 3), dtype=np.uint8)
        for url in ("", "https://example.com/juego", profile.demo_url or ""):
            assert 0.0 <= profile.detect(url, blank) <= 1.0

    def test_se_reconoce_su_propia_demo(self, profile: ProfileSpec) -> None:
        if not profile.demo_url:
            pytest.skip("perfil sin demo pública")
        assert resolve(profile.demo_url).name == profile.name

    def test_no_reclama_urls_ajenas(self, profile: ProfileSpec) -> None:
        for other in PROFILES:
            if other is not profile and other.demo_url:
                assert profile.detect(other.demo_url) < MIN_CONFIDENCE, f"{profile.name} reclama {other.name}"

    def test_patron_de_red_compila(self, profile: ProfileSpec) -> None:
        if profile.network_pattern:
            re.compile(profile.network_pattern)


def test_url_desconocida_usa_el_respaldo() -> None:
    assert resolve("https://proveedor-desconocido.example/game").name == FALLBACK_PROFILE


def test_ningun_proveedor_fuera_de_su_carpeta() -> None:
    """El núcleo no conoce proveedores: sus nombres solo pueden aparecer en su propia carpeta."""
    providers = [p.name for p in PROFILES if p.name != FALLBACK_PROFILE]
    profiles_dir = REPO / "betsson" / "profiles"
    offenders = []
    for path in (REPO / "betsson").rglob("*.py"):
        own_folder = path.relative_to(profiles_dir).parts[0] if profiles_dir in path.parents else None
        text = path.read_text(encoding="utf-8").lower()
        offenders += [f"{path.relative_to(REPO)}: {name}" for name in providers if name in text and own_folder != name]
    assert not offenders, offenders


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.name)
def test_cumple_el_protocol_de_core(profile: ProfileSpec) -> None:
    assert isinstance(profile, ProviderProfile)


def test_el_registro_cumple_el_protocol_de_core() -> None:
    from betsson.profiles.registry import REGISTRY

    assert isinstance(REGISTRY, ProviderRegistry)
