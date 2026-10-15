# Traspaso del área C (Migue): escenarios, comprobaciones e informe

Estado al migrar al portátil de Alejandro (15-oct-2026). Con esto basta para retomar sin la conversación anterior.

## Hecho y probado
- **Contratos en `betsson/core/`** (commit `feat(core): contratos pydantic…`, rama `feat/C-contracts`, subida y **sin PR abierto**: en el portátil viejo no había `gh`). Para abrirlo: https://github.com/gitmobau/Malackaton/pull/new/feat/C-contracts
  - `ids.py`: `Scenario` (S1, S2), `CheckId` (los 15 ids de PREPARACION §3) y `SCENARIO_CHECKS`.
  - `money.py`: `Money(amount: Decimal, currency: ISO 4217)`, inmutable. `+` y `-` lanzan `CurrencyMismatch` si las monedas no coinciden.
  - `results.py`:
    - `CheckResult` (`status` PASS/FAIL, `reason`, `failure_kind` = `integration` | `inconclusive` | `provider_ui_changed`, `expected`, `observed`, `evidence`), con los constructores `passed`, `failed`, `inconclusive` (prefijo `"inconclusive: "`) y `ui_changed`.
    - `RunResult` (= `results.json`): calcula `verdict`, `missing_checks` y `provider_ui_changed`; `write_json()` y `read_json()`.
  - `errors.py`: `PROVIDER_UI_CHANGED` y `ProviderUIChanged(reason, evidence)`.
  - `interfaces.py`:
    - Modelos: `Rect` (fracciones de 0 a 1 que no se salen del canvas), `IntroScreen`, `SpinEndSignal`, `Reading` (con `currency_seen`), `SpinEnd` y `Message`.
    - Protocols: `MarketContext` (`id`, `currency_code`, `language`, `money_tolerance`), `ProviderProfile`, `ProviderRegistry`, `GameHandle` (`iframe_url`, `play_mode`, `capture()`), `GameEyes` y `BetssonSite` (`login`, `is_logged_in`, `read_balance -> Reading`, `open_game`, `screenshot`).
  - `tests/test_contracts.py`: 23 tests. Con los del esqueleto de D son 33 y todos pasan (`pytest -m unit`), en Python 3.14 y en sintaxis compatible con 3.12 (CI).
- **Entorno verificado** en el venv compartido (Py 3.14): pydantic 2.14, jinja2, pytest 9.1, rapidocr 3.10 con onnxruntime 1.31 (el OCR funciona), OpenCV 5, imagehash y Playwright 1.64 con Chromium 156 (necesita `PLAYWRIGHT_BROWSERS_PATH`). Falta `anthropic`; ya se ha avisado a D.

## En qué punto quedó
Contratos terminados y subidos. Faltaba:
1. pasar el agente `python-reviewer` por el PR de contratos (lo pidió Migue antes de cada PR);
2. abrir el PR y avisar a A y B.

No se había empezado `run_scenario`.

## Siguientes pasos, en orden
1. `python-reviewer` sobre `betsson/core/` y `tests/test_contracts.py`, arreglar lo CRITICAL/HIGH y abrir el PR `feat/C-contracts` → `main`. Avisar a A y B.
2. En `feat/C-core` (para el M1 de las 13:00):
   - `betsson/checks/balance.py`: `después = antes − apuesta + ganancia` con `market.money_tolerance`. Si falta un dato o no coincide la moneda → `CheckResult.inconclusive`.
   - `betsson/checks/s1.py` y `s2.py`: las comprobaciones de §3 a partir de las `Reading`. Para `currency_matches_market` solo cuentan las lecturas con `currency_seen=True`. Si nada la vio → inconclusive.
   - `betsson/core/scenario.py`: `run_scenario(market, scenario, site, eyes, out_dir, run_id, slug)`. Si salta `ProviderUIChanged`, las comprobaciones de pantalla pendientes son `CheckResult.ui_changed` y se añade un aviso.
   - `betsson/report/`: plantilla Jinja2 que genera `report.html` junto a `results.json`, más un índice global en `outputs/runs/<runId>/report.html`.
   - `tests/fakes.py` (`FakeBetssonSite`, `FakeGameEyes`, `FakeGameHandle`, `FakeMarket`, `FakeProfile`) y tests de la regla del saldo, de los veredictos y de S1/S2 de punta a punta, con `@pytest.mark.unit`.
   - Usar las fixtures de `conftest.py`: `market_id`, `run_id` y `evidence_dir` (`outputs/runs/<runId>/<market>/<test>/`).
3. Después del M1: cruce de las tres fuentes en el informe, huella por juego y aviso `PROVIDER_UI_CHANGED`, y tapado de secretos.

## Decisiones tomadas (acordadas con A y B por mensaje)
- `ProviderProfile`: la propuesta de B tal cual (Rect, IntroScreen, SpinEndSignal, labels por campo e idioma, hint_zones, spin_templates, spin_hint, insufficient_texts por idioma, spin_end, network_pattern y `detect() -> float`).
- `ProviderRegistry.resolve()`: devuelve el perfil con mayor `detect`, `generic-vision` si ninguno pasa de 0,5, y lanza `ProviderUIChanged` si tampoco este reconoce el juego. La implementación es de B; el Protocol, de C.
- `Money` vive en core y la moneda es obligatoria. `parse_money` (A):
  - si el texto trae el símbolo de otra moneda, devuelve esa moneda;
  - si no trae ninguno, `require_currency=True` lanza `MoneyParseError` y `False` usa la moneda del mercado;
  - si la moneda se vio va en `Reading.currency_seen`, no en Money;
  - A expondrá `detect_currency(texto, mercado)`.
- `MarketContext.currency_code` (y no `currency`) para no chocar con el objeto `currency` de A. `GameHandle.capture()` (y no `frame()`) para no chocar con el Frame de Playwright de A.
- `BetssonSite.read_balance()` devuelve `Reading` (con evidencia), no `Money` a secas.
- Rama `feat/C-contracts` construida sobre `origin/main` (8aad168, después del squash del PR #1). Un rebase normal reaplicaba commits viejos de docs, así que se usó cherry-pick.

## Problemas abiertos
- `anthropic` no está instalado en el venv (lo lleva D).
- Las sesiones abiertas antes del setup no tienen `PLAYWRIGHT_BROWSERS_PATH=D:\DevCache\ms-playwright` y Chromium falla. Le propuse a D un `setdefault` en `conftest.py`.
- La CI de PR usa Python 3.12 y en local se usa 3.14: nada exclusivo de 3.13 o 3.14.
- A todavía tiene que confirmar los nombres (`currency_code`, `capture`, `Reading` en `read_balance`).

## Comandos
```powershell
git fetch origin; git checkout feat/C-core      # o feat/C-contracts para el PR
<venv>\Scripts\python.exe -m pytest -m unit -q   # 33 passed
$env:PLAYWRIGHT_BROWSERS_PATH = "<DevCache>\ms-playwright"   # solo si se usa el navegador
```
