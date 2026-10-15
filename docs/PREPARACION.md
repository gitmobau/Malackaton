# Preparación · Malackathon 2026 · Betsson "Intelligent Game Validation"

> Documento vivo. Se actualiza con cada "Nueva info". La fuente que manda es el PDF del reto de Betsson.
> Última actualización: 15-oct-2026 (v1.1): extensibilidad a otros proveedores y cuentas de prueba españolas.

## 1. El reto en una frase

Una prueba de concepto que, **como lo haría un jugador** (sin acceso al DOM del juego), entra en el casino de Betsson, **inicia sesión** con una cuenta de prueba con saldo, abre **cualquier juego de Pragmatic Play en Real Play** y valida **dos escenarios en dos mercados**, con un informe PASS/FAIL por comprobación y evidencias.

| Mercado | Idioma | Moneda |
|---|---|---|
| betsson.com | Inglés | EUR |
| betsson.pe (Perú) | Español | PEN (S/) |

### Escenario 1: tirada completada en Real Play
1. Abrir el lobby del mercado.
2. Iniciar sesión.
3. Abrir un juego de Pragmatic en Real Play.
4. Leer el saldo de Betsson antes de girar e identificar la apuesta mostrada y la moneda.
5. Localizar los controles dentro del juego y girar.
6. Verificar en pantalla que la tirada empezó y terminó.
7. Leer el resultado (ganancia) y los saldos de después.

Comprobaciones:
- La tirada empezó y terminó. Un clic no basta.
- La apuesta mostrada es la que se usó.
- La moneda es la del mercado.
- El saldo dentro del juego es coherente.
- El saldo de Betsson cuadra: **`después = antes − apuesta + ganancia`**. No hace falta ganar.

### Escenario 2: saldo insuficiente
Se usa una cuenta sin saldo utilizable, que se prepara con los mentores. Pasos: abrir el lobby, iniciar sesión, abrir el juego en Real Play, leer el saldo, intentar girar y verificar.

Comprobaciones:
- La tirada se rechaza.
- Aparece un mensaje de saldo insuficiente **en el idioma correcto**. Puede estar dentro del juego.
- La moneda es la correcta.
- El saldo de Betsson no cambia.
- El saldo dentro del juego no cambia.

### Entregables
1. **Repo de GitHub**: el comprobador, con configuración por mercado y **sin credenciales ni secretos**.
2. **Workflow de GitHub Actions**: ejecuta los dos escenarios una vez por mercado y publica el informe.
3. **Informe y evidencias**: PASS/FAIL por comprobación, escenario y mercado, incluido el saldo de Betsson, con capturas, traza o vídeo.
4. **Presentación** (solo finalistas): 7 min el 16 de octubre, con una ejecución que funcione y la explicación de las decisiones técnicas.

### Evaluación (sobre 100, más hasta 10 de bonus)
| Criterio | Peso |
|---|---|
| Los escenarios funcionan (2 × 2, con el saldo de Betsson) | **30** |
| "Ve como un jugador": lee la pantalla y verifica la respuesta del juego | **20** |
| Código y arquitectura, configuración por mercado, sin secretos | 15 |
| Informe y evidencias | 15 |
| Workflow de GitHub | 10 |
| Demo | 10 |
| Bonus (trabajo destacado no cubierto; requiere un motivo escrito) | 0–10 |

### Calendario (según el PDF; **hora de entrega pendiente de confirmar**)
| Cuándo | Qué |
|---|---|
| 15-oct 09:45 | Presentación del reto |
| 15-oct 10:15–20:00 | **Desarrollo, con apoyo de los mentores** |
| 15-oct 21:45 | Anuncio de finalistas |
| 16-oct 09:30 / 10:00 | Llegada de finalistas / presentaciones (7 min) |

### Lo que se repite en las grabaciones (refuerza el PDF)
- Los juegos son de terceros, van pintados en canvas y no tienen HTML útil.
- Hay que iniciar sesión con la cuenta que nos dan, abrir el juego y apostar. Hay que comprobar que el saldo baja al perder y sube al ganar, y que sin saldo no se puede jugar.
- Uso real: un test que se ejecuta con cada cambio de la plataforma, varias veces por semana.
- Valoran la **creatividad y el pensamiento lateral**. Sus vías de investigación son solo orientativas.
- Mencionan un documento con más detalle y "vías de investigación" (en un Drive) → **pedirlo**.

