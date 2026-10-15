"""Test ficticio del esqueleto: comprueba que el entorno compartido importa todo.

El área C puede borrarlo cuando haya tests reales.
"""
import importlib

import pytest

DEPENDENCIAS = ["cv2", "rapidocr_onnxruntime", "pydantic", "imagehash", "jinja2", "playwright", "PIL", "numpy"]


@pytest.mark.unit
@pytest.mark.parametrize("modulo", DEPENDENCIAS)
def test_dependencia_importa(modulo: str) -> None:
    importlib.import_module(modulo)


@pytest.mark.unit
def test_paquete_betsson_importa() -> None:
    for area in ["site", "market", "game", "vision", "profiles", "core", "checks", "report"]:
        importlib.import_module(f"betsson.{area}")
