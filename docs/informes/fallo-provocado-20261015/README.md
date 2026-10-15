# Fallo provocado (15-oct-2026, 19:29) · S1 real en betsson.es

Requisito del mentor: *"make your test fail once… provide this report failing… then revert back"*.
Sirve para demostrar que el comprobador **detecta de verdad** un error y que el informe lo refleja: si un test roto siguiera en verde, el test no estaría comprobando nada.

## Qué se rompió
Un solo cambio en `betsson/checks/balance.py` (commit `bd091f5`, rama `demo/fallo-provocado`, [PR #36](https://github.com/gitmobau/Malackaton/pull/36), **sin fusionar**). La regla del saldo resta la apuesta **dos veces**:

```diff
-    expected = b - w + p
+    expected = b - w - w + p   # FALLO PROVOCADO
```

## Qué pasó
- Ejecución real del escenario S1 (cuenta con saldo, Big Bass Splash, Real Play) con `main` + solo ese commit.
- **Resultado: FAIL** ([report.html](S1/report.html), [results.json](S1/results.json)):
  - `ingame_balance_consistent` → FAIL: *no cuadra: 99,50 − 0,10 + 0 = 99,30 EUR; leído 99,40 EUR; diferencia 0,10*
  - `betsson_balance_reconciles` → FAIL: lo mismo con el saldo de Betsson.
  - El resto de comprobaciones (login, Real Play, moneda, apuesta, inicio y fin de la tirada, ganancia) siguen en **PASS**: el fallo se aísla exactamente en la regla rota.
- La diferencia (0,10 €) es justo la apuesta restada de más: el comprobador lee la pantalla bien y es la regla la que falla.
- En GitHub Actions, el PR #36 muestra el check **en rojo** (14 tests unitarios fallan): así se notifica un cambio que rompe la validación.

## Reversión
El commit **nunca ha entrado en `main`**. `main` sigue con la regla correcta y la ejecución de la CI [38775750739](https://github.com/gitmobau/Malackaton/actions/runs/38775750739) da **PASS** en S1 y S2.
