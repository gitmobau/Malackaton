"""Resistencia a cambios del proveedor: el perfil sigue leyendo con capturas alteradas.

Simula lo que cambia sin aviso en un juego de terceros: la interfaz se desplaza, el canvas se
reescala (otro viewport o DPR), cambian los colores o el brillo, o llega más comprimido.
Las anclas son la etiqueta visible y la forma de los botones, no posiciones ni colores fijos.
"""
from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
import pytest

from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.profiles.base import ProfileSpec
from betsson.profiles.pragmatic.tests.test_fixtures import FIXTURES, EurEsReader, FakeMarket
from betsson.profiles.registry import ensure_recognized, get_profile
from betsson.vision.template import find_template

pytestmark = [pytest.mark.unit, pytest.mark.slow]  # ~3,5 min de OCR

Mutation = Callable[[np.ndarray], np.ndarray]


def shift(dx: int, dy: int) -> Mutation:
    """Desplaza toda la interfaz (p. ej. una barra nueva arriba o a la izquierda)."""

    def apply(frame: np.ndarray) -> np.ndarray:
        matrix = np.float32([[1, 0, dx], [0, 1, dy]])
        return cv2.warpAffine(frame, matrix, (frame.shape[1], frame.shape[0]), borderValue=(20, 20, 20))

    return apply


def rescale(factor: float) -> Mutation:
    """Canvas más pequeño o más grande (otro viewport, DPR o zoom)."""
    return lambda frame: cv2.resize(frame, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)


def hue_shift(degrees: int) -> Mutation:
    """Cambio de paleta (tema nuevo del juego)."""

    def apply(frame: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv[..., 0] = (hsv[..., 0].astype(int) + degrees // 2) % 180
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    return apply


def brightness(factor: float) -> Mutation:
    return lambda frame: np.clip(frame.astype(np.float32) * factor, 0, 255).astype(np.uint8)


def jpeg(quality: int) -> Mutation:
    def apply(frame: np.ndarray) -> np.ndarray:
        _, data = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    return apply


MUTATIONS: dict[str, Mutation] = {
    "desplazada_40px": shift(40, -25),
    "desplazada_-60px": shift(-60, -20),
    "reescalada_0.8": rescale(0.8),
    "reescalada_1.25": rescale(1.25),
    "tono_+90": hue_shift(90),
    "mas_oscura_0.7": brightness(0.7),
    "jpeg_q40": jpeg(40),
}

# (captura, crédito, apuesta, ganancia)
CASES = [
    ("04_fin_1.png", "100000.00", "2.00", "0"),
    ("13_fin_ganancia.png", "99990.00", "2.00", "2.00"),
]


@pytest.fixture(scope="module")
def profile() -> ProfileSpec:
    return get_profile("pragmatic")


def _amount(reading) -> str | None:  # noqa: ANN001 - Reading
    return str(reading.money.amount) if reading.money else None


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
@pytest.mark.parametrize("case", CASES, ids=lambda c: c[0])
def test_lee_importes_con_la_captura_alterada(profile: ProfileSpec, case: tuple[str, ...], mutation: str) -> None:
    name, balance, bet, win = case
    frame = MUTATIONS[mutation](read_image(FIXTURES / name))
    eyes = GameEyes(FileFrameSource([frame]), profile, FakeMarket(), money_reader=EurEsReader())
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    got = tuple(_amount(r) for r in readings)
    # Lo único aceptable además del valor correcto es "no concluyente" (None), nunca otro importe.
    wrong = [g for g, e in zip(got, (balance, bet, win)) if g is not None and g != e]
    assert not wrong, f"{mutation}: importe equivocado {got} (esperado {(balance, bet, win)})"
    assert got == (balance, bet, win), f"{mutation}: no concluyente {got} -> {[r.reason for r in readings]}"


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_encuentra_los_botones_con_la_captura_alterada(profile: ProfileSpec, mutation: str) -> None:
    frame = MUTATIONS[mutation](read_image(FIXTURES / "04_fin_1.png"))
    for templates in (profile.spin_templates, profile.bet_down.templates, profile.bet_up.templates):
        assert find_template(frame, templates) is not None, f"{mutation}: no encuentra {templates[0].name}"


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_el_registro_sigue_reconociendo_el_juego(profile: ProfileSpec, mutation: str) -> None:
    ensure_recognized(profile, MUTATIONS[mutation](read_image(FIXTURES / "04_fin_1.png")))


def test_barra_cortada_por_el_borde_no_inventa_importes(profile: ProfileSpec) -> None:
    """Si la barra inferior queda medio fuera del canvas, lo que no se lee entero es no concluyente."""
    frame = shift(40, 30)(read_image(FIXTURES / "04_fin_1.png"))
    eyes = GameEyes(FileFrameSource([frame]), profile, FakeMarket(), money_reader=EurEsReader())
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    got = tuple(_amount(r) for r in readings)
    assert all(g in (expected, None) for g, expected in zip(got, ("100000.00", "2.00", "0"))), got


def test_lectura_sobre_un_juego_irreconocible_no_inventa_importes(profile: ProfileSpec) -> None:
    """Una interfaz totalmente distinta (aquí, ruido) da no concluyente, nunca un importe."""
    noise = np.random.default_rng(1).integers(0, 255, (768, 1366, 3), dtype=np.uint8)
    eyes = GameEyes(FileFrameSource([noise]), profile, FakeMarket(), money_reader=EurEsReader())
    assert all(r.money is None for r in (eyes.read_balance(noise), eyes.read_bet(noise), eyes.read_win(noise)))
