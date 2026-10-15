"""Informe HTML (Jinja2): uno por escenario junto a results.json y un índice por run."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from betsson.core import RunResult

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


def render_run(run: RunResult, out_dir: Path) -> Path:
    """report.html de un escenario. Las evidencias se enlazan relativas a out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    html = _env.get_template("run.html.j2").render(run=run)
    path = out_dir / REPORT_FILE
    path.write_text(html, encoding="utf-8")
    return path


def render_index(run_dir: Path) -> Path:
    """Índice de outputs/runs/<runId>/: todos los results.json de <market>/<escenario>/."""
    entries = []
    for results in sorted(run_dir.glob("*/*/results.json")):
        run = RunResult.read_json(results)
        entries.append({"run": run, "link": results.parent.relative_to(run_dir).as_posix() + "/" + REPORT_FILE})
    html = _env.get_template("index.html.j2").render(run_id=run_dir.name, entries=entries)
    path = run_dir / REPORT_FILE
    path.write_text(html, encoding="utf-8")
    return path
