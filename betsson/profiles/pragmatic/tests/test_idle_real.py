"""Calibración del reposo con capturas reales de la demo (burbujas y agua en movimiento)."""
from __future__ import annotations

from pathlib import Path

import pytest

from betsson.game.sources import read_image
from betsson.vision.diff import change_ratio
from betsson.vision.idle import calibrate

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic"
IDLE = ["02_reposo.png", "04_fin_1.png", "06_fin_2.png", "08_fin_3.png"]  # misma pantalla en reposo

pytestmark = pytest.mark.unit


def test_reposo_real_sube_el_umbral_por_encima_de_las_burbujas() -> None:
    frames = [read_image(FIXTURES / n) for n in IDLE]
    cal = calibrate(frames, profile_threshold=0.01)  # el umbral por defecto del perfil genérico
    assert cal.reliable
    assert cal.start_threshold > cal.idle_max_vs_first  # el reposo nunca parece una tirada
    assert cal.stable_threshold >= cal.idle_max_step  # el reposo cuenta como quieto
    spinning = read_image(FIXTURES / "10_girando.png")
    assert change_ratio(frames[-1], spinning) > cal.start_threshold  # una tirada de verdad sí lo supera


def test_captura_real_quieta_deja_el_umbral_del_perfil() -> None:
    still = read_image(FIXTURES / "real-es" / "s1" / "02_apuesta_min.png")
    cal = calibrate([still] * 6, profile_threshold=0.12)
    assert cal.start_threshold == 0.12 and cal.stable_threshold == 0.12
