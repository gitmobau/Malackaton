"""Punto de entrada único de la demo (betsson.site.run): sin red, sin navegador y sin sesiones."""
from __future__ import annotations

import argparse

import pytest

from betsson.site import run

pytestmark = pytest.mark.unit


def test_parse_scenarios_normalises_and_rejects_unknown() -> None:
    assert run.parse_scenarios(" S2, s1 ,s1") == ["s1", "s2"]
    for bad in ("", "s3", "s1,x"):
        with pytest.raises(argparse.ArgumentTypeError):
            run.parse_scenarios(bad)


def test_pytest_command_is_private_and_filtered() -> None:
    both = run.pytest_command("es", ["s1", "s2"])
    assert "-k" not in both
    assert both[both.index("--tracing") + 1] == "off" and both[both.index("--video") + 1] == "off"
    only_s2 = run.pytest_command("es", ["s2"])
    assert only_s2[-2:] == ["-k", "real_s2"]


def test_accounts_follow_s2_plan_b(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S2_ACCOUNT", raising=False)
    assert run.accounts_for(["s1", "s2"]) == ["empty", "funded"]
    monkeypatch.setenv("S2_ACCOUNT", "funded")
    assert run.accounts_for(["s1", "s2"]) == ["funded"]


def test_no_session_stops_before_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run.BrowserSession, "is_listening", lambda self: False)
    monkeypatch.setattr(run.subprocess, "call", lambda *a, **k: pytest.fail("no debe ejecutar pytest sin sesión"))
    assert run.main(["--market", "es", "--scenarios", "s1", "--game", "big-bass-splash", "--no-open"]) == 2
