# Betsson Intelligent Game Validation · Malackathon 2026

> **Summary (English).** An automated checker that validates casino games on Betsson **the way a player does**.
> The game is a third-party `<canvas>` with no usable DOM, so the checker *looks at the screen*: it finds amounts by
> their visible labels (OCR with RapidOCR) and buttons by multi-scale template matching (OpenCV). The provider's
> network traffic and the Betsson wallet are only used to **confirm** what is seen, never to replace it.
> It uses Betsson test accounts (assisted login: a person signs in, by the mentor's decision), opens a
> **Pragmatic Play** game in Real Play on **betsson.es (ES/EUR)** and validates two scenarios:
> **S1, spin completed** (`balance after = before − bet + win`, both in the game and in Betsson) and
> **S2, insufficient funds** (spin rejected, message in the market's language, balances unchanged).
> Each scenario ends as **PASS**, **FAIL**, **INCONCLUSIVE** (never an optimistic pass) or **PROVIDER_UI_CHANGED**
> (the provider changed its game UI: a warning, not an integration failure), with screenshots as evidence.
> Extensible by design: a provider is a folder (`betsson/profiles/<provider>/`; Pragmatic Play and Play'n GO are
> included, with `generic-vision` as fallback) and a market is a JSON file (`config/markets/`: Spain, Peru/PEN and
> Malta/English). It runs in **GitHub Actions** on a self-hosted runner in Spain (Betsson geoblocks GitHub's US
> runners) and publishes the HTML report as an artifact and on **GitHub Pages**: https://gitmobau.github.io/Malackaton/

Reto **Betsson "Intelligent Game Validation"** de la Malackathon 2026 (Málaga).

## Qué hace

Un comprobador que entra en Betsson **como un jugador**, abre un juego de tragaperras en **Real Play** y valida dos escenarios:

| Escenario | Qué se comprueba |
| --- | --- |
| **S1, tirada completada** | La tirada empieza y termina. La apuesta y la moneda son las del mercado. Se cumple `saldo después = antes − apuesta + ganancia`, tanto en el juego como en el saldo de Betsson |
| **S2, saldo insuficiente** | Con una cuenta sin saldo, la tirada se rechaza, el mensaje sale en el idioma del mercado y los saldos no cambian |

Principios:
- **Ve como un jugador.** El juego es un `<canvas>` de un tercero, sin DOM útil.
  - Los importes se localizan por su **etiqueta visible**, con OCR (RapidOCR).
  - Los botones se localizan por **plantilla multiescala**, con OpenCV.
  - Un clic nunca es una prueba: la prueba es lo que cambia en pantalla.
  - La red del proveedor y el monedero de Betsson solo **confirman** lo que se ve.
- **Lo dudoso nunca es PASS.** Si no se puede verificar con seguridad, el resultado es INCONCLUSIVE o FAIL.
- **Otros proveedores.** Escenarios, comprobaciones e informe no conocen ningún proveedor: solo usan la interfaz `ProviderProfile`.
  - Añadir un proveedor es añadir una carpeta `betsson/profiles/<proveedor>/` y pasar el test de contrato.
  - La carpeta contiene las pantallas de inicio, las etiquetas por idioma, las zonas en fracciones del canvas, las plantillas y los textos de saldo insuficiente.
  - Incluidos: **Pragmatic Play** y **Play'n GO**, con `generic-vision` como respaldo.
- **Cualquier mercado.** Un mercado es un archivo `config/markets/<mercado>.json` validado con pydantic, con moneda, formato numérico, idioma, textos esperados y apuesta mínima.
  - Los importes se leen siempre con `parse_money(texto, mercado)`.
  - Mercados incluidos: `es` (EUR, activo), `pe` (Perú, PEN) y `com` (Malta, EUR en inglés). Los dos últimos están configurados, pero sin cuenta de prueba.
- **Resistencia a cambios del proveedor.**
  - Las zonas fijas son solo una pista: el ancla es la etiqueta leída por OCR.
  - Hay tests con capturas alteradas (escala, color y desplazamiento).
  - Cada juego tiene una **huella** que se compara con la de la última ejecución buena.
  - Si el perfil no reconoce el juego, el resultado es `PROVIDER_UI_CHANGED`, no un FAIL de integración.
- **Ningún secreto en ningún sitio.**
  - Las credenciales van en `.env` en local y en GitHub Secrets en la CI.
  - Con la sesión iniciada no se graban trazas, HAR ni vídeo.
  - Un escáner bloquea la publicación si aparece alguna credencial en las evidencias.

## Arquitectura

```
config/markets/*.json ──► betsson/market (mercado, parse_money)
                                 │
betsson/site (A) ── web de Betsson: login asistido por CDP, saldo, abrir el juego ─────┐
betsson/game, vision, profiles (B) ── ojos sobre el canvas: OCR, plantillas, perfiles ──┤
                                                                                         ▼
betsson/core (contratos) ◄── betsson/checks (C): escenarios S1 y S2 ──► betsson/report (C)
                                                                        results.json + report.html
.github/workflows (D) ── CI: tests sin red en GitHub; ejecución real en el runner propio; artifact y Pages
```

| Área | Carpetas | Responsabilidad |
| --- | --- | --- |
| **A**, web de Betsson y mercados | `betsson/site/`, `betsson/market/`, `config/markets/` | Login asistido, saldo de Betsson, búsqueda y apertura del juego, avisos del regulador; esquema de mercado y `parse_money` |
| **B**, ojos y proveedores | `betsson/game/`, `betsson/vision/`, `betsson/profiles/`, `fixtures/` | `GameEyes` (leer saldo, apuesta y ganancia, girar, esperar el fin de la tirada, leer mensajes) y perfiles de proveedor |
| **C**, escenarios e informe | `betsson/core/`, `betsson/checks/`, `betsson/report/`, `tests/` | Contratos (`ProviderProfile`, `GameEyes`, `BetssonSite`, `CheckResult`, `RunResult`), comprobaciones de S1 y S2, informe |
| **D**, CI e infraestructura | raíz, `.github/` | Workflow, runner propio, escáner de secretos, informe web y Pages |

Los contratos de `betsson/core/` (modelos pydantic y `Protocol`) son el único punto de unión entre áreas. Cada área se probó contra simulaciones (`tests/fakes.py`) antes de integrarse.

## Instalación

```powershell
git clone https://github.com/gitmobau/Malackaton.git D:\Malackaton
cd D:\Malackaton
py -3 -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-betsson.txt -c requirements-betsson.lock
python -m playwright install chromium
pytest -m unit   # tests sin red: OCR sobre capturas, parse_money, contratos y perfiles
```

- `requirements-betsson.txt`: lo mínimo para el comprobador. `requirements-betsson.lock`: las versiones exactas con las que pasó la entrega (Python 3.14). `requirements.txt` añade el resto de librerías del hackathon y `requirements.lock` es el `pip freeze` completo, solo como referencia.

Más detalles para dejar el portátil listo en [Preparar el portátil](#preparar-el-portátil-todo-en-d).

## Cómo ejecutar

### Requisitos
- Windows con **Chrome del sistema** (o `CHROME_PATH` apuntando a `chrome.exe`) y el `.venv` preparado con `setup-portatil.ps1`.
- Conexión desde **España, sin VPN**: Betsson geobloquea otras IP (por eso la CI real va en el runner propio).
- Dos cuentas de prueba de betsson.es: **con saldo** (S1, tirada completa) y **sin saldo** (S2, saldo insuficiente). Las credenciales las escribe una persona en el login asistido; el comprobador nunca las teclea. Si se guardan, solo en `.env` (ver `.env.example`).

### Login asistido (antes de cada ejecución real)
Betsson rechaza el login automatizado aunque vaya a ritmo humano. Por eso, **con autorización de los mentores**, una persona inicia sesión a mano en un Chrome normal y el comprobador lo reutiliza por CDP. Sin stealth, sin huella falsa y sin resolver captchas.

| Cuenta | Escenario | Perfil de Chrome (fuera del repo) | Puerto CDP |
|---|---|---|---|
| `funded` (con saldo) | S1 | `D:\MAIKI\Malackathon\.chrome-profiles\es-funded` | 9222 |
| `empty` (sin saldo) | S2 | `D:\MAIKI\Malackathon\.chrome-profiles\es-empty` | 9223 |

Los puertos salen de `config/markets/es.json` (`site.browser_session.cdp_ports`) y la carpeta de perfiles se cambia con `CHROME_PROFILES_ROOT`. **Un perfil con sesión equivale a una credencial**: no se copia ni se sube.

1. **Abrir los dos Chrome.** Se lanzan como proceso normal de Chrome, no con Playwright, y siguen abiertos al terminar el script. Si ya hay uno en el puerto, se reutiliza.
   ```powershell
   python -m betsson.site.login_asistido --market es --account funded
   python -m betsson.site.login_asistido --market es --account empty
   ```
2. **Lo que hace la persona** en cada ventana: pulsa *Iniciar sesión*, escribe el usuario y la contraseña de esa cuenta y entra. **Nada más**: no toca el diálogo de límites de la DGOJ ni cierra la ventana.
   - Mientras escribe, el script no está conectado a Chrome, para no interferir con el antibot.
   - Con `--wait`, el script vigila cada 15 s y termina solo cuando detecta la sesión (tope de 10 min).
3. **Comprobar que la sesión está viva.** Abre y cierra una pestaña propia, con un tope de 20 s, y anota la hora:
   ```powershell
   python -m betsson.site.login_asistido --market es --account funded --check
   python -m betsson.site.login_asistido --market es --account empty --check
   ```
   - Salida `0` ("sesión VÁLIDA"): se puede lanzar.
   - Salida `1` ("AUSENTE O CADUCADA"): repetir el paso 2 en esa ventana.
   - Salida `2` (no hay Chrome en ese puerto): repetir el paso 1.
4. **Al final del día**, cerrar las dos sesiones:
   ```powershell
   python -m betsson.site.login_asistido --market es --account funded --logout
   python -m betsson.site.login_asistido --market es --account empty --logout
   ```

**Lo que hace el comprobador** (`BetssonSite.attach_cdp`):
- Se conecta al Chrome del puerto de la cuenta, abre **su propia pestaña** y la trae al frente.
- Comprueba la sesión **sin escribir nunca credenciales**. Si no hay sesión, el resultado es no concluyente; nunca intenta un login automatizado de reserva.
- Lee el saldo de la cabecera de Betsson, abre el juego y acepta el aviso previo y el diálogo de la DGOJ (5 h / 25 %).
- Al terminar cierra solo su pestaña: ni cierra Chrome ni hace logout.
- **No graba traza, HAR ni vídeo**, porque con la sesión iniciada la web descarga el perfil del cliente. Las evidencias son capturas de pantalla.

**Caducidad: la sesión de Betsson se cierra por inactividad tras unos 25-30 min** (observado hoy, no medido con exactitud).
- Hay que hacer el login asistido, o al menos el `--check`, **justo antes** de lanzar. Que el puerto CDP responda no garantiza que la sesión siga viva.
- Si caduca, el escenario sale **no concluyente** ("repetir el login asistido"), no como FAIL de integración.
- El límite de 5 h de la DGOJ es otra cosa: es la sesión de juego y lo gestiona el comprobador.

### Lanzar S1 y S2 en local
Con las dos sesiones vivas y el `.venv` activado:
```powershell
$env:GAME_SLUG = "big-bass-splash"
python -m pytest tests/test_real.py -m real --market es --headed --browser-channel chrome --tracing off --video off --screenshot off            # S1 y S2
python -m pytest tests/test_real.py -m real --market es --headed --browser-channel chrome --tracing off --video off --screenshot off -k real_s1  # solo S1 (9222)
python -m pytest tests/test_real.py -m real --market es --headed --browser-channel chrome --tracing off --video off --screenshot off -k real_s2  # solo S2 (9223)
```
- Resultados en `outputs/runs/<runId>/es/S1|S2/` (`results.json` y `report.html`), con el índice en `outputs/runs/<runId>/report.html`.
- Plan B si no hay cuenta vacía: `$env:S2_ACCOUNT="funded"; $env:S2_BET_TARGET="above_balance"`.

### Lanzar por la CI
Primero el login asistido; después:
```bash
gh workflow run "Validación de juegos" -R gitmobau/Malackaton --ref main -f markets=es -f scenarios=s1,s2 -f game_slug=big-bass-splash
```
- `scenarios` admite `s1`, `s2` o `s1,s2`. Solo se exige el Chrome del escenario pedido.
- El detalle está en [CI (GitHub Actions)](#ci-github-actions).

### Cambiar de juego
El juego se elige con **`GAME_SLUG`**, el slug de la URL de Betsson (`https://www.betsson.es/casino/<categoría>/<slug>`). Puede venir de tres sitios:
- la variable de entorno, en local;
- el input `game_slug` del workflow;
- la variable del repo `GAME_SLUG` (ahora `big-bass-splash`).

Ningún juego ni proveedor está fijo en el código:
- El comprobador busca el juego con el buscador del casino, lo abre en Real Play y el registro de perfiles detecta el proveedor por lo que se ve.
- Si no reconoce el proveedor, usa `generic-vision`.
- Si no consigue leer el juego, el resultado es `PROVIDER_UI_CHANGED` (no concluyente).

### Añadir un mercado
Un mercado nuevo es **un archivo** `config/markets/<id>.json`, validado con pydantic (`betsson/market/schema.py`), sin tocar código. Se parte de `es.json` (verificado en real) y se ajustan estos campos:
- `base_url`, `locale`, `language` y `timezone`.
- `currency`: `code` ISO, `symbols` (alias visibles como `€`, `S/` o `PEN`) y `symbol_position`.
- `number_format`: separador de miles, separador decimal y número de decimales. Todos los importes se leen con `parse_money(texto, mercado)`.
- `min_bet`: la apuesta mínima.
- `expected_texts` en el idioma del mercado: `insufficient_funds`, `balance_labels`, `bet_labels` y `win_labels`.
- `credentials_env`: solo los **nombres** de las variables de entorno, nunca los valores.
- `site`: `casino_path`; `browser_session.cdp_ports` (un puerto por cuenta, si hay login asistido); `session_limits` (patrones del diálogo del regulador, si existe).
- `real_execution_enabled`: `false` mientras no haya cuenta (el test real se salta con motivo).
- `verified`: `true` solo después de probarlo en real.

`com.json` (Malta, EUR, inglés) y `pe.json` (Perú, PEN) ya están configurados y desactivados por falta de cuenta. Cuando haya cuenta: `real_execution_enabled: true` y `-f markets=es,pe`.

## Cómo se informa

Cada ejecución deja sus resultados en `outputs/runs/<runId>/` (en la CI se publica como artifact):

| Archivo | Qué es |
|---|---|
| `outputs/runs/<runId>/report.html` | **Portada**: una tarjeta por escenario y mercado con su resultado, sus avisos (login asistido, juego cambiado, `PROVIDER_UI_CHANGED`) y una tira con lo que leyó en el canvas, más una matriz comprobación × escenario (pasa el ratón para ver el motivo). |
| `<market>/<S1\|S2>/report.html` | Informe del escenario: avisos, galería **«Lo que vio el comprobador»** (cada lectura con su captura, el texto OCR, el valor interpretado, la confianza y si se vio la moneda), tabla de comprobaciones con motivo, esperado, observado y evidencias. |
| `<market>/<S1\|S2>/results.json` | Lo mismo en JSON (esquema `RunResult`, `schema_version` 1). |

Campos clave de `results.json`:
- `outcome`: `PASS` · `FAIL` · `INCONCLUSIVE` · `PROVIDER_UI_CHANGED` (resumen del escenario). `verdict` es su versión binaria (PASS o FAIL).
- `results[]`: una entrada por comprobación de §3 (`id`, `status` PASS/FAIL, `failure_kind` `integration` | `inconclusive` | `provider_ui_changed`, `reason`, `expected`, `observed`, `evidence[]`).
- `readings[]`: lo que se leyó en pantalla (juego y web de Betsson), con su captura.
- `warnings[]`, `error`, `provider` (perfil detectado), `game`, `market`, `run_id`, fechas.
- Las rutas de evidencia son relativas a la carpeta del escenario. Nunca hay URLs con tokens, rutas locales ni credenciales (y `scan_secrets` lo vigila).

Qué significa cada resultado y cómo se decide:
- **PASS**: la comprobación se verificó en pantalla. La red y el monedero solo confirman, nunca sustituyen a la pantalla. Un escenario es PASS solo si todas sus comprobaciones lo son.
- **FAIL** (`integration`): se vio un error real. Por ejemplo: el saldo no cuadra (`después ≠ antes − apuesta + ganancia`, con la tolerancia del mercado), una tirada que no se rechaza con saldo insuficiente, un mensaje en otro idioma o el juego abierto en modo demo. Si hay al menos uno, el escenario es FAIL.
- **INCONCLUSIVE**: no se pudo verificar con seguridad (OCR dudoso, moneda no vista, sesión caducada, tirada sin fin visible…). Cuenta como FAIL y nunca como un PASS optimista. El motivo empieza por `inconclusive:`.
- **PROVIDER_UI_CHANGED**: el perfil del proveedor ya no reconoce el juego (deriva del proveedor). Es un aviso de mantenimiento, no un fallo de Betsson. Las comprobaciones de pantalla afectadas llevan ese motivo.
- Aparte, una **huella por juego** (franja de controles y ruta del juego) avisa de que el juego del proveedor ha cambiado desde la última ejecución buena, con capturas de antes y ahora. No cambia el veredicto.
- **Login asistido**: si una persona inició la sesión (autorizado por los mentores), `login_ok` lo dice con la hora y el informe lo muestra siempre. El resto es automático.

Apuesta (`BET_STRATEGY`): `step` por defecto, que cambia la apuesta una vez y juega con el nuevo valor. También `min` (baja a la mínima) y `current` (juega con la visible). Si la apuesta no cabe en el saldo, baja a la mínima. Se juega siempre con saldo de prueba, que recargan los mentores de Betsson cuando se agota.

En la CI:
- las evidencias se publican como artifact `evidencias-<mercado>-<run>`, solo si el escáner de secretos sale en verde;
- el job `pages` publica el informe web en **https://gitmobau.github.io/Malackaton/** y como artifact `informe-web-<run>`.

### Informes guardados
Índice en [`docs/informes/`](docs/informes/README.md):
- **Ejecución en PASS**: [`docs/informes/pass-20261015/`](docs/informes/pass-20261015/).
- **Fallo provocado**: [`docs/informes/fallo-provocado-20261015/`](docs/informes/fallo-provocado-20261015/). Demuestra que el test detecta errores. En la rama `demo/fallo-provocado`, la regla del saldo resta la apuesta dos veces. Resultado: S1 sale FAIL en `ingame_balance_consistent` y `betsson_balance_reconciles`, y fallan 14 tests unitarios. Al revertirlo, todo vuelve a verde. Esa rama nunca llega a `main`.

## Limitaciones conocidas
- **Login asistido.** Por decisión del mentor, una persona inicia sesión, porque el antibot de Betsson rechaza el login automatizado. El valor del comprobador está en el análisis del canvas, no en el formulario de login.
- **Las sesiones de Betsson caducan por inactividad** (unos 25-30 min). El login asistido se repite, o al menos se comprueba, justo antes de cada ejecución.
- **Runner propio.** La ejecución real necesita un equipo en España con escritorio, porque el navegador es visible. Los runners de GitHub tienen IP de EE. UU. y Betsson los geobloquea.
- **Saldo de prueba limitado.** Cada S1 gasta saldo de la cuenta de prueba; lo recargan los mentores.
- **Un solo mercado real.** `pe` y `com` están configurados, pero sin cuenta de prueba no se ejecutan en real.
- **Sin vídeo ni traza en la CI.** Con la sesión iniciada guardarían datos personales del cliente. Las evidencias son capturas.

## Documentación del equipo
| Ruta | Qué es |
| --- | --- |
| `docs/PREPARACION.md` | Requisitos, arquitectura, comprobaciones, decisiones y riesgos |
| `docs/PLAN_24H.md` | Áreas, hitos y plan de recortes |
| `docs/PREGUNTAS.md` | Preguntas a mentores y organización |
| `docs/demo/GUION.md` | Guion de la demo de 7 minutos |
| `CLAUDE.md`, `.claude/` | Instrucciones y agentes de Claude Code ([ECC](https://github.com/affaan-m/ECC)) que usó el equipo |

# Anexos

## Preparar el portátil (todo en D:)

Abre **PowerShell** (no hace falta como administrador).

1. **Si no tienes Git**, instálalo y abre una terminal nueva:

   ```powershell
   winget install --id Git.Git -e --location D:\DevTools\Git
   ```

2. **Clona el repo en D:** (si GitHub pide iniciar sesión, hazlo en la ventana que se abre):

   ```powershell
   git clone https://github.com/gitmobau/Malackaton.git D:\Malackaton
   ```

3. **Ejecuta el script de preparación:**

   ```powershell
   powershell -ExecutionPolicy Bypass -File D:\Malackaton\setup-portatil.ps1
   ```

   Añade `-ConOllama` si os toca NTT DATA (modelos de lenguaje en local).
   Se puede ejecutar varias veces sin problema.

4. **Abre una terminal nueva** y arranca Claude Code:

   ```powershell
   cd D:\Malackaton
   .venv\Scripts\Activate.ps1
   claude
   ```

   La primera vez te pedirá iniciar sesión con tu cuenta de Claude.

5. **Instala el plugin ECC (el mismo que usa el coordinador).** El repo lo declara en `.claude/settings.json`.
   Al abrir `claude` en el repo, acepta confiar en la carpeta e **instala `ecc@ecc`** cuando te lo pida.
   Si no te lo pide, ejecuta `/plugin` y busca `ecc` en el marketplace `ecc`.
   En las opciones del plugin, deja **`hooks_enabled = true`** y **`hook_profile = standard`**. Esta preferencia es personal y se guarda en tu configuración de usuario.
   Después ejecuta `/reload-plugins`.

6. **Comprueba que ECC está cargado** preguntándole a Claude: *"¿Qué skills y agentes de ECC tienes?"*.
   Con el plugin, los comandos llevan prefijo (`/ecc:plan`, `/ecc:code-review`, `/ecc:build-fix`) y deberías ver unos 77 agentes `ecc:*`.
   La copia suelta de `.claude/` (comandos sin prefijo) se queda solo para las sesiones en la nube.

### Dónde queda cada cosa

| Carpeta | Contenido |
| --- | --- |
| `D:\Malackaton` | Este repo y el entorno virtual de Python (`.venv`) |
| `D:\ClaudeCode` | Configuración, historial y plugins de Claude Code (`CLAUDE_CONFIG_DIR`) |
| `D:\DevTools` | Claude Code (`npm-global`) y, si el instalador lo permite, Git, Python, Node.js y Ollama |
| `D:\DevCache` | Cachés de pip y npm, navegadores de Playwright, modelos de Ollama y Hugging Face |

Si algún programa no admite instalarse en D:, el script lo instala en su carpeta por defecto y lo
avisa al final.

## CI (GitHub Actions)

Workflow `.github/workflows/validacion.yml` ("Validación de juegos"):
- **Tests `unit`** (sin red): en los runners de GitHub, en cada PR (sin los `slow`) y en cada push a `main` (todos). El job real ejecuta además los `browser` (navegador sin red externa, p. ej. la regresión de la traza) y los `real`.
- **Job `real`** (entra en Betsson): **solo a mano**, en Actions → *Validación de juegos* → *Run workflow*, indicando los mercados (por defecto `es`; `com` y `pe` están configurados pero desactivados por falta de cuenta). Se ejecuta en el runner propio del portátil de Alejandro, porque los runners de GitHub tienen IP de EE. UU. y Betsson los geobloquea.
- El job real usa **Chrome del sistema** (`--browser-channel chrome`): con él no salió captcha en el reconocimiento.
- El runner `portatil-alejandro` (`D:\DevTools\actions-runner`) lleva las etiquetas `self-hosted, windows, betsson-es` y **se arranca con `run.cmd` en una terminal, no como servicio**. Un servicio no tiene escritorio y el navegador visible (`--headed`) falla; el workflow lo comprueba.
- **Tras un reinicio o si se cierra su ventana, el runner se cae.** Para volver a arrancarlo:
  `start "runner" /min cmd /c "D:\DevTools\actions-runner\run.cmd"`.
  **Arranca solo al iniciar sesión**: la última línea de `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\unidad-D.cmd` (después del `subst`, que crea la unidad D:) lanza `run.cmd` minimizado.
- **Login asistido** (autorizado por el mentor): antes de lanzar el job real, una persona inicia sesión en Chrome (perfiles `es-funded` y `es-empty` en `D:\MAIKI\Malackathon\.chrome-profiles`, puertos CDP 9222 y 9223) y el comprobador se conecta por CDP. El workflow comprueba que los puertos responden y, si no, falla con "repetir login asistido". Los puertos se cambian con la variable del repo `CDP_PORTS`. El runner corre con el mismo usuario de Windows que ese Chrome.
- **Lanzar la validación (demo)**, con `gh` y la sesión iniciada:
  ```bash
  gh workflow run "Validación de juegos" -R gitmobau/Malackaton --ref main -f markets=es
  gh run watch -R gitmobau/Malackaton "$(gh run list -R gitmobau/Malackaton -w 'Validación de juegos' -L 1 --json databaseId -q '.[0].databaseId')"
  gh run download -R gitmobau/Malackaton -n "evidencias-es-<runId>-<intento>" -D outputs/ci   # el nombre aparece en el resumen del run
  ```
  Abre Chrome en el portátil del runner y gasta saldo: avisar al equipo antes.
- **Elegir escenarios**: input `scenarios` (por defecto `s1,s2`). `-f scenarios=s1` ejecuta solo la tirada completa (`-k "not real_s2"`) y `-f scenarios=s2` solo el saldo insuficiente (`-k "not real_s1"`); los tests sin red se ejecutan siempre. Solo se exige el puerto CDP del escenario pedido (S1 → 9222, S2 → 9223; con los dos, ambos). `CDP_PORTS` se escribe como `<puerto S1>,<puerto S2>`. Otro valor hace fallar el job.
- **Las sesiones de Betsson caducan por inactividad en unos 25-30 min**: el login asistido se hace **justo antes** de lanzar. Que los puertos CDP respondan no garantiza que la sesión siga viva.
- Secretos en *Settings → Secrets → Actions*: `BETSSON_<MERCADO>_USERNAME` y `BETSSON_<MERCADO>_PASSWORD` (y `..._EMPTY_...` para el escenario 2). Mismos nombres que en `.env.example`.
- Antes de publicar el artifact, `.github/scripts/scan_secrets.py` busca las credenciales en `outputs/`. Si encuentra alguna, no se publica nada. En el job real **no se graban** trazas, vídeos ni capturas automáticas de pytest-playwright (`--tracing off --video off --screenshot off`): con la sesión iniciada guardarían las cookies y el perfil del cliente (dirección, documento, KYC), que el escáner no reconoce. Si aun así aparece algún `.zip`, `.webm` o `.har`, nunca se publica y se borra del runner al terminar.
- **Informe web**: tras una ejecución a mano, el job `pages` genera `index.html` con el resumen PASS/FAIL y los enlaces a `report.html` y `results.json` de cada mercado (`.github/scripts/build_pages.py`). Solo usa evidencias que ya pasaron el escáner de secretos y nunca publica trazas ni vídeos. Siempre se sube como artifact `informe-web-<runId>-<intento>`.
- **GitHub Pages**: el plan de la cuenta no lo permite en un repo privado (HTTP 422). Si el repo pasa a público o la cuenta a Pro: *Settings → Pages → Source: GitHub Actions* y variable del repo `PAGES_ENABLED=true`. Ojo: la web de Pages es pública.
- **Probar el despliegue sin gastar saldo**: `gh workflow run "Validación de juegos" -R gitmobau/Malackaton -f markets=ninguno` (ningún mercado activo: no abre Chrome).
- `.github/CODEOWNERS`: el equipo usa una única cuenta compartida (`gitmobau`), así que todo es suyo. El reparto por áreas queda documentado en comentarios.

## Sesiones en la nube

ECC funciona también en claude.ai/code porque está dentro de `.claude/`. La red de esas sesiones está
limitada: lo que tenga que entrar en webs de Betsson o en la red del evento hay que ejecutarlo en el
portátil.
