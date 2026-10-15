"""Configuración común de pytest para todas las áreas.

- Navegador como un jugador: viewport 1366x768 y DPR 1.
- Mercado con --market (por defecto "es") o la variable MARKET.
- Evidencias en outputs/runs/<runId>/<market>/<scenario>/.
- La traza de Playwright graba lo que se escribe: el login debe pausarla
  (context.tracing.stop_chunk / start_chunk) y tapar los campos.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
VIEWPORT = {"width": 1366, "height": 768}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--market",
        default=os.getenv("MARKET", "es"),
        help="Mercado: id de config/markets/<mercado>.json",
    )


@pytest.fixture(scope="session")
def market_id(pytestconfig: pytest.Config) -> str:
    return pytestconfig.getoption("--market")


@pytest.fixture(scope="session")
def run_id() -> str:
    return os.getenv("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@pytest.fixture
def evidence_dir(run_id: str, market_id: str, request: pytest.FixtureRequest) -> Path:
    """Carpeta de evidencias de la prueba actual. El nombre del escenario sale del test."""
    path = ROOT / "outputs" / "runs" / run_id / market_id / request.node.name
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    return {**browser_context_args, "viewport": VIEWPORT, "device_scale_factor": 1}