### Aclaraciones posteriores de los mentores (15-oct)
- **Se valora muchísimo que la solución se pueda extender a otros proveedores**, no solo a Pragmatic Play. → La arquitectura gira en torno a **perfiles de proveedor enchufables** (§3).
- **El juego del proveedor puede cambiar de un día para otro, y la responsabilidad es de Betsson**. El proveedor solo entrega el juego; si al día siguiente cambia la slot o su interfaz, Betsson tiene que garantizar que sigue funcionando en su web (si no, el proveedor se va a otro operador). → La solución tiene que **resistir cambios en la interfaz del proveedor** y, cuando no pueda, **avisar de que el juego ha cambiado**, distinguiéndolo de una integración rota (§3).
- **Ya no hace falta VPN**: nos están creando **cuentas de prueba de España**. Se prueba en real **solo betsson.es**; Perú y Malta (betsson.com) ya no.
- **Pero la solución tiene que poder adaptarse a todos los mercados**: si se activa Perú, tiene que reconocer los soles (`S/`, PEN), el español de Perú, su formato numérico, etc. → **Un mercado nuevo = un archivo de configuración**, sin tocar el código (§3).

## 2. Lo que sabemos del sitio (exploración del 15-oct desde España, sin VPN y sin login)

Las capturas están en `docs/recon/`.
- Desde España, betsson.com, /sv, .gr y .co **redirigen a betsson.es**, con la cabecera `x-obg-country-block: Country blocked`. Esto se decide **por la IP**, no por la cuenta. Ahora no se usa VPN (hay cuentas españolas), pero **la CI tiene que ejecutarse desde España**: los runners de GitHub tienen IP de EE. UU.
- Antibots: **AWS WAF Bot Control** (`aws-waf-token`, `/mp_verify`), **Group-IB** y FullStory. Con Chrome normal no salió ningún captcha.
- El lobby de betsson.es usa **Shadow DOM** (componentes Stencil):
  - Cada tarjeta tiene `data-test-id="gaming-game-thumbnail-<gameId>"` y su título enlaza a `/casino/<categoria>/<slug>`.
  - El scroll es el del contenedor `div.content-wrapper`, no el de la ventana.
  - Las imágenes cargan al llegar a ellas (`loading=lazy`).
- Cookies (OneTrust): primero `#onetrust-pc-btn-handler`, luego `.ot-pc-refuse-all-handler`.
- API pública: `GET /api/v2/games/{gameId}/`. Devuelve `provider`, `slug`, `launchType`, etc.
- `robots.txt`: `Crawl-delay: 2`.
- Supuesto: la estructura de .com y .pe será parecida porque es la misma plataforma, pero **está por verificar**.

## 3. Arquitectura propuesta

```
CLI / Playwright Test ── Scenario (S1 | S2) × Market (com | pe)
        │
        ├─ BetssonSite (DOM, legítimo: es la web de Betsson)
        │     cookies · login · leer saldo Betsson · abrir juego en Real Play
        ├─ GameEyes (canvas, "como un jugador"), genérico, no conoce ningún proveedor
        │     OCR (RapidOCR) · diff de imagen y plantillas multiescala (OpenCV) · VisionProvider (IA opcional, Mock)
        ├─ ProviderProfile (enchufable, uno por proveedor, elegido por registro)
        │     detect(iframeUrl, captura) · introScreens · zonas BALANCE/BET/WIN · spin · minBet
        │     señales de fin de tirada · textos de saldo insuficiente por idioma · patrón de red (opcional)
        │     profiles/pragmatic/ (el primero) · profiles/generic-vision/ (proveedor desconocido, vía IA)
        ├─ Checks → results.json (PASS/FAIL por comprobación, con motivo y evidencias)
        ├─ Evidence: outputs/runs/<runId>/<market>/<scenario>/ (capturas, vídeo, traza, red filtrada; outputs/ no se sube a git)
        └─ Report: HTML + JSON → artifact de Actions + GitHub Pages
```

