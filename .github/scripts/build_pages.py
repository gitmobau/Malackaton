"""Construye la web del informe (GitHub Pages) a partir de las evidencias ya escaneadas.

Entrada: carpeta con un subdirectorio por artifact `evidencias-<mercado>-<runId>` (download-artifact).
Salida: carpeta lista para Pages con un index.html que enlaza los informes y results.json de cada mercado.
Solo copia HTML, JSON e imágenes: trazas (.zip) y vídeos (.webm) nunca se publican.
No conoce el formato de results.json (es del área C): cuenta los valores "PASS"/"FAIL" que encuentre.
Uso: python build_pages.py <entrada> <salida>
"""
from __future__ import annotations

import html
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PUBLISHABLE = {".html", ".json", ".png", ".jpg", ".jpeg", ".css", ".svg"}
ARTIFACT_PREFIX = "evidencias-"
OUTCOME_KEY = "outcome"  # results.json de un escenario (área C): PASS/FAIL/INCONCLUSIVE/PROVIDER_UI_CHANGED


def copy_publishable(src: Path, dst: Path) -> list[Path]:
    copied: list[Path] = []
    for file in sorted(src.rglob("*")):
        if file.is_file() and file.suffix.lower() in PUBLISHABLE:
            target = dst / file.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
            copied.append(target.relative_to(dst.parent))
    return copied


def summarize(files: list[Path], site: Path) -> Counter[str]:
    """Un escenario = un results.json: cuenta su "outcome" de nivel superior."""
    counter: Counter[str] = Counter()
    for rel in files:
        if rel.name != "results.json":
            continue
        try:
            data = json.loads((site / rel).read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            counter["ilegible"] += 1
            continue
        outcome = data.get(OUTCOME_KEY) if isinstance(data, dict) else None
        counter[str(outcome).upper() if outcome else "sin outcome"] += 1
    return counter


def market_section(name: str, files: list[Path], counter: Counter[str]) -> str:
    # Primero el índice de C (runs/<runId>/report.html, el de ruta más corta), luego cada escenario.
    links = sorted((f for f in files if f.name in ("report.html", "results.json")), key=lambda f: (len(f.parts), f.as_posix()))
    items = "".join(
        f'<li><a href="{html.escape(f.as_posix())}">{html.escape(f.as_posix())}</a></li>' for f in links
    ) or "<li>Sin informe todavía (el área C lo genera en outputs/runs/&lt;runId&gt;/).</li>"
    badge = " · ".join(f"{k}: {v}" for k, v in sorted(counter.items())) or "sin resultados"
    return f"<section><h2>{html.escape(name)}</h2><p class=\"badge\">{html.escape(badge)}</p><ul>{items}</ul></section>"


def render_index(sections: list[str]) -> str:
    run_url = os.getenv("RUN_URL", "")
    meta = (
        f"Generado {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · commit {html.escape(os.getenv('GITHUB_SHA', '-')[:7])}"
        f" · mercados pedidos: {html.escape(os.getenv('MARKETS', '-') or 'ninguno')}"
    )
    run_link = f' · <a href="{html.escape(run_url)}">ejecución en Actions</a>' if run_url else ""
    body = "".join(sections) or "<p>Esta ejecución no tiene mercados activos ni evidencias publicadas.</p>"
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Validación de juegos · Betsson</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;padding:0 16px;color:#1b1b1b;background:#fff}}
section{{border:1px solid #ddd;border-radius:8px;padding:1rem;margin:1rem 0}}
.badge{{font-weight:600}} .meta{{color:#555;font-size:.9rem}}
</style></head><body>
<h1>Validación de juegos · Betsson</h1>
<p class="meta">{meta}{run_link}</p>
<p class="meta">Solo informes y resultados: las trazas y los vídeos no se publican aquí.</p>
{body}
</body></html>
"""


def main(src_dir: str, out_dir: str) -> int:
    src, site = Path(src_dir), Path(out_dir)
    site.mkdir(parents=True, exist_ok=True)
    sections: list[str] = []
    artifacts = sorted(p for p in src.glob(f"{ARTIFACT_PREFIX}*") if p.is_dir()) if src.exists() else []
    for artifact in artifacts:
        name = artifact.name.removeprefix(ARTIFACT_PREFIX)
        files = copy_publishable(artifact, site / name)
        sections.append(market_section(name, files, summarize(files, site)))
    (site / "index.html").write_text(render_index(sections), encoding="utf-8")
    print(f"Web del informe en {site}: {len(artifacts)} mercados.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
