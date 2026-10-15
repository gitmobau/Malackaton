# Guion de la demo (7 min, solo finalistas)

Objetivo: que el jurado vea en 7 minutos que **funciona**, que **ve como un jugador**, que **se extiende** a otros proveedores y mercados, y que **corre en CI con evidencias**.
Una persona habla y otra maneja el portátil (el del runner, `portatil-alejandro`).

## Bloques y tiempos

| # | Bloque | Tiempo | Acumulado | Quién | Qué se enseña |
|---|---|---|---|---|---|
| 1 | El problema | 0:30 | 0:30 | Habla | El juego es un canvas de terceros sin DOM: hay que comprobarlo como un jugador. Dos escenarios: tirada completada (S1) y saldo insuficiente (S2) |
| 2 | Ejecución real | 2:00 | 2:30 | Maneja | **15 s de contexto**: "el login es asistido por decisión del mentor (antibot de Betsson): una persona inicia sesión y el comprobador se conecta a ese Chrome; el valor está en el análisis del canvas". Después, `gh workflow run` en directo: el runner se conecta al Chrome con sesión, abre el juego de Pragmatic y gira con la apuesta mínima |
| 3 | Informe PASS/FAIL | 1:30 | 4:00 | Maneja | Informe web: PASS/FAIL por comprobación, con motivo y capturas; la regla `después = antes − apuesta + ganancia`; S2 con el mensaje en el idioma del mercado |
| 4 | Cómo "ve como un jugador" | 1:00 | 5:00 | Habla | OCR sobre el canvas localizando los importes por su etiqueta (SALDO/APUESTA/GANANCIA), plantillas multiescala para el botón, la red y el monedero de Betsson solo **confirman**. Lo dudoso es FAIL "inconclusive", nunca PASS |
| 5 | Extensibilidad: proveedores y mercados | 0:45 | 5:45 | Habla | Un proveedor = una carpeta en `betsson/profiles/<proveedor>/` + test de contrato; `generic-vision` de respaldo. Un mercado = un `config/markets/<mercado>.json` (Perú/PEN, Malta/EN) validado con pydantic. `PROVIDER_UI_CHANGED` si el proveedor cambia la interfaz |
| 6 | CI y arquitectura | 0:45 | 6:30 | Habla | GitHub Actions: tests sin red en cada PR, ejecución real en un runner propio en España (geobloqueo), matriz por mercado, escáner de secretos antes de publicar evidencias |
| 7 | Siguientes pasos | 0:30 | 7:00 | Habla | Segundo proveedor real, mercados `com` y `pe` con cuenta, deriva visual con hash perceptual, Pages público |

Plan B si la ejecución en directo falla o tarda más de 2 min: pasar al **vídeo de respaldo** (bloque 2) y al informe de la última ejecución buena (bloque 3). No se depura en directo.

## Comandos exactos

Desde una terminal del portátil, con `gh` y la sesión iniciada (cuenta del equipo):

```bash
# 1) Lanzar la validación real en el mercado español
gh workflow run "Validación de juegos" -R gitmobau/Malackaton --ref main -f markets=es
#    Solo un escenario: añadir -f scenarios=s1 (tirada completa) o -f scenarios=s2 (saldo insuficiente).
#    Por defecto, s1,s2. Solo se exige el Chrome del escenario pedido (S1 → 9222, S2 → 9223).

# 2) Seguirla en directo (coge la última ejecución del workflow)
RUN=$(gh run list -R gitmobau/Malackaton -w "Validación de juegos" -L 1 --json databaseId -q '.[0].databaseId')
gh run watch -R gitmobau/Malackaton "$RUN"

# 3) Descargar el informe web y las evidencias
gh run download -R gitmobau/Malackaton "$RUN" -p "informe-web-*" -D outputs/demo
gh run download -R gitmobau/Malackaton "$RUN" -p "evidencias-*" -D outputs/demo

# 4) Abrir el informe
start outputs/demo/informe-web-*/index.html        # Git Bash / cmd
# PowerShell: Invoke-Item (Get-ChildItem outputs\demo\informe-web-*\index.html)
```

Si Pages llega a estar activo (`PAGES_ENABLED=true`), el informe también está en la URL que muestra el job `pages`.

## Checklist previa (15 min antes)

- [ ] **Runner online**: `gh api repos/gitmobau/Malackaton/actions/runners --jq '.runners[] | [.name,.status] | @tsv'` → `portatil-alejandro online`. Si no: `start "runner" /min cmd /c "D:\DevTools\actions-runner\run.cmd"`.
- [ ] **Saldo de la cuenta** de prueba suficiente para S1 (apuesta mínima) y la cuenta de S2 **sin saldo**. Si no, pedir recarga a los mentores.
- [ ] **Login asistido hecho JUSTO antes de lanzar**: las sesiones de Betsson caducan en menos de 1 h, así que no se hace al preparar la sala sino en el último minuto antes del `gh workflow run`. Una persona inicia sesión en los Chrome de los perfiles `es-main` (puerto 9222) y `es-empty` (puerto 9223) de `D:\MAIKI\Malackathon\.chrome-profiles`, **sin que se vea en el proyector**. Comprobar que responden: `curl -s http://127.0.0.1:9222/json/version` y lo mismo con 9223. Si la sesión caduca, el workflow falla con "repetir login asistido".
- [ ] **Chrome** instalado y actualizado. Cerrar las demás ventanas de Chrome de A y B en el portátil del runner, pero **no** las dos del login asistido.
- [ ] **Red**: el lobby de betsson.es carga desde el portátil, sin VPN y sin que salte el WAF.
- [ ] **Última ejecución buena** descargada en `outputs/demo/` (plan B) y **vídeo de respaldo** abierto en otra ventana.
- [ ] Ninguna ventana con `.env`, GitHub Secrets ni gestores de contraseñas a la vista. Notificaciones de Windows silenciadas (Asistente de concentración).
- [ ] Pantalla a 1366×768 o duplicada en el proyector, zoom del terminal grande.

## Vídeo de respaldo (grabarlo hoy, con una ejecución buena)

**Opción rápida: Xbox Game Bar (incluida en Windows)**
1. Abrir la ventana que se quiere grabar (Chrome del runner o el informe).
2. `Win + Alt + R` para empezar y parar. Graba **solo la ventana activa**, no el escritorio.
3. Los vídeos quedan en `C:\Users\<usuario>\Videos\Captures`. Moverlos a `D:\` y **no subirlos al repo**.

**Opción completa: OBS Studio**
- Fuente "Captura de ventana" solo de Chrome y del terminal, a 1366×768, 30 fps, MP4.
- Permite unir en un vídeo la ejecución y el recorrido por el informe.

**Sin credenciales en pantalla (innegociable)**
- Las credenciales salen de GitHub Secrets o de `.env`: **nunca** se teclean ni se muestran durante la grabación.
- El código tapa los campos del login; aun así, revisar el vídeo fotograma a fotograma en la parte del login antes de usarlo.
- No grabar la pestaña de GitHub Secrets, el `.env`, ni la salida de `gh secret`.
- Duración objetivo: 2 min (equivale al bloque 2). Recortar las esperas.
