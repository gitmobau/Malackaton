"""run_scenario: ejecuta S1 o S2 con las piezas inyectadas y escribe results.json + report.html.

No conoce ningún proveedor ni mercado concreto: todo llega por las interfaces de core.
Orden: login → saldo de Betsson → abrir juego → perfil (resolve + ensure_recognized)
→ ojos → jugar → saldo de Betsson después. Cada paso que no se llega a hacer queda
como None y su comprobación sale no concluyente (nunca PASS).

El saldo de Betsson "después" lo lee BetssonSite.read_balance(), que debe esperar a
que el monedero se estabilice (lo implementa A); aquí no hay esperas fijas.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Callable
from typing import Any

from betsson.checks.common import LOGIN_ASSISTED_WARNING
from betsson.checks.s1 import S1Observation, bet_not_minimum, evaluate_s1
from betsson.checks.s2 import S2Observation, evaluate_s2
from betsson.core import (
    BetssonSite,
    BetTarget,
    CheckResult,
    GameEyes,
    GameEyesFactory,
    GameOpenError,
    MarketContext,
    Message,
    Notice,
    ProviderRegistry,
    ProviderUIChanged,
    RunResult,
    Scenario,
    ScreenReading,
)
from betsson.report.fingerprint import BaselineStore, check_drift, take
from betsson.report.html import render_run

log = logging.getLogger(__name__)

RESULTS_FILE = "results.json"
NOTICE_VALUE = "aviso visible"  # un aviso no es una lectura dudosa
MAX_ERROR_CHARS = 300
_URL = re.compile(r"https?://\S+")
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:home|Users|tmp|var|mnt|d|c)/)\S*")


def safe_error(exc: BaseException | str) -> str:
    """Motivo apto para el informe: sin URLs (pueden llevar tokens) ni rutas locales, una línea."""
    text = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    first = text.strip().splitlines()[0] if text.strip() else type(exc).__name__
    clean = _PATH.sub("<ruta>", _URL.sub("<url>", first))
    return clean[:MAX_ERROR_CHARS]


def _prepare(
    site: BetssonSite, registry: ProviderRegistry, eyes_factory: GameEyesFactory,
    market: MarketContext, slug: str, obs: dict[str, Any], extra: dict[str, Any],
) -> GameEyes | None:
    """Login, saldo inicial, apertura del juego y perfil. Devuelve los ojos o None."""
    # El modo asistido se conoce desde el constructor: se anota antes, por si login() falla.
    obs["login_assisted"] = bool(site.login_assisted)
    obs["logged_in"] = site.login()
    # Solo se muestra en el informe: tolerante a un BetssonSite anterior al campo.
    obs["login_assisted_at"] = getattr(site, "login_assisted_at", None)
    if not obs["logged_in"]:
        return None
    obs["betsson_before"] = site.read_balance()
    try:
        handle = site.open_game(slug)
    except GameOpenError as exc:
        obs["open_error"] = safe_error(str(exc))
        return None
    obs["play_mode"] = handle.play_mode
    obs["play_mode_reason"] = safe_error(handle.play_mode_reason) if handle.play_mode_reason else None
    # Avisos de Betsson al abrir (p. ej. la DGOJ sin saldo). Tolerante a un GameHandle sin el campo.
    extra["notices"] = tuple(getattr(handle, "notices", ()) or ())
    obs["open_evidence"] = tuple(handle.evidence)
    extra["handle"] = handle
    return _recognized_eyes(handle, registry, eyes_factory, market, extra)


def _recognized_eyes(handle: Any, registry: ProviderRegistry, eyes_factory: GameEyesFactory,
                     market: MarketContext, extra: dict[str, Any]) -> GameEyes:
    """Perfil en dos pasos, porque la intro del juego tapa la pantalla de juego:
    1) primer perfil con lo que se ve al abrir (sirve para cerrar su intro);
    2) los ojos cierran la intro; se resuelve otra vez con el juego listo y, si cambia
       el perfil, se rehacen los ojos con el bueno;
    3) solo entonces ensure_recognized (ProviderUIChanged sube a run_scenario).
    """
    profile = registry.resolve(handle.iframe_url, handle.capture())
    eyes = eyes_factory(handle, profile, market)
    ready = registry.resolve(handle.iframe_url, handle.capture())
    if ready.name != profile.name:
        log.info("perfil tras la intro: %s (antes %s)", ready.name, profile.name)
        profile, eyes = ready, eyes_factory(handle, ready, market)
    extra["provider"] = profile.name
    registry.ensure_recognized(profile, handle.capture())
    return eyes


def _fingerprint_frame(obs: dict[str, Any], extra: dict[str, Any]) -> None:
    """Captura para la huella solo cuando el juego ya está listo (se leyó su saldo)."""
    reading = obs.get("game_before")
    handle = extra.get("handle")
    if handle is not None and reading is not None and reading.ok:
        extra["frame"], extra["iframe_url"] = handle.capture(), handle.iframe_url


def _play_s1(eyes: GameEyes, site: BetssonSite, obs: dict[str, Any], bet_target: BetTarget,
             on_ready: Callable[[], None]) -> None:
    # El saldo del juego solo se lee ANTES de pulsar girar y DESPUÉS de que la tirada
    # termine (wait_spin_end); nunca a mitad de giro, porque no se sabe cuándo descuenta.
    obs["bet"] = eyes.set_bet(bet_target)
    obs["game_before"] = eyes.read_balance()
    on_ready()
    if bet_not_minimum(obs["bet"], obs.get("min_bet"), obs.pop("_tolerance")):
        return  # nunca se gira por encima de la apuesta mínima: wager_read queda no concluyente
    obs["spin_started"] = eyes.spin()
    if not obs["spin_started"]:
        return
    obs["spin_end"] = eyes.wait_spin_end()
    if not obs["spin_end"].completed:
        return  # leer ahora sería leer a mitad de giro: queda no concluyente
    obs["win"] = eyes.read_win()
    obs["game_after"] = eyes.read_balance()
    obs["bet_after"] = eyes.read_bet()
    obs["betsson_after"] = site.read_balance()


def _play_s2(eyes: GameEyes, site: BetssonSite, obs: dict[str, Any], bet_target: BetTarget,
             on_ready: Callable[[], None]) -> None:
    # Cuenta sin saldo: basta la mínima. Cuenta con saldo: bet_target="above_balance".
    obs["bet"] = eyes.set_bet(bet_target)
    obs["game_before"] = eyes.read_balance()
    on_ready()
    obs["spin_started"] = eyes.spin()
    # Primero el mensaje: el "cambio visual" tras pulsar suele ser la propia ventana de
    # fondos insuficientes, no los rodillos. Si se reconoce el aviso, no se espera a un fin
    # de tirada que no va a llegar.
    obs["message"] = eyes.read_message()
    if obs["spin_started"] and not obs["message"].matches_insufficient:
        end = eyes.wait_spin_end()
        obs["spin_completed"] = end.completed
        if not end.completed:
            return  # sin fin visible no se lee el saldo a mitad de giro
    obs["game_after"] = eyes.read_balance()
    obs["betsson_after"] = site.read_balance()


def _evaluate(scenario: Scenario, obs: dict[str, Any], market: MarketContext) -> list[CheckResult]:
    obs.pop("_tolerance", None)
    if scenario is Scenario.S1:
        return evaluate_s1(S1Observation(**obs), market)
    return evaluate_s2(S2Observation(**obs), market)


# Lecturas que se enseñan en el informe, en el orden del jugador: (clave en obs, nombre, origen).
_READINGS = (
    ("betsson_before", "Saldo de Betsson antes", "betsson"),
    ("bet", "Apuesta", "juego"),
    ("game_before", "Saldo del juego antes", "juego"),
    ("win", "Ganancia", "juego"),
    ("game_after", "Saldo del juego después", "juego"),
    ("bet_after", "Apuesta tras la tirada", "juego"),
    ("message", "Mensaje en el juego", "juego"),
    ("betsson_after", "Saldo de Betsson después", "betsson"),
)


def _notice_reading(notice: Any) -> ScreenReading:
    """Aviso de Betsson: Notice(text, evidence_path) o, durante la transición, un str."""
    if isinstance(notice, Notice):
        return ScreenReading(name="Aviso de Betsson", source="betsson", raw_text=notice.text,
                             value=NOTICE_VALUE, evidence=notice.evidence_path)
    return ScreenReading(name="Aviso de Betsson", source="betsson", raw_text=str(notice), value=NOTICE_VALUE)


def _screen_readings(obs: dict[str, Any], notices: tuple[Any, ...] = ()) -> tuple[ScreenReading, ...]:
    out = []
    for key, name, source in _READINGS:
        if key == "bet":  # los avisos de Betsson al abrir el juego van justo antes de jugar
            out += [_notice_reading(n) for n in notices]
        item = obs.get(key)
        if item is None:
            continue
        if isinstance(item, Message):
            out.append(ScreenReading(name=name, source=source, raw_text=item.text, confidence=item.confidence,
                                     value=item.lang_detected and f"idioma {item.lang_detected}",
                                     reason=item.reason, evidence=item.evidence_path))
        else:
            out.append(ScreenReading(name=name, source=source, raw_text=item.raw_text,
                                     value=str(item.money) if item.money else None, confidence=item.confidence,
                                     currency_seen=item.currency_seen, reason=item.reason,
                                     evidence=item.evidence_path))
    return tuple(out)


def _relative(path: Path, base: Path, warnings: list[str]) -> Path | None:
    """Ruta relativa a la carpeta del run. Si queda fuera, se descarta con aviso (nunca rutas locales)."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    try:
        return absolute.resolve().relative_to(base.resolve())
    except ValueError:
        warnings.append(f"evidencia fuera de la carpeta del run descartada: {path.name}")
        return None


