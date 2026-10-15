"""Informe HTML (Jinja2): uno por escenario junto a results.json y un índice por run."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from betsson.checks.common import LOGIN_ASSISTED_WARNING
from betsson.core import CheckId, RunResult
from betsson.report.video import REPLAY_FILE

TEMPLATES = Path(__file__).parent / "templates"
REPORT_FILE = "report.html"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["posix"] = lambda p: Path(p).as_posix()
_env.tests["image"] = lambda p: Path(p).suffix.lower() in IMAGE_SUFFIXES
_env.globals["LOGIN_ASSISTED_WARNING"] = LOGIN_ASSISTED_WARNING


def render_run(run: RunResult, out_dir: Path) -> Path:
    """report.html de un escenario. Las evidencias se enlazan relativas a out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    replay = REPLAY_FILE if (out_dir / REPLAY_FILE).exists() else None
    html = _env.get_template("run.html.j2").render(run=run, replay=replay)
    path = out_dir / REPORT_FILE
    path.write_text(html, encoding="utf-8")
    return path


def _cell(run: RunResult, check: CheckId) -> dict[str, str] | None:
    """Celda de la matriz: estado resumido y motivo (None si la comprobación no es de ese escenario)."""
    for r in run.results:
        if r.id is check:
            kind = r.failure_kind.value if r.failure_kind else None
            label = {"inconclusive": "INCONCLUSIVE", "provider_ui_changed": "PROVIDER_UI_CHANGED"}.get(kind or "", r.status)
            return {"label": label, "reason": r.reason}
    if check in run.missing_checks:
        return {"label": "INCONCLUSIVE", "reason": "sin resultado"}
    return None


def _matrix(entries: list[dict]) -> dict:
    """Comprobaciones (filas, en el orden de §3) × escenarios (columnas) para la portada."""
    runs = [e for e in entries if e["run"] is not None]
    present = {r.id for e in runs for r in e["run"].results} | {c for e in runs for c in e["run"].missing_checks}
    checks = [c for c in CheckId if c in present]
    rows = [{"check": c.value, "cells": [_cell(e["run"], c) for e in runs]} for c in checks]
    outcomes: dict[str, int] = {}
    for e in runs:
        outcomes[e["run"].outcome] = outcomes.get(e["run"].outcome, 0) + 1
    unreadable = len(entries) - len(runs)
    if unreadable:  # un results.json roto nunca deja la portada en verde
        outcomes["FAIL"] = outcomes.get("FAIL", 0) + unreadable
    return {"columns": runs, "rows": rows, "outcomes": outcomes}


def render_index(run_dir: Path) -> Path:
    """Índice de outputs/runs/<runId>/: todos los results.json de <market>/<escenario>/."""
    entries = []
    for results in sorted(run_dir.glob("*/*/results.json")):
        link = results.parent.relative_to(run_dir).as_posix() + "/" + REPORT_FILE
        try:
            entries.append({"run": RunResult.read_json(results), "link": link, "error": None})
        except ValueError as exc:  # un results.json roto no tumba el índice entero
            entries.append({"run": None, "link": link, "error": f"results.json ilegible ({type(exc).__name__})"})
    html = _env.get_template("index.html.j2").render(run_id=run_dir.name, entries=entries,
                                                     **_matrix(entries))
    path = run_dir / REPORT_FILE
    path.write_text(html, encoding="utf-8")
    return path
