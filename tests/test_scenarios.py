"""S1 y S2 de punta a punta con fakes: veredictos, results.json e informe HTML."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from betsson.checks.scenario import run_scenario
from betsson.core import CheckId, FailureKind, Message, RunResult, Scenario, SpinEnd
from betsson.report.html import render_index
from tests.fakes import FakeBetssonSite, FakeGameEyes, FakeGameHandle, FakeMarket, FakeRegistry, factory, reading

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
CORE_DIRS = ["betsson/core", "betsson/checks", "betsson/report"]


def run_s1(out: Path, *, betsson=("100.00", "99.90"), game=("100.00", "99.90"), bet="0.10", win="0.00",
           market: FakeMarket | None = None, site_kw: dict | None = None, eyes_kw: dict | None = None,
           registry: FakeRegistry | None = None) -> RunResult:
    market = market or FakeMarket()
    registry = registry or FakeRegistry()
    as_reading = lambda v: v if not isinstance(v, str) and v is not None else reading(v, market.currency_code)
    site = FakeBetssonSite([as_reading(v) for v in betsson], out, **(site_kw or {}))
    eyes = FakeGameEyes(registry.profile, out, [as_reading(v) for v in game], as_reading(bet), as_reading(win),
                        **(eyes_kw or {}))
    return run_scenario(market=market, scenario=Scenario.S1, site=site, registry=registry,
                        eyes_factory=factory(eyes), slug="fake-slot", out_dir=out, run_id="test")


def run_s2(out: Path, *, betsson=("0.05", "0.05"), game=("0.05", "0.05"), spin_starts=False,
           message: Message | None = None) -> RunResult:
    market = FakeMarket()
    registry = FakeRegistry()
    msg = message if message is not None else Message(text="Saldo insuficiente", lang_detected="es",
                                                       matches_insufficient=True, confidence=0.95)
    site = FakeBetssonSite([reading(v) for v in betsson], out)
    eyes = FakeGameEyes(registry.profile, out, [reading(v) for v in game], reading("0.20"),
                        spin_starts=spin_starts, message=msg)
    return run_scenario(market=market, scenario=Scenario.S2, site=site, registry=registry,
                        eyes_factory=factory(eyes), slug="fake-slot", out_dir=out, run_id="test")


def by_id(run: RunResult) -> dict[CheckId, object]:
    return {r.id: r for r in run.results}


# --- S1 -----------------------------------------------------------------------


def test_s1_losing_spin_passes_and_writes_artifacts(tmp_path: Path) -> None:
    run = run_s1(tmp_path)
    assert run.outcome == "PASS", [r.reason for r in run.results if r.status == "FAIL"]
    assert not run.missing_checks
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert data["verdict"] == "PASS" and data["provider"] == "fake-provider"
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "betsson_balance_reconciles" in html and "PASS" in html


def test_s1_winning_spin_passes(tmp_path: Path) -> None:
    run = run_s1(tmp_path, betsson=("100.00", "101.40"), game=("100.00", "101.40"), win="1.50")
    assert run.outcome == "PASS"


def test_s1_uses_min_bet(tmp_path: Path) -> None:
    registry = FakeRegistry()
    eyes = FakeGameEyes(registry.profile, tmp_path, [reading("1.00"), reading("0.80")], reading("0.20"))
    site = FakeBetssonSite([reading("1.00"), reading("0.80")], tmp_path)
    run_scenario(market=FakeMarket(), scenario=Scenario.S1, site=site, registry=registry,
                 eyes_factory=factory(eyes), slug="fake-slot", out_dir=tmp_path, run_id="test")
    assert eyes.bets_set == ["min"]


def test_s1_betsson_not_reconciling_is_integration_failure(tmp_path: Path) -> None:
    run = run_s1(tmp_path, betsson=("100.00", "100.00"))
    r = by_id(run)[CheckId.BETSSON_BALANCE_RECONCILES]
    assert r.status == "FAIL" and r.failure_kind is FailureKind.INTEGRATION
    assert by_id(run)[CheckId.INGAME_BALANCE_CONSISTENT].status == "PASS"
    assert run.outcome == "FAIL"


def test_s1_doubtful_win_is_inconclusive_not_pass(tmp_path: Path) -> None:
    run = run_s1(tmp_path, win=None)
    checks = by_id(run)
    for cid in (CheckId.PAYOUT_READ, CheckId.INGAME_BALANCE_CONSISTENT, CheckId.BETSSON_BALANCE_RECONCILES):
        assert checks[cid].failure_kind is FailureKind.INCONCLUSIVE
    assert run.outcome == "INCONCLUSIVE"


def test_s1_spin_not_seen_is_inconclusive(tmp_path: Path) -> None:
    run = run_s1(tmp_path, eyes_kw={"spin_starts": False})
    assert by_id(run)[CheckId.SPIN_STARTED].failure_kind is FailureKind.INCONCLUSIVE
    assert by_id(run)[CheckId.SPIN_COMPLETED].failure_kind is FailureKind.INCONCLUSIVE


def test_s1_spin_end_timeout_is_inconclusive(tmp_path: Path) -> None:
    run = run_s1(tmp_path, eyes_kw={"spin_end": SpinEnd(completed=False, duration_s=30, reason="timeout de 30 s")})
    assert "timeout" in by_id(run)[CheckId.SPIN_COMPLETED].reason


def test_s1_provider_drift_is_ui_changed_not_failure(tmp_path: Path) -> None:
    run = run_s1(tmp_path, registry=FakeRegistry(drift="no se encuentra la etiqueta SALDO"))
    checks = by_id(run)
    assert checks[CheckId.LOGIN_OK].status == "PASS"
    assert checks[CheckId.BETSSON_BALANCE_BEFORE].status == "PASS"
    assert checks[CheckId.WAGER_READ].failure_kind is FailureKind.PROVIDER_UI_CHANGED
    assert not any(r.failure_kind is FailureKind.INTEGRATION for r in run.results)
    assert run.outcome == "PROVIDER_UI_CHANGED"
    assert any("PROVIDER_UI_CHANGED" in w for w in run.warnings)
    assert "ha cambiado" in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_s1_demo_mode_fails_real_play(tmp_path: Path) -> None:
    run = run_s1(tmp_path, site_kw={"handle": FakeGameHandle(play_mode="demo")})
    assert by_id(run)[CheckId.REAL_PLAY].failure_kind is FailureKind.INTEGRATION


def test_s1_game_not_opened_fails_real_play(tmp_path: Path) -> None:
    run = run_s1(tmp_path, site_kw={"open_error": "botón Jugar no encontrado"})
    assert by_id(run)[CheckId.REAL_PLAY].failure_kind is FailureKind.INTEGRATION
    assert run.outcome == "FAIL"


def test_s1_login_failure(tmp_path: Path) -> None:
    run = run_s1(tmp_path, site_kw={"logged_in": False})
    assert by_id(run)[CheckId.LOGIN_OK].failure_kind is FailureKind.INTEGRATION
    assert by_id(run)[CheckId.WAGER_READ].failure_kind is FailureKind.INCONCLUSIVE
    assert run.verdict == "FAIL"


def test_s1_crash_still_writes_results(tmp_path: Path) -> None:
    run = run_s1(tmp_path, eyes_kw={"fail_on_spin": RuntimeError("navegador cerrado")})
    assert run.error == "RuntimeError: navegador cerrado"
    assert run.outcome == "FAIL"
    assert RunResult.read_json(tmp_path / "results.json").error == run.error


def test_s1_wrong_visible_currency_fails(tmp_path: Path) -> None:
    run = run_s1(tmp_path, betsson=[reading("100.00", "PEN"), reading("99.80", "PEN")])
    assert by_id(run)[CheckId.CURRENCY_MATCHES_MARKET].failure_kind is FailureKind.INTEGRATION


def test_s1_currency_never_seen_is_inconclusive(tmp_path: Path) -> None:
    unseen = lambda v: reading(v, seen=False)
    run = run_s1(tmp_path, betsson=[unseen("100.00"), unseen("99.80")], game=[unseen("100.00"), unseen("99.80")],
                 bet=unseen("0.20"), win=unseen("0.00"))
    assert by_id(run)[CheckId.CURRENCY_MATCHES_MARKET].failure_kind is FailureKind.INCONCLUSIVE


def test_s1_other_market_by_config_only(tmp_path: Path) -> None:
    peru = FakeMarket(id="pe", currency_code="PEN", language="es")
    run = run_s1(tmp_path, market=peru)
    assert run.market == "pe" and run.outcome == "PASS"


def test_evidence_is_relative_to_run_folder(tmp_path: Path) -> None:
    run_s1(tmp_path)
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    paths = [p for r in data["results"] for p in r["evidence"]]
    assert paths and all(not Path(p).is_absolute() and "\\" not in p for p in paths)
    assert all((tmp_path / p).exists() for p in paths)


# --- S2 -----------------------------------------------------------------------


def test_s2_rejected_spin_passes(tmp_path: Path) -> None:
    run = run_s2(tmp_path)
    assert run.outcome == "PASS", [r.reason for r in run.results if r.status == "FAIL"]


def test_s2_spin_that_starts_is_integration_failure(tmp_path: Path) -> None:
    run = run_s2(tmp_path, spin_starts=True)
    assert by_id(run)[CheckId.SPIN_REJECTED].failure_kind is FailureKind.INTEGRATION


def test_s2_message_in_wrong_language_fails(tmp_path: Path) -> None:
    msg = Message(text="Insufficient funds", lang_detected="en", matches_insufficient=True)
    run = run_s2(tmp_path, message=msg)
    r = by_id(run)[CheckId.INSUFFICIENT_MESSAGE_LANGUAGE]
    assert r.failure_kind is FailureKind.INTEGRATION and r.observed == "en"


def test_s2_unreadable_message_is_inconclusive(tmp_path: Path) -> None:
    run = run_s2(tmp_path, message=Message(reason="OCR sin texto"))
    checks = by_id(run)
    assert checks[CheckId.INSUFFICIENT_MESSAGE_LANGUAGE].failure_kind is FailureKind.INCONCLUSIVE
    assert checks[CheckId.SPIN_REJECTED].failure_kind is FailureKind.INCONCLUSIVE


def test_s2_no_message_is_failure(tmp_path: Path) -> None:
    run = run_s2(tmp_path, message=Message(text="", lang_detected=None, matches_insufficient=False))
    assert by_id(run)[CheckId.INSUFFICIENT_MESSAGE_LANGUAGE].failure_kind is FailureKind.INTEGRATION


def test_s2_balance_change_fails(tmp_path: Path) -> None:
    run = run_s2(tmp_path, betsson=("0.05", "0.00"), game=("0.05", "0.00"))
    checks = by_id(run)
    assert checks[CheckId.BETSSON_BALANCE_UNCHANGED].failure_kind is FailureKind.INTEGRATION
    assert checks[CheckId.INGAME_BALANCE_UNCHANGED].failure_kind is FailureKind.INTEGRATION


# --- Extensibilidad e informe del run ------------------------------------------


def test_core_knows_no_provider_or_market_names() -> None:
    # Ni proveedor ni dominio de mercado en el núcleo: llegan por perfil y configuración.
    banned = ["pragmatic", "betsson.es", "betsson.com", "betsson.pe"]
    for folder in CORE_DIRS:
        for f in (ROOT / folder).rglob("*.*"):
            if f.suffix not in {".py", ".j2"}:
                continue
            text = f.read_text(encoding="utf-8").lower()
            for word in banned:
                assert word.lower() not in text, f"{word} en {f.relative_to(ROOT)}"


def test_demo_run_writes_report_for_ci_artifact(run_id: str, market_id: str, evidence_dir: Path) -> None:
    """Deja en outputs/runs/<runId>/<market>/S1 y S2 un informe con fakes (lo publica la CI)."""
    market_dir = evidence_dir.parent
    s1 = run_s1(market_dir / "S1", market=FakeMarket(id=market_id))
    s2 = run_s2(market_dir / "S2")
    index = render_index(market_dir.parent)
    html = index.read_text(encoding="utf-8")
    assert s1.outcome == s2.outcome == "PASS"
    assert "S1/report.html" in html and "S2/report.html" in html


# --- Arreglos de la revisión ----------------------------------------------------


def test_safe_error_hides_urls_and_local_paths() -> None:
    from betsson.checks.scenario import safe_error

    msg = safe_error(RuntimeError("Timeout https://x.test/play?token=abc en C:\\Users\\yo\\shot.png\nCall log: ..."))
    assert "token" not in msg and "Users" not in msg and "Call log" not in msg
    assert msg.startswith("RuntimeError: Timeout <url>")


def test_s1_no_reading_mid_spin_when_end_not_seen(tmp_path: Path) -> None:
    run = run_s1(tmp_path, eyes_kw={"spin_end": SpinEnd(completed=False, reason="timeout de 30 s")})
    checks = by_id(run)
    assert checks[CheckId.INGAME_BALANCE_CONSISTENT].failure_kind is FailureKind.INCONCLUSIVE
    assert checks[CheckId.BETSSON_BALANCE_RECONCILES].failure_kind is FailureKind.INCONCLUSIVE


def test_s1_zero_bet_is_not_a_pass(tmp_path: Path) -> None:
    run = run_s1(tmp_path, betsson=("100.00", "100.00"), game=("100.00", "100.00"), bet="0.00")
    assert by_id(run)[CheckId.WAGER_READ].failure_kind is FailureKind.INCONCLUSIVE
    assert run.outcome != "PASS"


def test_currency_seen_only_on_betsson_is_inconclusive(tmp_path: Path) -> None:
    unseen = lambda v: reading(v, seen=False)
    run = run_s1(tmp_path, game=[unseen("100.00"), unseen("99.80")], bet=unseen("0.20"), win=unseen("0.00"))
    assert by_id(run)[CheckId.CURRENCY_MATCHES_MARKET].failure_kind is FailureKind.INCONCLUSIVE


def test_s2_with_enough_balance_is_not_integration_failure(tmp_path: Path) -> None:
    run = run_s2(tmp_path, betsson=("100.00", "99.80"), game=("100.00", "99.80"), spin_starts=True)
    r = by_id(run)[CheckId.SPIN_REJECTED]
    assert r.failure_kind is FailureKind.INCONCLUSIVE and "precondición" in r.reason


def test_s2_language_comparison_ignores_case_and_region(tmp_path: Path) -> None:
    msg = Message(text="Saldo insuficiente", lang_detected="ES-es", matches_insufficient=True)
    assert by_id(run_s2(tmp_path, message=msg))[CheckId.INSUFFICIENT_MESSAGE_LANGUAGE].status == "PASS"


def test_ui_changed_evidence_reaches_report(tmp_path: Path) -> None:
    shot = tmp_path / "drift.png"
    shot.write_bytes(b"png")

    class DriftRegistry(FakeRegistry):
        def ensure_recognized(self, profile, frame) -> None:  # type: ignore[override]
            from betsson.core import ProviderUIChanged
            raise ProviderUIChanged("perfil no reconoce la pantalla", evidence=[shot])

    run = run_s1(tmp_path, registry=DriftRegistry())
    assert run.evidence == (Path("drift.png"),)


def test_broken_results_json_does_not_break_index(tmp_path: Path) -> None:
    run_s1(tmp_path / "es" / "S1")
    bad = tmp_path / "es" / "S2"
    bad.mkdir(parents=True)
    (bad / "results.json").write_text("{no es json", encoding="utf-8")
    html = render_index(tmp_path).read_text(encoding="utf-8")
    assert "ERROR" in html and "S1/report.html" in html


def test_real_play_shows_player_steps_from_betsson(tmp_path: Path) -> None:
    dialog = tmp_path / "session_limits_dialog.png"
    dialog.write_bytes(b"png")
    run = run_s1(tmp_path, site_kw={"handle": FakeGameHandle(evidence=(dialog,))})
    r = by_id(run)[CheckId.REAL_PLAY]
    assert r.status == "PASS" and "límites de sesión" in r.reason
    assert r.evidence == (Path("session_limits_dialog.png"),)


def test_assisted_login_is_pass_but_never_hidden(tmp_path: Path) -> None:
    run = run_s1(tmp_path, site_kw={"login_assisted": True})
    r = by_id(run)[CheckId.LOGIN_OK]
    assert r.status == "PASS" and "asistido por una persona" in r.reason
    assert any("login asistido" in w for w in run.warnings)
    assert "login asistido" in (tmp_path / "report.html").read_text(encoding="utf-8")


def test_autonomous_login_has_no_assisted_warning(tmp_path: Path) -> None:
    run = run_s1(tmp_path)
    assert not any("asistido" in w for w in run.warnings)


def test_assisted_login_reason_has_time(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    at = datetime(2026, 10, 15, 14, 5, tzinfo=timezone.utc)
    run = run_s1(tmp_path, site_kw={"login_assisted": True, "login_assisted_at": at})
    assert at.astimezone().strftime("%H:%M") in by_id(run)[CheckId.LOGIN_OK].reason


def test_assisted_without_session_is_inconclusive_not_failure(tmp_path: Path) -> None:
    run = run_s1(tmp_path, site_kw={"login_assisted": True, "logged_in": False})
    r = by_id(run)[CheckId.LOGIN_OK]
    assert r.failure_kind is FailureKind.INCONCLUSIVE and "caducada o ausente" in r.reason
    assert run.outcome == "INCONCLUSIVE"


def test_report_shows_what_the_checker_saw(tmp_path: Path) -> None:
    run = run_s1(tmp_path, win=None)
    names = [r.name for r in run.readings]
    assert names[:3] == ["Saldo de Betsson antes", "Apuesta", "Saldo del juego antes"]
    win = next(r for r in run.readings if r.name == "Ganancia")
    assert win.value is None and "inconclusive" in (win.reason or "")
    assert all(r.evidence is None or not r.evidence.is_absolute() for r in run.readings)
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Lo que vio el comprobador" in html and "confianza 98 %" in html and "dudoso" in html


def test_s2_report_includes_message_reading(tmp_path: Path) -> None:
    run = run_s2(tmp_path)
    msg = next(r for r in run.readings if r.name == "Mensaje en el juego")
    assert msg.raw_text == "Saldo insuficiente" and msg.value == "idioma es"


def test_real_test_never_records_network_trace_har_or_video() -> None:
    """Con la sesión iniciada la web descarga el perfil completo del cliente (datos personales)."""
    source = (ROOT / "tests" / "test_real.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("#", "-", "*")))
    for banned in ("tracing.start", "start_chunk", "record_har", "record_video", "ChunkedTrace("):
        assert banned not in code, f"{banned} en test_real.py"


def test_index_cover_has_matrix_tiles_and_flags(tmp_path: Path) -> None:
    run_s1(tmp_path / "es" / "S1", site_kw={"login_assisted": True})
    run_s2(tmp_path / "es" / "S2", message=Message(reason="OCR sin texto"))
    html = render_index(tmp_path).read_text(encoding="utf-8")
    assert "Comprobaciones por escenario" in html
    assert "betsson_balance_reconciles" in html and "insufficient_message_language" in html
    assert "Login asistido por una persona" in html
    assert "PASS: 1" in html and "INCONCLUSIVE: 1" in html
    assert 'class="strip"' in html and "S1/game_bet.png" in html


def test_index_counts_unreadable_results_as_fail(tmp_path: Path) -> None:
    run_s1(tmp_path / "es" / "S1")
    bad = tmp_path / "es" / "S2"
    bad.mkdir(parents=True)
    (bad / "results.json").write_text("roto", encoding="utf-8")
    html = render_index(tmp_path).read_text(encoding="utf-8")
    assert "FAIL: 1" in html and "PASS: 1" in html


def test_index_s2_strip_shows_message_first(tmp_path: Path) -> None:
    run_s2(tmp_path / "es" / "S2")
    html = render_index(tmp_path).read_text(encoding="utf-8")
    strip = html.split('class="strip"', 1)[1]
    assert strip.index("S2/message.png") < strip.index("S2/game_bet.png")


# --- Datos de la ejecución real (betsson.es, 15-oct) ------------------------------


def test_s1_real_numbers_from_betsson_es(tmp_path: Path) -> None:
    """100,00 − 0,10 + 0 = 99,90 € en el juego y en Betsson, con la apuesta mínima."""
    run = run_s1(tmp_path, betsson=("100.00", "99.90"), game=("100.00", "99.90"), bet="0.10", win="0.00")
    assert run.outcome == "PASS", [r.reason for r in run.results if r.status == "FAIL"]


def test_s1_never_spins_above_min_bet(tmp_path: Path) -> None:
    run = run_s1(tmp_path, bet="2.00")
    checks = by_id(run)
    assert checks[CheckId.WAGER_READ].failure_kind is FailureKind.INCONCLUSIVE
    assert "no es la mínima" in checks[CheckId.WAGER_READ].reason
    assert checks[CheckId.SPIN_STARTED].reason.endswith("no se llegó a intentar la tirada")
    assert run.outcome != "PASS"


def test_s1_unreadable_bet_does_not_spin(tmp_path: Path) -> None:
    run = run_s1(tmp_path, bet=None)
    assert by_id(run)[CheckId.SPIN_STARTED].failure_kind is FailureKind.INCONCLUSIVE
    assert "no se llegó a intentar" in by_id(run)[CheckId.SPIN_STARTED].reason


def test_s2_real_insufficient_funds_dialog(tmp_path: Path) -> None:
    msg = Message(text="Fondos insuficientes para realizar esta apuesta. Haga un depósito en su cuenta o "
                       "reduzca el nivel de la apuesta.", lang_detected="es", matches_insufficient=True,
                  confidence=0.97)
    run = run_s2(tmp_path, betsson=("0.00", "0.00"), game=("0.00", "0.00"), message=msg)
    assert run.outcome == "PASS", [r.reason for r in run.results if r.status == "FAIL"]


def test_betsson_notices_appear_in_readings(tmp_path: Path) -> None:
    from betsson.core import Notice

    shot = tmp_path / "dgoj_no_balance.png"
    shot.write_bytes(b"png")
    handle = FakeGameHandle(notices=(Notice(text="No dispones de saldo…", evidence_path=shot),))
    run = run_s1(tmp_path, site_kw={"handle": handle})
    notice = next(r for r in run.readings if r.name == "Aviso de Betsson")
    assert notice.raw_text == "No dispones de saldo…" and notice.evidence == Path("dgoj_no_balance.png")


def test_plain_text_notices_are_accepted(tmp_path: Path) -> None:
    handle = FakeGameHandle(notices=("No dispones de saldo, pero puedes crear la sesión…",))
    run = run_s1(tmp_path, site_kw={"handle": handle})
    notice = next(r for r in run.readings if r.name == "Aviso de Betsson")
    assert notice.raw_text.startswith("No dispones de saldo") and notice.evidence is None
