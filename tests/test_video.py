"""Repetición del escenario: GIF con los fotogramas del canvas (sin capturas de la web de Betsson)."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from betsson.core import CheckId, CheckResult, RunResult, Scenario
from betsson.report.html import render_run
from betsson.report.video import REPLAY_FILE, canvas_frames, make_replay

pytestmark = pytest.mark.unit


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (1366, 768)) -> None:
    Image.new("RGB", size, color).save(path)


def test_only_numbered_canvas_frames_in_capture_order(tmp_path: Path) -> None:
    _png(tmp_path / "010_read_balance.png", (0, 0, 255))
    _png(tmp_path / "002_spin_started.png", (0, 255, 0))
    _png(tmp_path / "001_read_bet.png", (255, 0, 0))
    _png(tmp_path / "betsson_balance.png", (9, 9, 9))  # web de Betsson: nunca entra
    _png(tmp_path / "session_limits_dialog.png", (9, 9, 9))
    assert [p.name for p in canvas_frames(tmp_path)] == ["001_read_bet.png", "002_spin_started.png",
                                                         "010_read_balance.png"]


def test_replay_gif_has_every_frame(tmp_path: Path) -> None:
    for i, color in enumerate([(255, 0, 0), (0, 255, 0), (0, 0, 255)], start=1):
        _png(tmp_path / f"{i:03d}_paso.png", color)
    path = make_replay(tmp_path)
    assert path == tmp_path / REPLAY_FILE
    with Image.open(path) as gif:
        assert gif.n_frames == 3 and gif.size[0] == 480


def test_no_replay_with_fewer_than_two_frames(tmp_path: Path) -> None:
    _png(tmp_path / "001_read_bet.png", (1, 2, 3))
    assert make_replay(tmp_path) is None


def test_report_shows_replay_only_when_it_exists(tmp_path: Path) -> None:
    run = RunResult(run_id="r", market="es", scenario=Scenario.S1,
                    results=(CheckResult.passed(CheckId.LOGIN_OK, "ok"),))
    assert "Repetición del escenario" not in render_run(run, tmp_path).read_text(encoding="utf-8")
    for i in (1, 2):
        _png(tmp_path / f"{i:03d}_paso.png", (i * 60, 0, 0))
    make_replay(tmp_path)
    html = render_run(run, tmp_path).read_text(encoding="utf-8")
    assert "Repetición del escenario" in html and 'src="replay.gif"' in html