def _relative_all(paths: tuple[Path, ...], base: Path, warnings: list[str]) -> tuple[Path, ...]:
    return tuple(p for p in (_relative(x, base, warnings) for x in paths) if p is not None)


def _with_relative_evidence(run: RunResult, base: Path) -> RunResult:
    warnings = list(run.warnings)
    results = tuple(r.model_copy(update={"evidence": _relative_all(r.evidence, base, warnings)}) for r in run.results)
    evidence = _relative_all(run.evidence, base, warnings)
    readings = tuple(
        r.model_copy(update={"evidence": _relative(r.evidence, base, warnings) if r.evidence else None})
        for r in run.readings
    )
    return run.model_copy(update={"results": results, "evidence": evidence, "readings": readings,
                                  "warnings": tuple(dict.fromkeys(warnings))})


def _with_drift(run: RunResult, baselines: BaselineStore, extra: dict[str, Any], out_dir: Path) -> RunResult:
    """Aviso si el juego cambió desde la última ejecución buena. Solo un PASS actualiza la referencia."""
    try:
        fp = take(extra["frame"], iframe_url=extra["iframe_url"], market=run.market, game=run.game or "",
                  provider=run.provider, run_id=run.run_id)
        warnings, evidence = check_drift(baselines, extra["frame"], fp, out_dir, update=run.outcome == "PASS")
    except Exception as exc:  # la huella es un extra: nunca debe tumbar el resultado
        log.exception("huella del juego")
        return run.model_copy(update={"warnings": (*run.warnings, f"huella no disponible: {safe_error(exc)}")})
    return run.model_copy(update={"warnings": (*run.warnings, *warnings), "evidence": (*run.evidence, *evidence)})


