# Plan del hackathon

> El nombre del archivo es histórico. Según el PDF, el plazo de desarrollo es **hoy, 15-oct, de 10:15 a 20:00** (pendiente de confirmar).
> Si al final son 24 h reales, se estira cada bloque y se añade un bloque de robustez y bonus antes de congelar el código.
> Horas pensadas empezando hacia las 11:00. Ajustar los hitos si se empieza más tarde.

## Áreas

**A: Maiki** · **B: Alejandro** · **C: Migue** · **D: Guilli**

| Área | Responsabilidad | Carpetas (solo escribe su dueño) |
|---|---|---|
| **A, Betsson web y mercados**: **Maiki** (portátil del coordinador) | Cookies, login, saldo de Betsson, búsqueda y apertura del juego en Real Play. **Multimercado**: esquema de configuración, `es`/`com`/`pe`, `parse_money` y sus tests. **Coordinación**: mantiene `docs/` al día | `betsson/site/`, `betsson/market/`, `config/markets/`, `docs/` |
| **B, ojos sobre el juego y proveedores**: **Alejandro** | Motor genérico (OCR, comparación de imágenes, plantillas, visión con IA opcional), **perfiles de proveedor enchufables** (Pragmatic primero, después `generic-vision` y un segundo proveedor), detección de la tirada y de su fin, mensaje de saldo insuficiente | `betsson/game/`, `betsson/vision/`, `betsson/profiles/`, `fixtures/<proveedor>/` |
| **C, escenarios e informe**: **Migue** | Contratos, comprobaciones, regla del saldo, `results.json`, informe HTML, evidencias | `betsson/core/` (contratos: dueño único), `betsson/checks/`, `betsson/report/`, `tests/` |
| **D, CI e infraestructura**: **Guilli** | Esqueleto, workflow, runner propio en España (su portátil, que **no** puede ser el de Maiki), secretos, Oracle, Pages, README y demo | raíz, `.github/`, `requirements.txt`, `pytest.ini`, `setup-portatil.ps1` |

Reglas:
- **Extensibilidad**: la palabra "pragmatic" solo puede aparecer dentro de `profiles/pragmatic/` y `fixtures/pragmatic/`. Escenarios y comprobaciones hablan solo con `ProviderProfile`.
- Los contratos (`betsson/core/`) solo los cambia C; `requirements.txt` y `pytest.ini`, solo D. Los demás piden el cambio por PR, con un motivo de una línea.
- Las dependencias nuevas se añaden en los hitos.

## Arranque en paralelo (los 4 a la vez, cada uno con su sesión de Claude)

**Cómo se evita esperar a los demás:**
1. **Contratos v0 ya escritos** en `PREPARACION.md` §3: ids de las comprobaciones, forma de `results.json` y métodos de `ProviderProfile`. Cada área programa contra ellos desde el minuto 0. C los pasa a código (`betsson/core/`, con pydantic) en **30 min** como primer PR; si hay que cambiarlos, se pide por PR.
2. **Cada área tiene sus carpetas** (tabla de arriba). No hay archivos compartidos, así que no hay conflictos.
3. **`requirements.txt` con todas las dependencias desde el principio**: D añade al que ya existe `pytest`, `pytest-playwright`, `opencv-python`, `rapidocr-onnxruntime`, `pydantic`, `imagehash` y `jinja2`. Ya estaban `playwright`, `pillow`, `numpy`, `python-dotenv` y `anthropic`. Cada uno ejecuta `pip install -r requirements.txt` en su `.venv`. Nadie más toca `requirements.txt` hasta el primer hito.
4. **Cada área trabaja con simulaciones de las demás** hasta las fusiones (13:00, 15:30…).
5. **Cada Claude arranca con la misma frase**: "Soy el área X. Lee CLAUDE.md y docs/PLAN_24H.md §Arranque y trabaja solo en tus carpetas".

| Área | Empieza en el minuto 0 con… | No espera a… | Usa como simulación | Entrega para la fusión de las 13:00 |
|---|---|---|---|---|
| **A, Betsson web** | Lobby de betsson.es: cookies, buscar un juego de Pragmatic, abrirlo, localizar el iframe. Login en cuanto lleguen las cuentas | Nada | – | `BetssonSite`: `login()`, `readBalance()`, `openGame(slug)` → iframe/canvas |
| **B, ojos y proveedores** | **Demo pública de Pragmatic Play** (sin registro) para capturar pantallas y construir `profiles/pragmatic/` y el motor de OCR **sin necesitar login** | Las cuentas ni a A | Capturas en `fixtures/pragmatic/` | `GameEyes` + perfil: `readBalance/Bet/Win`, `spin()`, `waitSpinEnd()`, `readMessage()` probados con las capturas |
| **C, escenarios e informe** | Contratos en código (30 min), comprobaciones del escenario 1 y 2 e informe HTML | A ni B | `FakeBetssonSite` y `FakeGameEyes` con valores fijos | `runScenario(market, scenario)` → `results.json` + `report.html` con datos simulados |
| **D, CI e infra** | Esqueleto, pedir Oracle, registrar el runner propio, workflow con matriz de mercados, secretos | Nada | Un test ficticio | Workflow que ejecuta `pytest` en el runner y publica el artifact |