Principios:
- **Se extiende a otros proveedores (lo valoran muchísimo)**:
  - Los escenarios y las comprobaciones **no saben nada de Pragmatic**. Solo hablan con la interfaz `ProviderProfile`.
  - Añadir un proveedor = añadir una carpeta `profiles/<proveedor>/` (datos: zonas, plantillas, textos y un `detect`), **sin tocar el núcleo**.
  - El perfil `generic-vision` intenta jugar con un proveedor desconocido usando solo IA con visión: localiza el botón de girar, el saldo y la apuesta. Así funciona aunque no haya perfil.
  - Lo demostramos con un **segundo proveedor** si da tiempo, y siempre con un test de contrato que valida cualquier perfil.
  - Tenerlo en cuenta para el bonus y para la puntuación de arquitectura (15).
- **Multimercado por configuración**:
  - `config/markets/<mercado>.json`: URL base, `locale` (`es-ES`, `en-MT`, `es-PE`…), moneda ISO y **todos sus símbolos y alias** (`€`/`EUR`, `S/`/`S/.`/`PEN`/`soles`), separadores de miles y decimales, posición del símbolo, decimales, textos esperados por idioma (saldo insuficiente, etiquetas BALANCE/SALDO/CRÉDITO…), selectores o textos de la web de Betsson que cambien por mercado, apuesta mínima y zona horaria.
  - Un **validador de esquema** (pydantic) rechaza configuraciones incompletas. Añadir Perú es copiar una plantilla y rellenarla.
  - Lectura de dinero genérica: `parse_money(texto, mercado)` → `Money(amount: Decimal, currency)`, con tests para EUR (`1.234,56 €`, `€1,234.56`) y PEN (`S/ 1,234.50`, `S/. 1234.5`).
  - La comprobación `currency_matches_market` compara lo **leído en pantalla** con la configuración, sin darlo por supuesto.
  - Los perfiles de proveedor guardan sus textos **por idioma**, no por mercado: un mercado nuevo con un idioma conocido no necesita tocar los perfiles.
  - **Hay que demostrarlo sin cuenta**: `es` se ejecuta en real; `com` (Malta, EN/EUR) y `pe` (ES/PEN) vienen configurados y **probados con capturas y textos de ejemplo** (tests unitarios de formato y moneda). En el informe aparecen como "mercado configurado; ejecución real desactivada: sin cuenta".
- **Resistente a cambios del proveedor**:
  - **Anclas semánticas, no posiciones**: localizar los importes por su etiqueta visible ("BALANCE"/"CREDIT"/"SALDO", "BET"/"APUESTA", "WIN"/"GANANCIA") con OCR. El botón de girar se busca con plantillas a varias escalas o con visión. Las zonas en fracciones son solo una pista inicial.
  - **Autocalibración**: si el perfil no encuentra algo, se recalibra en esa misma ejecución (OCR de etiquetas, plantillas o `generic-vision`) y deja anotado qué cambió.
  - **Detección de deriva**: se guarda una huella de referencia por juego (hash perceptual de las pantallas clave, URL y versión de los recursos del iframe). Si cambia, el informe dice **"el juego del proveedor ha cambiado desde la última ejecución"**, con capturas antes y después.
  - **Decisión del 15-oct (cerrada)**: proveedor **desconocido** → `ProviderRegistry.resolve()` devuelve `generic-vision` (sin excepción). Proveedor **conocido** cuya interfaz ya no reconoce su perfil → el registro de perfiles (`ensure_recognized()`) lanza `ProviderUIChanged`, no `GameEyes`.
  - **Distinguir la causa**: `PROVIDER_UI_CHANGED` (el perfil no reconoce el juego: aviso para mantenerlo, comprobación no concluyente) frente a fallo de integración (saldo que no cuadra, tirada no rechazada…): **FAIL real**.
  - **Test de resistencia**: se pasa el perfil contra capturas "mutadas" (desplazadas, a otra escala, recoloreadas) para demostrar que no se rompe.
