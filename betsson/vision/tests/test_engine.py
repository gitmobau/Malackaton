"""Tests del motor genérico con datos sintéticos (sin OCR real ni navegador)."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from betsson.vision.anchors import find_amount
from betsson.vision.diff import change_ratio
from betsson.vision.ocr import TextBox, normalize
from betsson.vision.template import find_template


def box(text: str, x0: int, y0: int, x1: int, y1: int, score: float = 0.95) -> TextBox:
    return TextBox(text, score, x0, y0, x1, y1)


class TestAnclas:
    def test_etiqueta_y_valor_en_la_misma_caja(self) -> None:
        found = find_amount([box("CREDIT 100,000.00 €", 10, 700, 200, 720)], ["CREDIT"])
        assert found is not None and found.value_text == "100,000.00 €" and found.strategy == "inline"

    def test_valor_a_la_derecha(self) -> None:
        boxes = [box("APUESTA", 500, 700, 560, 720), box("1,00 €", 570, 700, 620, 720), box("9,99", 900, 700, 950, 720)]
        found = find_amount(boxes, ["APUESTA"])
        assert found is not None and found.value_text == "1,00 €" and found.strategy == "right"

    def test_valor_debajo(self) -> None:
        boxes = [box("SALDO", 50, 600, 100, 615), box("1.234,56 €", 40, 620, 120, 640)]
        found = find_amount(boxes, ["SALDO"])
        assert found is not None and found.value_text == "1.234,56 €" and found.strategy == "below"

    def test_tildes_y_mayusculas_dan_igual(self) -> None:
        found = find_amount([box("Crédito: 5,00 €", 0, 0, 100, 20)], ["CRÉDITO"])
        assert found is not None and found.value_text == "5,00 €"

    def test_no_confunde_bet_con_betsson(self) -> None:
        assert find_amount([box("BETSSON 2026", 0, 0, 100, 20)], ["BET"]) is None

    def test_sin_etiqueta_no_inventa(self) -> None:
        assert find_amount([box("12,00 €", 0, 0, 50, 20)], ["SALDO"]) is None

    def test_la_pista_desempata(self) -> None:
        boxes = [box("WIN 5.00", 600, 300, 700, 320, 0.99), box("WIN 0.20", 600, 700, 700, 720, 0.90)]
        found = find_amount(boxes, ["WIN"], hint=(500, 650, 800, 768))
        assert found is not None and found.value_text == "0.20"

    def test_normalize(self) -> None:
        assert normalize("  Crédito   total ") == "CREDITO TOTAL"


class TestDiff:
    def test_iguales_no_cambian(self) -> None:
        frame = np.full((768, 1366, 3), 80, dtype=np.uint8)
        assert change_ratio(frame, frame.copy()) == 0.0

    def test_cambio_grande(self) -> None:
        a = np.zeros((768, 1366, 3), dtype=np.uint8)
        b = a.copy()
        b[100:500, 200:900] = 255
        assert change_ratio(a, b) > 0.2

    def test_ruido_leve_no_cuenta(self) -> None:
        rng = np.random.default_rng(0)
        a = np.full((768, 1366, 3), 120, dtype=np.uint8)
        b = np.clip(a.astype(int) + rng.integers(-5, 6, a.shape), 0, 255).astype(np.uint8)
        assert change_ratio(a, b) < 0.004


def _spin_button(size: int) -> np.ndarray:
    tile = np.zeros((size, size, 3), dtype=np.uint8)
    c = size // 2
    cv2.circle(tile, (c, c), int(size * 0.45), (240, 240, 240), max(2, size // 12))
    cv2.ellipse(tile, (c, c), (int(size * 0.25), int(size * 0.25)), 0, 30, 300, (240, 240, 240), max(2, size // 14))
    return tile


class TestPlantilla:
    def test_encuentra_el_boton_a_otra_escala(self, tmp_path: Path) -> None:
        template_path = tmp_path / "spin.png"
        cv2.imwrite(str(template_path), _spin_button(80))
        frame = np.full((768, 1366, 3), 30, dtype=np.uint8)
        frame[300:404, 1150:1254] = _spin_button(104)  # 1.3x
        match = find_template(frame, [template_path])
        assert match is not None
        assert abs(match.center[0] - 1202 / 1366) < 0.02 and abs(match.center[1] - 352 / 768) < 0.03

    def test_sin_boton_devuelve_none(self, tmp_path: Path) -> None:
        template_path = tmp_path / "spin.png"
        cv2.imwrite(str(template_path), _spin_button(80))
        frame = np.full((768, 1366, 3), 30, dtype=np.uint8)
        assert find_template(frame, [template_path]) is None
