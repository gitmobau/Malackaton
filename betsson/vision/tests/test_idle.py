"""Calibración de la animación de reposo con un juego sintético muy animado (sin proveedores)."""
from __future__ import annotations

from decimal import Decimal

import cv2
import numpy as np
import pytest

from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource
from betsson.profiles.registry import get_profile
from betsson.vision.diff import change_ratio
from betsson.vision.idle import MAX_START_THRESHOLD, calibrate

pytestmark = pytest.mark.unit


class _Market:
    id, currency_code, language, money_tolerance = "demo", "EUR", "es", Decimal("0.01")


def animated_game(frames: int, seed: int = 0) -> list[np.ndarray]:
    """Juego sintético animado en reposo: 12 círculos grandes que se desplazan un poco en cada fotograma."""
    rng = np.random.default_rng(seed)
    centers = rng.integers((200, 120), (1166, 640), (12, 2))
    colors = rng.integers(0, 255, (12, 3))
    out = []
    for _ in range(frames):
        frame = np.full((768, 1366, 3), 60, dtype=np.uint8)
        centers = centers + rng.integers(-25, 26, centers.shape)
        for (x, y), color in zip(centers, colors):
            cv2.circle(frame, (int(x), int(y)), 45, tuple(int(c) for c in color), -1)
        out.append(frame)
    return out


def test_juego_animado_el_umbral_fijo_se_dispararia_y_el_calibrado_no() -> None:
    idle = animated_game(6)
    cal = calibrate(idle, profile_threshold=0.01)
    assert change_ratio(idle[0], idle[1]) > 0.01  # el umbral fijo del 1 % vería una "tirada"
    assert cal.reliable and cal.start_threshold > 0.01
    assert all(change_ratio(idle[-1], f) <= cal.start_threshold for f in idle)


def test_spin_en_juego_animado_sin_tirada_false_y_con_tirada_true() -> None:
    profile = get_profile("generic-vision")
    quick = profile.model_copy(update={"spin_end": profile.spin_end.model_copy(update={"start_timeout_s": 0.5})})
    eyes = GameEyes(FileFrameSource(animated_game(6) + animated_game(6, seed=0)[2:4] * 3), quick, _Market())
    assert eyes.spin() is False  # solo animación de reposo
    assert eyes.idle_calibration is not None and eyes.idle_calibration.start_threshold > 0.01
    spinning = np.full((768, 1366, 3), 250, dtype=np.uint8)  # cambia casi toda la pantalla
    eyes2 = GameEyes(FileFrameSource(animated_game(6) + [spinning]), quick, _Market())
    assert eyes2.spin() is True


def test_quieto_deja_el_umbral_del_perfil() -> None:
    still = np.full((300, 400, 3), 120, dtype=np.uint8)
    cal = calibrate([still] * 6, profile_threshold=0.05)
    assert cal.start_threshold == 0.05 and cal.stable_threshold == 0.05 and cal.idle_max_step == 0


def test_calibracion_poco_fiable_si_el_reposo_cambia_casi_todo() -> None:
    frames = [np.full((300, 400, 3), v, dtype=np.uint8) for v in (0, 255, 0, 255)]
    cal = calibrate(frames, profile_threshold=0.01)
    assert not cal.reliable and cal.start_threshold == MAX_START_THRESHOLD
    assert "poco fiable" in cal.summary()