**Única dependencia real**: el esqueleto de D (unos 20 min). Mientras tanto, cada uno trabaja en su carpeta en local y lo sube después.

## Bloques

| Hora | A | B | C | D | Hito |
|---|---|---|---|---|---|
| 11:00–11:30 | Preguntas a los mentores (mercados con las cuentas españolas) | Diseño de `ProviderProfile` con C | Borrador de contratos, incluido `ProviderProfile` | Pedir Oracle; esqueleto | Áreas asignadas, stack confirmado |
| 11:30–13:00 | Login con la cuenta española, saldo de Betsson, apertura de un juego de Pragmatic; apuntar qué otros proveedores hay | Con A: **capturar todos los estados del juego**; motor OCR genérico y `profiles/pragmatic/` sobre las capturas | Comprobaciones del escenario 1 con datos simulados; `results.json`; test de contrato de perfiles | Workflow mínimo y runner propio en un portátil en España; secretos | – |
| **13:00** | | | | | **M1: escenario 1 de punta a punta en el primer mercado** (aunque sea básico) |
| 13:00–15:30 | `com` (EN/EUR) y `pe` (ES/PEN) configurados y probados con capturas y textos; `parse_money` con tests; escenario 2 (cuenta o apuesta por encima del saldo) | Detectar el fin de la tirada sin coordenadas fijas; mensaje de saldo insuficiente por idioma; moneda | Regla del saldo con tolerancia y nuevas consultas; informe HTML con evidencias y el proveedor detectado | El workflow ejecuta la matriz de mercados; informe como artifact | Almuerzo escalonado |
| **15:30** | | | | | **M2: 2 escenarios × mercados en local** |
| 15:30–17:30 | Robustez del login y del WAF; ayudar a B a capturar el segundo proveedor | **Resistencia a cambios**: anclas por OCR de etiquetas, autocalibración, test con capturas mutadas. **Segundo proveedor** como perfil de datos (sin tocar el núcleo) y/o `generic-vision` (si hay API); cruce con la red (bonus) | Cruce de las tres fuentes en el informe; **huella de referencia por juego y aviso `PROVIDER_UI_CHANGED`**; tapado de secretos | CI publica el informe en Pages; Oracle (Madrid) si ya está activo | **M3 (17:30): CI en verde o fallando con motivo claro, y un segundo proveedor** |
| 17:30–18:30 | Ejecuciones repetidas en los dos mercados | Arreglar inestabilidad | Pulir el informe | README (decisiones técnicas, cómo ejecutar) | – |
| **18:30** | | | | | **Código congelado**: solo arreglos con PR revisado |
| 18:30–19:45 | Ejecución final | Grabar el **vídeo de respaldo** | Revisar secretos en los artifacts (`grep`) | Ejecución final en CI y entrega | **Entrega antes de las 20:00** |
| Noche | – | – | – | – | Si somos finalistas: diapositivas y 2 ensayos de los 7 min |

## Puntos de integración fijos
Fusiones a `main` a las 13:00 (M1), 14:15, 15:30 (M2), 16:30, 17:30 (M3) y 18:30 (congelación). Antes de cada una: `pytest` en local y la revisión de un compañero (o, si no hay tiempo, del agente `code-reviewer`).

## Plan de recortes (por orden: lo primero que se cae)
1. Cruce con la red del proveedor.
2. GitHub Pages (basta el artifact de Actions).
3. Oracle (basta el runner en un portátil).
4. Perfil `generic-vision` funcionando (queda la interfaz y un Mock documentado).
5. Segundo proveedor real (queda un test de contrato con un perfil de ejemplo y un README de "cómo añadir un proveedor").
**Nunca se recorta**: 2 escenarios × mercados, la regla del saldo de Betsson, evidencias sin secretos, el workflow y **la arquitectura de perfiles de proveedor** (aunque solo haya uno funcionando).

## Demo (7 min, solo finalistas)
1. El problema (30 s).
2. Ejecución real grabada, con el vídeo de respaldo (2 min).
3. El informe PASS/FAIL con evidencias (1 min 30 s).
4. Cómo "ve como un jugador": OCR, plantillas y cruce de fuentes (1 min 15 s).
5. **Extensibilidad**: añadir un proveedor es añadir una carpeta de perfil; mostrar el segundo proveedor o `generic-vision` (45 s).
6. CI y arquitectura (45 s).
7. Siguientes pasos (30 s).
