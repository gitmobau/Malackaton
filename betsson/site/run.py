"""Un solo comando para la demo: comprueba las sesiones, ejecuta los escenarios y abre el informe.

    python -m betsson.site.run --market es --scenarios s1,s2 --game big-bass-splash

1. Comprueba (sin escribir credenciales) que la sesión del login asistido sigue viva en el Chrome de cada
   cuenta necesaria: S1 usa la cuenta con saldo y S2 la cuenta sin saldo (S2_ACCOUNT=funded para el plan B).
   Si alguna falta o caducó, dice qué comando repetir y no ejecuta nada.
2. Ejecuta tests/test_real.py con pytest -m real, el filtro de escenarios y SIN traza, vídeo ni capturas
   automáticas (con la sesión iniciada guardarían el perfil del cliente). Las mismas opciones que la CI.
3. Abre outputs/runs/<runId>/report.html en el navegador predeterminado.
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from betsson.market import load_market
from betsson.site.login_asistido import check_session
from betsson.site.session import BrowserSession, SessionUnavailable

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ("s1", "s2")
# Sin traza, vídeo ni capturas de pytest-playwright: anulan pytest.ini, igual que el job real de la CI.
PYTEST_PRIVACY = ["--tracing", "off", "--video", "off", "--screenshot", "off"]

log = logging.getLogger("run")


def accounts_for(scenarios: list[str]) -> list[str]:
    """Cuentas que necesitan sesión, como en tests/test_real.py (S2_ACCOUNT=funded: plan B sin cuenta vacía)."""
    by_scenario = {"s1": "funded", "s2": os.getenv("S2_ACCOUNT", "empty").strip().lower()}
    return sorted({by_scenario[s] for s in scenarios})


def parse_scenarios(value: str) -> list[str]:
    """'s1,s2' -> ['s1', 's2']. Rechaza vacíos y escenarios desconocidos."""
    wanted = sorted({s.strip().lower() for s in value.split(",") if s.strip()})
    unknown = [s for s in wanted if s not in SCENARIOS]
    if not wanted or unknown:
        raise argparse.ArgumentTypeError(f"escenarios no válidos: {value!r} (usa s1, s2 o s1,s2)")
    return wanted


def pytest_command(market_id: str, scenarios: list[str]) -> list[str]:
    """El mismo pytest que el job real de la CI, filtrado a los escenarios pedidos."""
    cmd = [sys.executable, "-m", "pytest", "tests/test_real.py", "-m", "real", "--market", market_id,
           "--headed", "--browser-channel", "chrome", *PYTEST_PRIVACY]
    if len(scenarios) == 1:
        cmd += ["-k", f"real_{scenarios[0]}"]
    return cmd


def check_sessions(market_id: str, scenarios: list[str]) -> bool:
    """True si todas las cuentas necesarias tienen la sesión viva. Si no, explica qué repetir."""
    market = load_market(market_id)
    ok = True
    for account in accounts_for(scenarios):
        try:
            session = BrowserSession(market, account)
            alive = session.is_listening() and check_session(session)
        except SessionUnavailable as exc:
            log.error("%s", exc)
            alive = False
        if alive:
            log.info("sesión de la cuenta '%s' VÁLIDA", account)
            continue
        ok = False
        log.error("sesión de la cuenta '%s' ausente o caducada. Repite el login asistido:\n"
                  "    python -m betsson.site.login_asistido --market %s --account %s\n"
                  "  inicia sesión a mano en esa ventana y vuelve a lanzar este comando.", account, market_id, account)
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--market", default=os.getenv("MARKET", "es"), help="id de config/markets/<mercado>.json")
    parser.add_argument("--scenarios", type=parse_scenarios, default=list(SCENARIOS), help="s1, s2 o s1,s2")
    parser.add_argument("--game", default=os.getenv("GAME_SLUG", ""), help="slug del juego en Betsson (o GAME_SLUG)")
    parser.add_argument("--no-open", action="store_true", help="no abrir el informe al terminar")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not args.game.strip():
        parser.error("indica el juego con --game <slug> o con la variable GAME_SLUG")

    if not check_sessions(args.market, args.scenarios):
        return 2

    run_id = os.getenv("RUN_ID") or "demo-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    env = {**os.environ, "GAME_SLUG": args.game.strip(), "RUN_ID": run_id}
    log.info("ejecutando %s (run %s, juego %s)", ",".join(args.scenarios).upper(), run_id, env["GAME_SLUG"])
    code = subprocess.call(pytest_command(args.market, args.scenarios), cwd=ROOT, env=env)  # noqa: S603

    report = ROOT / "outputs" / "runs" / run_id / "report.html"
    if report.is_file():
        log.info("informe: %s", report)
        if not args.no_open:
            webbrowser.open(report.as_uri())
    else:
        log.warning("no se generó el informe %s (mira la salida de pytest)", report)
    log.info("resultado: %s", "todo PASS" if code == 0 else f"hay FAIL o no concluyentes (pytest salió con {code})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