- **Ver como un jugador**: la prueba principal es lo que se ve (OCR o visión de BALANCE, BET, WIN, del mensaje y de la moneda). La red de Pragmatic y el monedero de Betsson **solo confirman**: dan bonus, pero nunca sustituyen a la pantalla.
- **Cruzar tres fuentes**: pantalla, respuesta de red de la tirada y monedero de Betsson. Si las tres coinciden, el resultado es muy sólido. Si no coinciden, eso ya es un hallazgo.
- Lo dudoso cuenta como **FAIL con motivo "no concluyente"**, nunca como un PASS optimista.
- Los clics se calibran con plantillas o visión sobre el canvas, nunca con coordenadas absolutas en píxeles.
- **Apuesta mínima** siempre, para no vaciar las cuentas.

### Comprobaciones (ids para `results.json`)
| Escenario | Id | Comprobación |
|---|---|---|
| S1, S2 | `login_ok` | Sesión iniciada |
| S1, S2 | `real_play` | Juego en Real Play (no demo o "fun") |
| S1, S2 | `currency_matches_market` | La moneda visible es la del mercado |
| S1 | `betsson_balance_before` | Saldo de Betsson leído antes |
| S1 | `wager_read` | Apuesta visible leída |
| S1 | `spin_started` / `spin_completed` | La tirada empezó / terminó (señal visible) |
| S1 | `payout_read` | Ganancia leída (puede ser 0) |
| S1 | `ingame_balance_consistent` | Saldo del juego = antes − apuesta + ganancia |
| S1 | `betsson_balance_reconciles` | Saldo de Betsson = antes − apuesta + ganancia |
| S1 | `wager_is_used_wager` | La apuesta mostrada es la que se descontó |
| S2 | `spin_rejected` | No se completa una tirada pagada |
| S2 | `insufficient_message_language` | Mensaje de saldo insuficiente visible y en el idioma del mercado |
| S2 | `betsson_balance_unchanged` / `ingame_balance_unchanged` | Los saldos no cambian |

## 4. Incógnitas

