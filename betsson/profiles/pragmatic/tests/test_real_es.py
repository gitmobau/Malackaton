"""Capturas de Real Play en betsson.es (es-ES, EUR), con el parse_money real del mercado.

- s1/: una tirada real con la apuesta mínima (15-oct). 100,00 - 0,10 + 0 = 99,90 leído en pantalla.
  Se tapó la franja inferior izquierda (hora e identificador de la jugada).
- s2/: cuenta sin saldo (capturas del área A): el juego rechaza la tirada con "Fondos insuficientes…".
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from betsson.game.eyes import GameEyes
from betsson.game.sources import FileFrameSource, read_image
from betsson.market import load_market
from betsson.profiles.base import ProfileSpec
from betsson.profiles.registry import ensure_recognized, get_profile, resolve
from betsson.vision.geometry import contains

REAL = Path(__file__).resolve().parents[4] / "fixtures" / "pragmatic" / "real-es"
# (captura, crédito, apuesta, ganancia) leídos con parse_money del mercado es
S1 = [
    ("004_credito_99_90.png", "99.90", "0.10", "0"),  # run real 17:32: cajas de CRÉDITO y valor solapadas
    ("01_reposo_apuesta_2.png", "100.00", "2.00", "0"),
    ("02_apuesta_min.png", "100.00", "0.10", "0"),
    ("04_fin_sin_premio.png", "99.90", "0.10", "0"),
]

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def profile() -> ProfileSpec:
    return get_profile("pragmatic")


def eyes_for(profile: ProfileSpec, path: Path):  # noqa: ANN201 - (GameEyes, frame)
    frame = read_image(path)
    return GameEyes(FileFrameSource([frame]), profile, load_market("es")), frame


@pytest.mark.parametrize(("name", "balance", "bet", "win"), S1)
def test_s1_lecturas_reales_en_eur(profile: ProfileSpec, name: str, balance: str, bet: str, win: str) -> None:
    eyes, frame = eyes_for(profile, REAL / "s1" / name)
    readings = (eyes.read_balance(frame), eyes.read_bet(frame), eyes.read_win(frame))
    assert tuple(str(r.money.amount) if r.money else None for r in readings) == (balance, bet, win), readings
    assert all(r.money.currency == "EUR" for r in readings)
    assert readings[0].currency_seen and readings[1].currency_seen  # la moneda se VE en pantalla


def test_s1_regla_del_saldo_en_pantalla(profile: ProfileSpec) -> None:
    before_eyes, before = eyes_for(profile, REAL / "s1" / "02_apuesta_min.png")
    after_eyes, after = eyes_for(profile, REAL / "s1" / "04_fin_sin_premio.png")
    start, bet = before_eyes.read_balance(before).money, before_eyes.read_bet(before).money
    end, win = after_eyes.read_balance(after).money, after_eyes.read_win(after).money
    assert start - bet + win == end
    assert end.amount == Decimal("99.90")


def test_se_reconoce_por_la_imagen_aunque_la_url_sea_otra(profile: ProfileSpec) -> None:
    """En betsson.es el iframe del juego no lleva la URL de la demo: el proveedor se reconoce por su botón."""
    frame = read_image(REAL / "s1" / "01_reposo_apuesta_2.png")
    assert resolve("srcdoc", frame).name == "pragmatic"
    ensure_recognized(profile, frame)


def test_s2_mensaje_real_de_fondos_insuficientes(profile: ProfileSpec) -> None:
    s2 = REAL / "s2"
    if not (s2 / "02_mensaje_fondos_insuficientes.png").exists():
        pytest.skip("capturas del S2 real (área A) aún no fusionadas")
    before_eyes, before = eyes_for(profile, s2 / "01_principal_credito_0.png")
    eyes, frame = eyes_for(profile, s2 / "02_mensaje_fondos_insuficientes.png")
    assert before_eyes.read_message(before).matches_insufficient is False
    message = eyes.read_message(frame)
    assert message.matches_insufficient is True and message.lang_detected == "es"
    assert eyes.read_balance(frame).money.amount == Decimal("0.00")  # el saldo no cambia


def test_s2_read_message_cierra_la_ventana_con_aceptar(profile: ProfileSpec) -> None:
    """Tras guardar la evidencia, pulsa ACEPTAR y comprueba que el aviso desaparece (petición de C)."""
    s2 = REAL / "s2"
    if not (s2 / "02_mensaje_fondos_insuficientes.png").exists():
        pytest.skip("capturas del S2 real (área A) aún no fusionadas")
    message_frame = read_image(s2 / "02_mensaje_fondos_insuficientes.png")
    after_frame = read_image(s2 / "01_principal_credito_0.png")  # la pantalla sin la ventana
    source = FileFrameSource([message_frame, after_frame])
    eyes = GameEyes(source, profile, load_market("es"))
    message = eyes.read_message(message_frame)
    assert message.matches_insufficient is True and message.reason is None
    ((fx, fy),) = source.clicks
    assert 0.40 < fx < 0.60 and 0.50 < fy < 0.66  # ACEPTAR, en el centro de la ventana


def test_s2_si_la_ventana_no_se_cierra_queda_dicho(profile: ProfileSpec) -> None:
    s2 = REAL / "s2"
    if not (s2 / "02_mensaje_fondos_insuficientes.png").exists():
        pytest.skip("capturas del S2 real (área A) aún no fusionadas")
    message_frame = read_image(s2 / "02_mensaje_fondos_insuficientes.png")
    eyes = GameEyes(FileFrameSource([message_frame]), profile, load_market("es"))
    message = eyes.read_message(message_frame)
    assert message.matches_insufficient is True and "no desapareció" in (message.reason or "")


def test_s2_sin_texto_del_boton_usa_la_pista_del_perfil(profile: ProfileSpec) -> None:
    """Si el OCR no lee ACEPTAR, se pulsa la pista de zona del perfil (nunca coordenadas fijas en el código)."""
    s2 = REAL / "s2"
    if not (s2 / "02_mensaje_fondos_insuficientes.png").exists():
        pytest.skip("capturas del S2 real (área A) aún no fusionadas")
    blind = profile.model_copy(update={"message_dismiss_texts": ["BOTON QUE NO EXISTE"]})
    source = FileFrameSource([read_image(s2 / "02_mensaje_fondos_insuficientes.png"), read_image(s2 / "01_principal_credito_0.png")])
    message = GameEyes(source, blind, load_market("es")).read_message()
    assert message.matches_insufficient is True and message.reason is None
    ((fx, fy),) = source.clicks
    assert contains(blind.message_dismiss_hint, (fx, fy))


# --- Run real del 15-oct (17:15): resolve() en la presentación con las flechas del gorila girando ---

PRESENTATION = REAL / "s1" / "00_presentacion_cargando.png"


def test_resolve_reconoce_la_presentacion_real(profile: ProfileSpec) -> None:
    frame = read_image(PRESENTATION)
    assert resolve("srcdoc", frame).name == "pragmatic"


def test_registry_recibe_rgb_del_handle_y_reconoce(profile: ProfileSpec) -> None:
    from betsson.profiles.registry import REGISTRY

    rgb = read_image(PRESENTATION)[:, :, ::-1]  # GameHandle.capture() da RGB
    assert REGISTRY.resolve("srcdoc", rgb).name == "pragmatic"
    REGISTRY.ensure_recognized(profile, rgb)  # su propia presentación cuenta como reconocida


class _FakeHandle:
    """GameHandle mínimo: primero carga (ruido) y después la presentación."""

    iframe_url = "srcdoc"

    def __init__(self, frames: list) -> None:  # noqa: ANN001
        self._frames, self._i = frames, 0

    def capture(self):  # noqa: ANN201
        frame = self._frames[min(self._i, len(self._frames) - 1)]
        self._i += 1
        return frame


def test_resolve_handle_reintenta_mientras_carga() -> None:
    import numpy as np

    from betsson.profiles.registry import REGISTRY

    loading = np.zeros((651, 1158, 3), dtype=np.uint8)
    handle = _FakeHandle([loading, loading, read_image(PRESENTATION)[:, :, ::-1]])
    assert REGISTRY.resolve_handle(handle, timeout_s=30).name == "pragmatic"
    assert REGISTRY.resolve_handle(_FakeHandle([loading]), timeout_s=0.5).name == "generic-vision"


def test_dismiss_intro_espera_al_juego_listo(profile: ProfileSpec) -> None:
    intro, game = read_image(PRESENTATION), read_image(REAL / "s1" / "01_reposo_apuesta_2.png")
    source = FileFrameSource([intro, intro, game])
    eyes = GameEyes(source, profile, load_market("es"))
    assert eyes.dismiss_intro() == ["presentacion"]
    assert not [n for n in eyes.notes if n.startswith("inconclusive")]


def test_set_bet_min_rapido_sobre_capturas_reales(profile: ProfileSpec) -> None:
    """2,00 -> 0,10 EUR: el bucle lee solo la zona de apuesta y el valor final se confirma en pantalla completa."""
    import time

    s1 = REAL / "s1"
    source = FileFrameSource([read_image(s1 / "01_reposo_apuesta_2.png")] * 2 + [read_image(s1 / "02_apuesta_min.png")])
    eyes = GameEyes(source, profile, load_market("es"))
    start = time.monotonic()
    bet = eyes.set_bet("min")
    elapsed = time.monotonic() - start
    assert bet.money is not None and str(bet.money.amount) == "0.10", bet
    assert len(source.clicks) == 2 and source.clicks[0] == source.clicks[1]  # plantilla buscada una sola vez
    assert all(contains(profile.bet_down.hint, c) for c in source.clicks)
    assert elapsed < 20, f"set_bet tardó {elapsed:.1f}s"
