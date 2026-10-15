# Traspaso del área A (Maiki): web de Betsson y mercados

Rama `feat/A-betsson-web`, con `origin/main` (esqueleto del PR #1) ya fusionado. Escrito el 15-oct a las 12:50 para migrar al portátil de Alejandro.

## Hecho y probado

- **Mercados** (`betsson/market/`, `config/markets/`)
  - `schema.py`: modelo pydantic `Market`, estricto (`extra="forbid"`, inmutable). Valida que `language` encaje con `locale`, que los separadores sean distintos y que `credentials_env` contenga NOMBRES de variables en MAYÚSCULAS, no valores. También tiene `money_tolerance` (por defecto 0.01).
  - `config/markets/es.json` (real, `verified: true`), `com.json` (Malta, en/EUR) y `pe.json` (Perú, PEN). Los dos últimos llevan `real_execution_enabled: false` y `verified: false`: la URL base y la estructura del sitio están **sin verificar**.
  - `loader.py`: `load_market(id)`, `list_markets()`.
  - `money.py`: `parse_money(texto, mercado) -> Money(amount: Decimal, currency: str | None, raw)`. **Tiene 4 bugs HIGH pendientes** (ver "Siguientes pasos", 1).
  - 35 tests unitarios en verde (`betsson/market/tests/test_money.py`, `pytestmark = unit`).
- **Web de Betsson** (`betsson/site/`), probada en real **sin login** contra betsson.es: lobby → rechazo de cookies → búsqueda → resultado por slug → página del juego → `GameLaunchError("pide iniciar sesión")`, que es lo correcto sin cuenta.
  - `BetssonSite(page, market, trace=..., pacer=...)`: `goto_lobby()`, `login()`, `is_logged_in()`, `read_balance() -> Money`, `find_game(slug)`, `open_game(slug) -> GameHandle(info, iframe, frame, canvas, iframe_url)`, `game_info_by_slug(slug)`.
  - `selectors.py`: selectores verificados (ver "Lo que sabemos de la web").
  - `credentials.py`: lee `.env` (el del worktree o el de la carpeta de arriba). El `repr` oculta los valores y los errores solo nombran las variables.
  - `tracing.py`: `ChunkedTrace` pausa la traza en el login (`stop_chunk` y `start_chunk`). `trace_paused()` es un context manager.
  - `pacing.py`: `Pacer`, al menos 2 s entre cargas (robots `Crawl-delay: 2`).
  - `__main__.py`: prueba de humo `python -m betsson.site`.

## Sin probar (hace falta la cuenta)

- `login()`: los selectores se vieron en real, pero nunca se ha enviado el formulario.
- `read_balance()`: `BALANCE_CANDIDATES` son **suposiciones** (`[data-test-id*=balance]`, `[class*=balance]`).
- `open_game()` tras el login: localizar el iframe y el canvas. Puede haber un paso más que no hemos visto, como el **límite de sesión de la DGOJ** u otro diálogo antes de lanzar el juego.

## En qué punto exacto quedó

- Todo commiteado y subido en el commit de traspaso.
- El agente `code-reviewer` terminó su revisión (resultado: WARNING, 0 CRITICAL, 4 HIGH, 8 MEDIUM). **No se ha aplicado ningún arreglo**: está todo abajo.
- Los acuerdos de contrato con C (paso 2) **no se habían empezado**.

## Siguientes pasos, en orden

### 1. Arreglar `parse_money` (HIGH: hoy puede devolver importes erróneos sin avisar)

Todos en `betsson/market/money.py`. Añadir un test por cada caso.

- **H1, separador inicial**: `",50 €"` y `".50 €"` dan 50 en lugar de 0,50, porque la regex `_NUMBER` exige un dígito al empezar.
  - Arreglo: si el carácter anterior al match es `.` o `,`, lanzar `MoneyParseError`.
- **H2, agrupar por espacio funde dos números**: `"0,20 200 giros"` da 0.20200 y `"12,50\n100"` da 12.50100.
  - Arreglo: usar solo espacios horizontales `[ \u00a0\u202f]`, nunca `\s`.
  - Y no permitir agrupar por espacio después de un decimal. Por ejemplo, `\d{1,3}(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)*|\d+(?:[.,]\d+)*`.
- **H3, faltan validaciones de formato** (`fmt.decimals` y `fmt.thousands_sep` no se usan).
  - Casos que salen mal:
    - es `"0.100"` da 100.
    - pe `"S/ 12.345"` da 12.345.
    - es `"1,23.456"` da 123.456.
    - es `"1.2345"` da 1.2345.
  - Arreglo:
    - Si los decimales superan `fmt.decimals`, lanzar `MoneyParseError` (no concluyente).
    - En miles, rechazar si el primer grupo tiene más de 3 cifras o empieza por 0.
    - Con un solo separador y 3 cifras detrás, aceptar miles solo si ese separador es `fmt.thousands_sep`. Si es el decimal del mercado, aceptarlo como decimal solo si las cifras no pasan de `decimals`.
    - Con dos separadores distintos, exigir que el último sea `fmt.decimal_sep`.
    - **Ojo**: hoy se acepta a propósito el formato inglés en `es` (`"€1,234.56"`, que se ve dentro del juego). Decidir con B y C si se mantiene. Si se mantiene, el caso de dos separadores es el único permitido fuera del formato del mercado.
- **H4, moneda por subcadena**: `"Europa 2024"` da EUR y `"Open 5"` da PEN (por "pen"). En `pe`, esto puede hacer que `_find_balance_locator` elija un elemento que no es el saldo.
  - Arreglo: buscar el alias con límites de palabra, `re.search(rf"(?<!\w){re.escape(sym)}(?!\w)", text, re.I)`. Para alias con letras, exigir además que estén pegados al número.

### 2. Contrato con C (Migue lo cerró por mensaje; su PR de contratos trae `betsson/core/`)

- `parse_money(texto, mercado, require_currency=False) -> betsson.core.money.Money`, con `currency` **obligatoria** (ISO):
  - Si el texto trae el símbolo de OTRA moneda conocida, se devuelve esa moneda (por ejemplo, "€ 12.50" en Perú da EUR). Las monedas conocidas salen de **todos** los `config/markets/*.json`, sin tabla fija en el código.
  - Si no trae ningún símbolo: con `require_currency=True` lanza `MoneyParseError`; con `False` usa la moneda del mercado.
- Función pública `detect_currency(texto, mercado) -> str | None`, para que B rellene `Reading.currency_seen`.
- `Market.currency_code` como property que devuelva `currency.code`. El Protocol `MarketContext` de C pide `id`, `currency_code`, `language` y `money_tolerance`.
- `read_balance() -> Reading(raw_text, money, currency_seen, confidence=1.0, evidence_path)`. Si el DOM falla, devuelve un Reading no concluyente, sin lanzar excepción.
- `login() -> bool` y `screenshot(name) -> Path`, con los campos de login tapados.
- `GameHandle`: añadir `play_mode: Literal["real","demo","unknown"]`, decidido por la web (por ejemplo, parámetros del `iframe_url`) y nunca supuesto, y `capture() -> np.ndarray` (canvas en RGB, con Pillow y numpy, que ya están en `requirements.txt`).
- Actualizar `test_currency_none_*` en `test_money.py`: con el contrato nuevo, "€ 12.50" en `pe` da `EUR`.

### 3. Arreglos MEDIUM de la revisión (`betsson/site/betsson_site.py`)

- **M6 (seguridad, el primero de este grupo)**: en `login()`, vaciar los campos en un `try/finally` **dentro** de `with trace_paused`, para que la traza solo se reanude con los campos vacíos aunque falle `fill` o `click`. Quitar `creds.username` del texto de `_visible_error()` antes de meterlo en `LoginError`.
- **M1, saldo equivocado o provisional**: preferir un `data-test-id` exacto del saldo total y comprobar la etiqueta con `market.expected_texts.balance_labels`. Exigir dos lecturas seguidas iguales, porque justo tras el login puede verse "0,00 €" mientras carga.
- **M2**: `read_balance` no debe hacer polling sin pausa. Reutilizar el `Money` ya leído en `_find_balance_locator` y capturar los errores de Playwright y de `MoneyParseError` si el nodo cambia.
- **M3, iframe equivocado**: en lugar de quedarse con el primer iframe grande, probar todos los candidatos y quedarse con el que tenga un canvas visible. Elegir el canvas más grande, no `.first`, y devolver la URL del frame que contiene el canvas.
- **M4**: capturar `playwright.sync_api.Error` en los bucles de frames (los iframes se recrean al lanzar el juego).
- **M5**: `find_game` debe ir al lobby si la URL no es `casino_path` o si no existe `SEARCH_OPEN_TRIGGER` (desde la página de un juego hay miniaturas pero no hay buscador).
- **M7**: llevar los textos regex (`SEARCH_OPEN`, `LOGIN_OPEN`, `LOGIN_TO_PLAY`, `SEARCH_INPUT_PLACEHOLDER`) y la ruta `/inicio` a `SiteConfig` en `config/markets/*.json`, con los valores actuales como valor por defecto.
- **M8**: si no se captura la API del juego, `log.warning` y marcar `provider_source="fallback"` en el `GameHandle`, para que el informe lo refleje.

### 4. Primera ejecución con login

`python -m betsson.site` (ver comandos). Ajustar el saldo, los diálogos previos al juego y el iframe con lo que se vea.

### 5. PR

Pasar el `code-reviewer` otra vez, abrir el PR de `feat/A-betsson-web` y fusionar en un hito.

### 6. `testpaths` de D

`testpaths = tests` **no recoge** `betsson/market/tests/`. Se le pidió a D que añada `betsson`; si no, mover los tests a `tests/` con un PR a C.

## Lo que sabemos de la web (betsson.es, 15-oct)

- **Cookies (OneTrust)**: el banner aparece **tarde** y no siempre. Se maneja con `page.add_locator_handler`: intenta `#onetrust-reject-all-handler` y, si no está, `#onetrust-pc-btn-handler` seguido de `.ot-pc-refuse-all-handler`. El handler **no** salta durante `wait_for_function` (no es una acción de Playwright).
- **Lobby**: las tarjetas son `gaming-game_thumbnail_v2[data-test-id="gaming-game-thumbnail-<gameId>"]`, con Shadow DOM abierto. El `gameId` lleva el proveedor como prefijo (`pragmaticPlayBigBassSplash`), pero el código no se apoya en eso.
- **Buscador**: el disparador es `[data-test-id="gaming-search-text"]`. Hay que hacer clic cuando la página está hidratada, por eso se reintenta. El campo tiene el placeholder "Búsqueda de juegos y proveedores". Los resultados están en `[data-test-id="search-modal-container"]`, y cada uno es un `a[data-test-id="game-thumbnail-title"]` con `href` `/casino/<categoría>/<slug>`. **Las tarjetas del diálogo NO llevan el gameId.**
- **URL directa del juego**: `/casino/juego/<slug>` no funciona (sale en blanco) y la categoría de la URL está localizada, así que se entra por el buscador.
- **API pública**: `GET /api/v2/games/<gameId>/` devuelve `id`, `slug`, `name`, `provider` ("PragmaticPlay"), `primaryType` y otros campos. Desde fuera da 400 `E_VALIDATION_INVALIDHEADER`: necesita las cabeceras `marketcode`, `brandid` y `x-obg-*`. Por eso `BetssonSite` **captura las respuestas que pide la propia página** (`page.on("response")`).
- **Login**: el botón "Iniciar sesión" lleva a `/inicio?returnUrl=…`. Los campos son `[data-test-id=email-input]` y `[data-test-id=password-input]`, y el botón es `[data-test-id=account-login-btn-1-button]`. Hay un iframe de Group-IB (antifraude).
- **Página del juego sin sesión**: muestra "Para jugar a este juego debes iniciar sesión · Ingresar y jugar". Sin login no hay iframe del juego.
- **Carga**: `domcontentloaded` a veces tarda más de 30 s (scripts de terceros y portátil cargado), así que `goto` usa `wait_until="commit"` y espera a que las tarjetas estén visibles (hasta 60 s).
- **CSP**: bloquea `eval()` dentro de `page.wait_for_function`, así que no hay que usarlo.

## Decisiones

- Navegador: **Chrome del sistema** (`channel="chrome"`), sin captcha en el reconocimiento. Se le preguntó a D si la CI usa lo mismo o Chromium (en `D:\DevCache\ms-playwright`; exportar `PLAYWRIGHT_BROWSERS_PATH`).
- Abrir el juego **como un jugador** (buscador), identificándolo por slug y no por texto. El proveedor sale de la API de Betsson. `BetssonSite` no conoce ningún proveedor.
- Tests de A dentro de `betsson/market/tests/` (`tests/` es de C).
- `betsson/core/` es de C. `Money` y `Reading` vienen de ahí cuando se fusione su PR.

## Problemas abiertos

- Selectores del saldo y lo que pasa tras el login: sin verificar.
- URL base de `pe` (`https://www.betsson.com/pe`) y de `com` (`/en`): sin verificar, no se ejecutan en real.
- `min_bet` de los mercados: es un valor orientativo; la mínima real depende del juego.
- Se hizo `pip install` de playwright, pydantic, pytest y python-dotenv en el `.venv` compartido antes del aviso de D (ya se le dijo). A partir de ahora, las dependencias se piden a D.

## Comandos

```powershell
# desde la raíz del worktree o del clon
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m pytest betsson/market tests -m unit -q   # 45 tests (35 de A)
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m betsson.site --no-login                  # humo sin cuenta (llega a "pide iniciar sesión")
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m betsson.site                             # con login (necesita .env)
#   opciones: --market es --slug big-bass-splash --query "texto" --headless
#   evidencias: outputs/smoke/<market>/<fecha>/ (01_lobby.png, 02_after_login.png, 03_canvas.png, trace-*.zip)
```

En otro portátil, cambia la ruta del `.venv`. Si se usa Chromium en lugar de Chrome, exporta antes `PLAYWRIGHT_BROWSERS_PATH`.

## `.env` (solo nombres; copia `.env.example`)

- `BETSSON_ES_USERNAME`, `BETSSON_ES_PASSWORD`: cuenta de prueba (Maiki la tiene; **todavía no estaba en el `.env`** cuando se migró).
- `BETSSON_ES_EMPTY_USERNAME`, `BETSSON_ES_EMPTY_PASSWORD`: cuenta sin saldo para el S2, si nos la dan.
