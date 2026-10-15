"""La traza pausada no guarda NADA de lo que pasa durante el login, tampoco la red.

Regresión del 15-oct: con stop_chunk/start_chunk el cuerpo del POST del login (usuario y
contraseña) acababa en el trace.zip. Sin red: la "web" es una página local servida con route.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

from betsson.site.tracing import SegmentedTrace, trace_paused

ORIGIN = "https://betsson.test"
SECRET = "Zx9-secreto-de-prueba-81"
FORM = """<input id='u'><input id='p' type='password'>
<button id='send' onclick="fetch('/api/login', {method: 'POST', body: JSON.stringify(
  {username: document.getElementById('u').value, password: document.getElementById('p').value})})
  .then(() => document.body.insertAdjacentHTML('beforeend', '<p id=done>ok</p>'))">Entrar</button>"""


def _serve(page: Page) -> None:
    page.route(f"{ORIGIN}/", lambda route: route.fulfill(status=200, content_type="text/html", body=FORM))
    page.route(f"{ORIGIN}/api/**", lambda route: route.fulfill(status=403, content_type="application/json", body="{}"))


def _login(page: Page) -> None:
    page.fill("#u", "usuario-" + SECRET)
    page.fill("#p", SECRET)
    page.click("#send")
    page.locator("#done").wait_for()
    page.fill("#u", "")
    page.fill("#p", "")


def _zips_contain(out: Path, needle: str) -> bool:
    for path in out.glob("*.zip"):
        with zipfile.ZipFile(path) as zf:
            if any(needle.encode() in zf.read(name) for name in zf.namelist()):
                return True
    return False


@pytest.fixture()
def page_and_context(browser: Browser):
    context = browser.new_context()
    page = context.new_page()
    _serve(page)
    yield page, context
    context.close()


def test_paused_trace_keeps_login_out_of_every_file(page_and_context, tmp_path: Path) -> None:
    page, context = page_and_context
    trace = SegmentedTrace(context, tmp_path)
    page.goto(f"{ORIGIN}/")
    with trace_paused(trace):
        _login(page)
    page.reload()  # actividad después del login: tiene que seguir grabándose
    trace.close()

    assert sorted(p.name for p in tmp_path.glob("*.zip")) == ["trace-0.zip", "trace-1.zip"]
    assert not _zips_contain(tmp_path, SECRET)


def test_unpaused_trace_would_leak(page_and_context, tmp_path: Path) -> None:
    """Control: sin pausa el secreto sí aparece, así que el test anterior mide algo real."""
    page, context = page_and_context
    trace = SegmentedTrace(context, tmp_path)
    page.goto(f"{ORIGIN}/")
    _login(page)
    trace.close()

    assert _zips_contain(tmp_path, SECRET)
