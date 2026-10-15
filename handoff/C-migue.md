# Traspaso del área C (Migue): escenarios, comprobaciones e informe

Estado: 15-oct-2026, hacia las 12:10, en el portátil de Alejandro. Con esto basta para retomar sin la conversación anterior.

## Hecho y probado
- **Contratos** `betsson/core/`: **fusionados en main** (PR #4, 1ab232d).
  - Revisados con python-reviewer.
  - `resolve()` nunca lanza; `ensure_recognized()` lanza `ProviderUIChanged`.
  - `GameEyes.set_bet("min" | "above_balance")`.
  - `RunResult.outcome` = PASS / FAIL / INCONCLUSIVE / PROVIDER_UI_CHANGED.
- **Rama `feat/C-core`** (subida):
  - `betsson/checks/balance.py`: `reconcile()` (después = antes − apuesta + ganancia) y `unchanged()`, con `market.money_tolerance`. Si falta una lectura o difiere la moneda → no concluyente.
  - `betsson/checks/common.py`:
    - `login_check`, `real_play_check`, `read_check`;
    - `currency_check`: solo cuentan las lecturas con `currency_seen=True`;
    - `apply_ui_changed`: lo no concluyente de pantalla pasa a PROVIDER_UI_CHANGED.
  - `betsson/checks/s1.py` y `s2.py`: `S1Observation`/`S2Observation` (frozen) y `evaluate_s1`/`evaluate_s2`, funciones puras.
  - `betsson/checks/scenario.py`: `run_scenario(market=, scenario=, site=, registry=, eyes_factory=, slug=, out_dir=, run_id=, bet_target="min")`.
    - Escribe `results.json` y `report.html` en `out_dir`.
    - Si salta una excepción, queda en `RunResult.error` y el run sale FAIL, pero se escribe igual.
  - `betsson/report/html.py`: `render_run` y `render_index(run_dir)`, con las plantillas de `betsson/report/templates/`.
  - `tests/fakes.py` (Fake* de A y B) y `tests/test_scenarios.py` (24 tests). `test_demo_run_writes_report_for_ci_artifact` deja un informe de demo en `outputs/runs/<runId>/<market>/{S1,S2}/` y un índice en `outputs/runs/<runId>/report.html`.
  - 87 tests unitarios en verde.

## En qué punto quedó
- python-reviewer revisando checks y report.
- Siguiente: aplicar lo CRITICAL/HIGH y abrir el PR `feat/C-core` → main para el hito M1 de las 13:00.

## Siguientes pasos
1. Arreglar lo que diga la revisión y abrir el PR (`gh pr create --base main --head feat/C-core`).
2. Con A y B: test `@pytest.mark.real` que construya `BetssonSite(page, market, account="funded" | "empty")`, el registro de B y la fábrica de GameEyes, y llame a `run_scenario` con `evidence_dir`. El `out_dir` debe ser `outputs/runs/<runId>/<market>/<S1|S2>/`.
3. Test de contrato de perfiles (comprobar firmas con `inspect.signature` contra los Protocols).
4. Informe: cruce de las tres fuentes (pantalla / red / monedero), huella por juego y tapado de secretos (grep en los artifacts).

## Decisiones
- S2 usa la cuenta vacía (`account="empty"`, que crea A) y `set_bet("min")`. El plan B es la cuenta con saldo y `bet_target="above_balance"`.
- `spin_rejected` = no se vio empezar la tirada **y** se ve el mensaje. Si solo se cumple una de las dos → no concluyente.
- `wager_is_used_wager` = la apuesta mostrada coincide con lo descontado del saldo del juego (antes + ganancia − después) y la apuesta no cambia tras la tirada.
- Las comprobaciones que no son de pantalla (`login_ok`, `real_play`, `betsson_balance_before`) nunca pasan a PROVIDER_UI_CHANGED.

## Comandos
```powershell
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m pytest -m unit -q
```
