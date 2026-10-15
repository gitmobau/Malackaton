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


def _run(out: Path, store: BaselineStore, frame: np.ndarray, run_id: str, betsson_after: str = "99.90"):
    registry = FakeRegistry()
    handle = FakeGameHandle(iframe_url=URL, frame=frame)
    site = FakeBetssonSite([reading("100.00"), reading(betsson_after)], out, handle=handle)
    eyes = FakeGameEyes(registry.profile, out, [reading("100.00"), reading("99.90")], reading("0.10"))
    return run_scenario(market=FakeMarket(), scenario=Scenario.S1, site=site, registry=registry,
                        eyes_factory=factory(eyes), slug="fake-slot", out_dir=out, run_id=run_id,
                        baselines=store)


def test_first_good_run_creates_baseline(tmp_path: Path) -> None:
    store = BaselineStore(tmp_path / "baselines")
    run = _run(tmp_path / "r1", store, game_frame(), "r1")
    assert run.outcome == "PASS"
    assert any("creada" in w for w in run.warnings)
    assert store.load("es", "fake-slot-S1") is not None


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
    saved, _ = store.load("es", "fake-slot-S1")
    assert saved.run_id == "r1"


def test_without_store_there_is_no_fingerprint(tmp_path: Path) -> None:
    registry = FakeRegistry()
    site = FakeBetssonSite([reading("100.00"), reading("99.80")], tmp_path)
    eyes = FakeGameEyes(registry.profile, tmp_path, [reading("100.00"), reading("99.80")], reading("0.20"))
    run = run_scenario(market=FakeMarket(), scenario=Scenario.S1, site=site, registry=registry,
                       eyes_factory=factory(eyes), slug="fake-slot", out_dir=tmp_path, run_id="r")
    assert not any("huella" in w for w in run.warnings)


def test_token_like_path_segments_are_masked() -> None:
    url = "https://games.example.test/launch/4f9c2a7be1d04c3a9b8e7f6a5d4c3b2a/index.html?x=1"
    assert iframe_path(url) == "https://games.example.test/launch/*/index.html"


def test_market_and_game_names_cannot_escape_store(tmp_path: Path) -> None:
    store = BaselineStore(tmp_path / "b")
    f = take(game_frame(), iframe_url=URL, market="../x", game="../../evil", provider=None, run_id="r")
    store.save(f, game_frame())
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files and all((tmp_path / "b") in p.parents for p in files)


def test_different_canvas_shape_is_not_comparable(tmp_path: Path) -> None:
    from betsson.report.fingerprint import check_drift

    store = BaselineStore(tmp_path / "b")
    store.save(fp(game_frame()), game_frame())
    narrow = game_frame()[:, :700]
    warnings, evidence = check_drift(store, narrow, fp(narrow), tmp_path / "out", update=False)
    assert any("no comparable" in w for w in warnings) and evidence == ()



def test_s1_and_s2_have_separate_baselines(tmp_path: Path) -> None:
    """Run real: S2 (saldo 0,00) se comparó con la huella de S1 (99,70) y dio un falso aviso."""
    from tests.test_scenarios import run_s2

    store = BaselineStore(tmp_path / "baselines")
    _run(tmp_path / "s1", store, game_frame("a"), "r1")
    registry = FakeRegistry()
    handle = FakeGameHandle(iframe_url=URL, frame=game_frame("b"))
    from betsson.core import Message
    msg = Message(text="Fondos insuficientes", lang_detected="es", matches_insufficient=True)
    site = FakeBetssonSite([reading("0.00"), reading("0.00")], tmp_path / "s2", handle=handle)
    eyes = FakeGameEyes(registry.profile, tmp_path / "s2", [reading("0.00"), reading("0.00")], reading("0.10"),
                        message=msg, spin_starts=False)
    run = run_scenario(market=FakeMarket(), scenario=Scenario.S2, site=site, registry=registry,
                       eyes_factory=factory(eyes), slug="fake-slot", out_dir=tmp_path / "s2", run_id="r2",
                       baselines=store)
    assert not any("ha cambiado" in w for w in run.warnings)
    assert store.load("es", "fake-slot-S2") is not None
