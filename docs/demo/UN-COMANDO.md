# La validación en un solo comando

```powershell
python -m betsson.site.run --market es --scenarios s1,s2 --game big-bass-splash
```

## Qué hace
1. **Comprueba las sesiones**: mira que el login asistido siga vivo en el Chrome de cada cuenta que hace falta.
   - S1 usa la cuenta con saldo, en el puerto 9222.
   - S2 usa la cuenta sin saldo, en el puerto 9223.
   - No escribe credenciales. Si alguna sesión falta o ha caducado, dice qué comando repetir y **no ejecuta nada** (código de salida 2).
2. **Ejecuta los escenarios** con el mismo `pytest -m real` que la CI, filtrado a los escenarios pedidos. No graba traza, vídeo ni capturas automáticas, porque con la sesión iniciada guardarían el perfil del cliente.
3. **Abre el informe** `outputs/runs/<runId>/report.html` en el navegador predeterminado.

Código de salida: `0` si todo es PASS. Cualquier otro valor indica algún FAIL o algún resultado no concluyente; los motivos están en el informe.

## Antes de lanzarlo (una vez, justo antes)
Las sesiones de Betsson caducan tras unos 25-30 min de inactividad. Para cada cuenta:
```powershell
python -m betsson.site.login_asistido --market es --account funded   # abre Chrome: una persona inicia sesión a mano
python -m betsson.site.login_asistido --market es --account empty
```

## Opciones
| Opción | Por defecto | Para qué |
|---|---|---|
| `--market` | `MARKET` o `es` | mercado (`config/markets/<id>.json`) |
| `--scenarios` | `s1,s2` | `s1`, `s2` o `s1,s2` |
| `--game` | `GAME_SLUG` | slug del juego en Betsson: `big-bass-splash`, `big-bass-bonanza`… |
| `--no-open` | — | no abrir el informe al terminar |

Variables opcionales:
- `RUN_ID`: nombre de la carpeta del run. Por defecto es `demo-<fecha UTC>`.
- `S2_ACCOUNT=funded` y `S2_BET_TARGET=above_balance`: plan B de S2 sin cuenta vacía.