def _collect(scenario: Scenario, site: BetssonSite, registry: ProviderRegistry, eyes_factory: GameEyesFactory,
             market: MarketContext, slug: str, bet_target: BetTarget) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ejecuta los pasos. Devuelve (observación, extra con provider/error/evidence)."""
    obs: dict[str, Any] = (
        {"min_bet": market.min_bet, "_tolerance": market.money_tolerance} if scenario is Scenario.S1 else {}
    )
    extra: dict[str, Any] = {"notices": (), "provider": None, "error": None, "evidence": (), "frame": None, "iframe_url": None,
                             "handle": None, "eye_notes": ()}
    eyes: GameEyes | None = None
    try:
        eyes = _prepare(site, registry, eyes_factory, market, slug, obs, extra)
        if eyes is not None:
            play = _play_s1 if scenario is Scenario.S1 else _play_s2
            play(eyes, site, obs, bet_target, lambda: _fingerprint_frame(obs, extra))
    except ProviderUIChanged as exc:
        obs["ui_changed"] = safe_error(exc.reason)
        extra["evidence"] = tuple(exc.evidence)
    except Exception as exc:  # el run se corta, pero deja results.json con el motivo
        log.exception("run_scenario %s/%s se cortó", market.id, scenario.value)
        extra["error"] = safe_error(exc)
    finally:
        # Notas de los ojos (p. ej. "inconclusive: la intro no se cerró en 60 s"): al informe como avisos.
        extra["eye_notes"] = tuple(safe_error(str(n)) for n in (getattr(eyes, "notes", ()) or ()))
    return obs, extra


def run_scenario(
    *,
    market: MarketContext,
    scenario: Scenario,
    site: BetssonSite,
    registry: ProviderRegistry,
    eyes_factory: GameEyesFactory,
    slug: str,
    out_dir: Path,
    run_id: str,
    bet_target: BetTarget = "min",
    baselines: BaselineStore | None = None,
) -> RunResult:
    """Ejecuta un escenario en un mercado y deja results.json y report.html en out_dir."""
    if scenario is Scenario.S1 and bet_target != "min":
        raise ValueError("S1 se juega siempre con la apuesta mínima")
    started = datetime.now(timezone.utc)
    obs, extra = _collect(scenario, site, registry, eyes_factory, market, slug, bet_target)
    warnings = [f"PROVIDER_UI_CHANGED: {obs['ui_changed']}"] if obs.get("ui_changed") else []
    if obs.get("login_assisted"):
        warnings.insert(0, LOGIN_ASSISTED_WARNING)
    warnings += [f"ojos del juego: {n}" for n in extra["eye_notes"]]
    error = extra["error"]
    try:
        results = tuple(_evaluate(scenario, obs, market))
    except Exception as exc:
        log.exception("evaluación de %s/%s", market.id, scenario.value)
        results, error = (), error or safe_error(exc)

    run = RunResult(
        run_id=run_id, market=market.id, scenario=scenario, provider=extra["provider"], game=slug,
        started_at=started, finished_at=datetime.now(timezone.utc), results=results,
        warnings=tuple(warnings), error=error, evidence=extra["evidence"], readings=_screen_readings(obs, extra["notices"]),
    )
    if baselines is not None and extra["frame"] is not None:
        run = _with_drift(run, baselines, extra, out_dir)
    run = _with_relative_evidence(run, out_dir)
    run.write_json(out_dir / RESULTS_FILE)
    try:
        render_run(run, out_dir)
    except Exception:  # results.json ya está escrito: el informe no debe ocultarlo
        log.exception("no se pudo generar report.html de %s/%s", market.id, scenario.value)
    return run
