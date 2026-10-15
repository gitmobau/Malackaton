"""Huella de referencia por juego: aviso cuando el juego del proveedor cambia entre ejecuciones."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from betsson.checks.scenario import run_scenario
from betsson.core import Scenario
from betsson.report.fingerprint import BaselineStore, compare, iframe_path, take
from tests.fakes import FakeBetssonSite, FakeGameEyes, FakeGameHandle, FakeMarket, FakeRegistry, factory, reading

pytestmark = pytest.mark.unit

URL = "https://games.example.test/fake-provider/slot/v1/index.html?token=SECRETO&lang=es"


def game_frame(controls: str = "a", reels_seed: int = 0) -> np.ndarray:
    """Canvas 768x1366: rodillos aleatorios arriba y franja de controles abajo."""
    rng = np.random.default_rng(reels_seed)
    frame = np.zeros((768, 1366, 3), dtype=np.uint8)
    frame[:600] = rng.integers(0, 255, size=(600, 1366, 3), dtype=np.uint8)
    band = frame[620:]
    if controls == "a":
        band[:, :400] = (200, 30, 30)
        band[40:100, 600:760] = (240, 240, 240)  # botón de girar
    else:
        band[:, 900:] = (30, 30, 200)
        band[20:140, 100:300] = (250, 250, 0)
    return frame


def fp(frame: np.ndarray, url: str = URL, run_id: str = "r1"):
    return take(frame, iframe_url=url, market="es", game="fake-slot", provider="fake-provider", run_id=run_id)


def test_iframe_path_drops_query_and_tokens() -> None:
    assert iframe_path(URL) == "https://games.example.test/fake-provider/slot/v1/index.html"
    assert "SECRETO" not in fp(game_frame()).model_dump_json()


def test_same_game_after_another_spin_is_not_a_change() -> None:
    assert compare(fp(game_frame(reels_seed=1)), fp(game_frame(reels_seed=2))) == []


def test_new_session_token_is_not_a_change() -> None:
    assert compare(fp(game_frame()), fp(game_frame(), url=URL.replace("SECRETO", "OTRO"))) == []


def test_controls_redesign_is_a_change() -> None:
    reasons = compare(fp(game_frame("a")), fp(game_frame("b")))
    assert any("controles" in r for r in reasons)


def test_new_game_version_path_is_a_change() -> None:
    reasons = compare(fp(game_frame()), fp(game_frame(), url=URL.replace("/v1/", "/v2/")))
    assert any("ruta del juego" in r for r in reasons)


def _run(out: Path, store: BaselineStore, frame: np.ndarray, run_id: str, betsson_after: str = "99.80"):
    registry = FakeRegistry()
    handle = FakeGameHandle(iframe_url=URL, frame=frame)
    site = FakeBetssonSite([reading("100.00"), reading(betsson_after)], out, handle=handle)
    eyes = FakeGameEyes(registry.profile, out, [reading("100.00"), reading("99.80")], reading("0.20"))
    return run_scenario(market=FakeMarket(), scenario=Scenario.S1, site=site, registry=registry,
                        eyes_factory=factory(eyes), slug="fake-slot", out_dir=out, run_id=run_id,
                        baselines=store)


def test_first_good_run_creates_baseline(tmp_path: Path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    run = _run(tmp_path / "r1", store, game_frame(), "r1")
    assert run.outcome == "PASS"
    assert any("creada" in w for w in run.warnings)
    assert store.load("es", "fake-slot") is not None


def test_changed_game_warns_with_before_and_after_but_keeps_verdict(tmp_path: Path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    _run(tmp_path / "r1", store, game_frame("a"), "r1")
    run = _run(tmp_path / "r2", store, game_frame("b"), "r2")
    assert run.verdict == "PASS"
    assert any("ha cambiado desde la última ejecución (r1)" in w for w in run.warnings)
    assert {p.name for p in run.evidence} == {"fingerprint_before.png", "fingerprint_now.png"}
    assert all((tmp_path / "r2" / p).exists() for p in run.evidence)
    assert "fingerprint_now.png" in (tmp_path / "r2" / "report.html").read_text(encoding="utf-8")


def test_failed_run_does_not_replace_baseline(tmp_path: Path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    _run(tmp_path / "r1", store, game_frame("a"), "r1")
    bad = _run(tmp_path / "r2", store, game_frame("b"), "r2", betsson_after="100.00")
    assert bad.outcome == "FAIL"
    saved, _ = store.load("es", "fake-slot")
    assert saved.run_id == "r1"


def test_without_store_there_is_no_fingerprint(tmp_path: Path) -> None:
    registry = FakeRegistry()
    site = FakeBetssonSite([reading("100.00"), reading("99.80")], tmp_path)
    eyes = FakeGameEyes(registry.profile, tmp_path, [reading("100.00"), reading("99.80")], reading("0.20"))
    run = run_scenario(market=FakeMarket(), scenario=Scenario.S1, site=site, registry=registry,
                       eyes_factory=factory(eyes), slug="fake-slot", out_dir=tmp_path, run_id="r")
    assert not any("huella" in w for w in run.warnings)