| # | Incógnita | Supuesto por defecto | Qué cambia según la respuesta | A quién / cuándo |
|---|---|---|---|---|
| 1 | **Hora de entrega** (el PDF dice 20:00; el equipo hablaba de 24 h) | Entrega hoy a las 20:00 | Si son 24 h de verdad, se amplía `PLAN_24H.md` | Mentores, **ya** |
| 2 | ~~¿Qué mercados se prueban?~~ **Respondida**: solo betsson.es en real; la solución tiene que adaptarse a todos | – | – | – |
| 2c | ¿Pueden activar Perú o Malta más adelante (aunque sea en la demo)? ¿Tienen capturas de esos mercados? | No | Si sí: ejecución real de `pe`/`com` sin tocar el código, lo que demostraría el multimercado | Mentores, 13:00 |
| 3 | Cuentas: cuántas, si hay una por mercado y cuándo llegan | 1 por mercado más 1 sin saldo | Orden de trabajo de las áreas A y B | Mentores, ya |
| 4 | Escenario 2: ¿cuenta a cero o vale subir la apuesta por encima del saldo? | Ellos preparan la cuenta a cero | Si vale subir la apuesta, no dependemos de ellos | Mentores, ya |
| 5 | ¿Se permite un runner propio en España (portátil u Oracle en Madrid)? ¿El WAF acepta la IP de esa máquina? | Runner propio en un portátil del equipo | Toda la arquitectura de CI | Mentores, antes de las 12:00 |
| 6 | Documento de "vías de investigación" | Existe y nos lo dan | Ideas y posibles atajos | Mentores, ya |
| 7 | API de IA (u OCI Generative AI) | No hay; RapidOCR y OpenCV | Si la hay: visión para el mensaje, los controles y una segunda lectura | Equipo y mentores, ya |
| 8 | ¿Repo público? ¿Informe en GitHub Pages? | Artifact y Pages, sin datos de cuentas | Revisar fugas de secretos antes de publicar | Equipo, 12:00 |
| 9 | ¿El saldo de Betsson se ve durante el juego? ¿Cuánto tarda en actualizarse? | Hay que cerrar el juego o recargar; se actualiza con retraso | Diseño de `betsson_balance_reconciles` | Primera prueba real |
| 10 | Formato de números por mercado (`1,234.56` / `S/ 1,234.50`) | Se define en `config/markets/*.json` | Lectura de los números del OCR | Primera prueba real |
| 11 | Pantallas de inicio de Pragmatic (sonido, "continuar", tutorial) | Hay alguna y se puede cerrar | Perfil de Pragmatic | Primera prueba real |
| 12 | Perfiles del equipo | Roles A–D sin asignar | Quién va a cada área | Equipo, **ya** |
| 13 | Plazo de activación de Oracle | Horas | Si llega tarde, se usa un portátil como runner | Pedirlo ya |
| 14 | ¿Qué otros proveedores hay en el mercado probado, y cuál usar como segundo de demostración? | Uno muy común con interfaz distinta (Play'n GO, NetEnt, Relax…) | Qué perfil hacer después de Pragmatic | Mentores o lobby, 13:00 |
| 16 | ¿Hay versiones anteriores de un juego, o un juego "cambiado", para probar la resistencia? | No; lo simulamos mutando capturas | Si las hay, demo de deriva real | Mentores, 13:00 |
| 15 | ¿Cómo medirán la extensibilidad? (¿añadiendo un proveedor en directo? ¿solo revisando el código?) | Revisando el código y un segundo perfil | Cuánto invertir en el perfil genérico por visión | Mentores, ya |

## 5. Decisiones

### Cerradas por el PDF
- Mercados: .com (EN/EUR) y .pe (ES/PEN).
- Proveedor: Pragmatic Play, cualquier juego.
- Real Play con cuentas de prueba.
- Los 4 entregables y los criterios de evaluación.
- Tecnología libre.
- ~~VPN obligatoria~~ → **ya no hace falta VPN**: cuentas de prueba españolas (mentores, 15-oct).
- **Extensibilidad a otros proveedores**: muy valorada (mentores, 15-oct).
- **Mercado real: solo betsson.es** (ES/EUR); **adaptable a todos los mercados** (Perú con soles, Malta…) (mentores, 15-oct).

### Tomadas (15 de octubre, al confirmar)
| Decisión | Detalle |
|---|---|
| Stack | **Python** (aprovecha el `.venv` y `setup-portatil.ps1` del repo): **pytest + pytest-playwright** (traza, vídeo y capturas con `--tracing on --video on --screenshot on`), navegador visible (en CI, con xvfb si el runner es Linux). OCR con **RapidOCR** (solo pip, sin binarios del sistema); plantillas multiescala y comparación de imágenes con **OpenCV**; hash perceptual con **imagehash**; contratos y configuración con **pydantic**; informe HTML con **Jinja2**. *Cambiado desde TypeScript el 15-oct*: el repo ya estaba montado en Python y la visión y el OCR son mejores ahí |
| Git | Ramas `feat/<área>-<tema>`, PR pequeño con revisión rápida (de un compañero o del agente `code-reviewer`), squash a `main` en los hitos. Sustituye a los commits directos a `main` del `CLAUDE.md` original |
| Proveedores | Interfaz **`ProviderProfile`** con registro y detección automática por la URL del iframe o por la captura. Perfiles como datos en `profiles/<proveedor>/` (zonas en **fracciones del canvas**, plantillas, textos por idioma). Primero `pragmatic`; perfil de respaldo `generic-vision`. Test de contrato común para todos los perfiles |
| Mercados | `config/markets/{es,com,pe}.json` validados con pydantic. `es` se ejecuta en real; `com` y `pe` configurados y probados con capturas y textos. `parse_money` genérico. Matriz de CI por mercado con `enabled` |
| Secretos | `.env` en local y GitHub Secrets en CI. **La traza de Playwright graba lo que se escribe**: se pausa durante el login, los campos se tapan en capturas y vídeo, y se hace un `grep` de los artifacts antes de publicar |
| Resultado | `results.json` con PASS/FAIL por comprobación, escenario y mercado, más el informe HTML |
| Apuesta | La mínima |
| VPN | **No se usa** (cuentas españolas). Se instala solo si algún mercado lo exige más tarde |
| Runner de CI | **Propio en España**: el portátil de Alejandro como runner de GitHub Actions; Oracle (región Madrid) si se activa a tiempo |
| Modo de trabajo | **Un solo portátil (el de Alejandro; antes el de Maiki)**: 4 sesiones de Claude, una por área, cada una en su worktree de git, con Remote Control para que cada miembro se conecte. Si hay atasco, un área pasa a un segundo portátil |
| Oracle | Pedir **ya** una cuenta (un miembro con correo `@uma.es`). Es un seguro, no una dependencia |
| Git | Ramas `feat/<área>-<tema>`, PR pequeño, 1 revisión, squash merge, main protegida, fusiones en los hitos |
| Idioma | Código en inglés; documentación e informe en español (el informe puede ser bilingüe) |
| Áreas | **A: Maiki** (también coordina `docs/`) · **B: Alejandro** · **C: Migue** · **D: Guilli** (el runner de CI va en el portátil de Alejandro) |

### Aplazadas
| Decisión | Límite |
|---|---|
| Segundo proveedor de demostración | 13:00 (se implementa entre las 15:30 y las 17:30) |
| Juego concreto de Pragmatic | 12:00 |
| Runner de CI: portátil u Oracle | 13:00 |
| Visión con IA o solo OCR | 13:00 |
| Cómo provocar el escenario 2 | 13:00 |
| Recortes | 16:30 |
| Congelar el código | 18:30 |

## 6. Riesgos

| Riesgo | Prob. / Impacto | Mitigación |
|---|---|---|
| Geobloqueo o WAF en la CI (los runners de GitHub tienen IP de EE. UU.) | Alta / Alto (10 pts más el informe) | **Runner propio en España**: un portátil o Oracle en Madrid. Como último recurso, que el job se ejecute y deje evidencias con el motivo |
| Captcha o WAF en el login | Media / Alto | Chrome con ventana visible, ritmo humano, 2 s entre cargas; preguntar si hay lista blanca |
| Acoplar el código a Pragmatic (penaliza la extensibilidad) | Media / Alto | Nada de "pragmatic" fuera de `profiles/pragmatic/`; test de contrato de perfiles; revisión en cada PR |
| El proveedor cambia la interfaz y el perfil deja de reconocerla | Alta (en producción) / Alto | Anclas semánticas, autocalibración, `generic-vision` de respaldo, detección de deriva con aviso `PROVIDER_UI_CHANGED` |
| El perfil `generic-vision` depende de una API de IA | Media / Medio | Si no hay API, se queda como interfaz y un Mock documentado, y la extensibilidad se demuestra con un segundo perfil de datos |
| El OCR lee mal números o símbolos | Alta / Alto (20 pts) | Recortar la zona exacta, ampliarla y pasarla a blanco y negro; limitar los caracteres; validar contra la regla del saldo; segunda opinión con visión |
| Pantallas de inicio, sonido o tutorial de Pragmatic | Alta / Medio | Detectarlas con plantilla o visión y cerrarlas, según el perfil |
| Secretos en traza, vídeo o informe | Media / Alto (descalifica) | Pausar la traza en el login, tapar los campos, `grep` antes de publicar |
| Cuentas sin saldo por repetir pruebas | Media / Medio | Apuesta mínima; avisar a los mentores para que recarguen |
| Retraso en el monedero de Betsson | Media / Medio | Reconsultar hasta que cambie, con tiempo límite |
| Tiempo: unas 9 h | Alta / Alto | Prueba de punta a punta a las 13:00, hitos fijos, plan de recortes |

## 7. Tareas inmediatas

| Orden | Id | Tarea | Resp. | Terminado cuando… |
|---|---|---|---|---|
| 1 | P1 | Portátiles: `setup-portatil.ps1` del repo (Git, Python, `.venv`, Chromium de Playwright, Claude Code), `pip install -r requirements.txt`, `gh auth status`, ECC. En Windows, además: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` | todos | `pytest --version` y `python -m playwright --version` funcionan en el `.venv` (`gh` portable en `D:\DevTools\gh`) |
| 1 | P1b | ~~VPN~~ → Comprobar que cada portátil abre el mercado de las cuentas españolas (sin VPN) | todos | El lobby carga y no salta el WAF |
| 1 | P2 | Acceso de escritura al repo `gitmobau/Malackaton`, clonarlo y configurar `git config` | todos | `git pull` funciona |
| 1 | P3 | Hacer las preguntas urgentes a los mentores (`PREGUNTAS.md` §1) | 1 persona | Respuestas apuntadas |
| 1 | P4 | Pedir la cuenta de Oracle en la encuesta del correo | 1 persona con `@uma.es` | Formulario enviado |
| 2 | P5 | Esqueleto: paquete `betsson/` con las carpetas de cada área, `requirements.txt` ampliado, `pytest.ini` / `conftest.py` (1366×768, DPR 1, traza, vídeo y capturas), `.gitattributes` (`eol=lf`), `.env.example`, plantilla de PR y CODEOWNERS | D | `pytest` en verde (con un test ficticio) en todos los portátiles |
| 2 | P6 | Prueba real: login con la cuenta española, abrir un juego de Pragmatic y **capturar todos los estados** (reposo, girando, ganancia, sin saldo, pantallas de inicio) en `fixtures/pragmatic/`. Apuntar también qué otros proveedores hay | A + B | Capturas de referencia y una traza sin secretos |
| 2 | P7 | Contratos: tipos de `results.json`, ids de las comprobaciones, configuración por mercado **e interfaz `ProviderProfile`** con su test de contrato | C (+ B en el perfil) | Revisado por los 4 |
| 3 | P8 | Primer workflow de GitHub Actions con un runner propio en España (portátil) | D | Un job lanzado a mano se ejecuta en el runner |

## 8. Cómo actualizar este documento
Con cada "Nueva info": cambiar las incógnitas, cerrar las decisiones que se puedan, ajustar riesgos y plan, y apuntarlo en el registro.

### Registro de cambios
- 15-oct, v0.1: plan de preparación genérico (24 h, sin bases).
- 15-oct, v0.2: VPN obligatoria (lo dice la organización).
- 15-oct, v1.0: llega el PDF del reto. Login, Real Play, Pragmatic, 2 escenarios × 2 mercados, GitHub Actions y criterios de evaluación. Desarrollo hasta las 20:00. Oracle disponible.
- 15-oct, **v1.7**: decisión cerrada: proveedor desconocido → `generic-vision`; deriva de un proveedor conocido → `ProviderUIChanged` desde el registro de perfiles.
- 15-oct, v1.6: migración al portátil de Alejandro (más RAM y CPU) con la misma ruta `D:\MAIKI\Malackathon`; un `handoff/<X>.md` por área y scripts en `coordinacion/`. Runner de CI en el portátil de Alejandro; rapidocr v3.
- 15-oct, v1.5: todo en un solo portátil (Maiki) con un worktree de git por área y Remote Control; `.venv` compartido; runner de CI también en ese portátil.
- 15-oct, v1.4: áreas asignadas (A Maiki, B Alejandro, C Migue, D Guilli). **Stack cambiado a Python** (el repo ya estaba preparado; mejor OCR y visión). Ramas por área + PR. `CLAUDE.md` fusionado con el original del repo.
- 15-oct, v1.3: solo betsson.es en real, pero **adaptable a todos los mercados** → configuración por mercado validada, `parseMoney` genérico, textos por idioma, `com` y `pe` configurados y probados con capturas.
- 15-oct, v1.2: el juego del proveedor puede cambiar en cualquier momento y Betsson responde de ello → anclas semánticas, autocalibración, detección de deriva (`PROVIDER_UI_CHANGED`) y test de resistencia. Plan de arranque en paralelo de las 4 áreas (`PLAN_24H.md`).
- 15-oct, v1.1: extensibilidad a otros proveedores muy valorada → `ProviderProfile` enchufable, perfil `generic-vision` y segundo proveedor como objetivo. Cuentas de prueba españolas → sin VPN; runner de CI en España; mercados por confirmar.
