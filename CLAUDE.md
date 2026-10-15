# Malackaton: instrucciones para Claude

Somos un equipo de 4 en la **Malackathon 2026** (Málaga) y nos ha tocado el reto de **Betsson**.
El uso de IA está permitido por la organización. Responde siempre en **español**.

Documentos vivos (la fuente principal es el primero):
- `docs/PREPARACION.md`: reto, arquitectura, comprobaciones, incógnitas, decisiones y riesgos.
- `docs/PLAN_24H.md`: áreas, arranque en paralelo, bloques horarios e hitos.
- `docs/PREGUNTAS.md`: preguntas abiertas y respondidas.

## El reto (Betsson "Intelligent Game Validation")

Comprobador que, **como un jugador** (el juego es un canvas de terceros sin DOM útil), entra en Betsson,
inicia sesión con una cuenta de prueba, abre un juego de **Pragmatic Play en Real Play** y valida dos escenarios:
- **S1, tirada completada**: la tirada empieza y termina. La apuesta y la moneda son correctas. Se cumple `saldo después = antes − apuesta + ganancia`, tanto en el juego como en Betsson.
- **S2, saldo insuficiente**: la tirada se rechaza, el mensaje sale en el idioma del mercado y los saldos no cambian.

Resultado: PASS/FAIL por comprobación, con evidencias (capturas, traza, vídeo), ejecutado en GitHub Actions.
En real se prueba en **betsson.es (ES/EUR)** con cuentas de prueba españolas, sin VPN.

Lo que más se valora:
1. Que funcione.
2. Que "vea como un jugador".
3. Que **se pueda extender a otros proveedores**.
4. Que **se adapte a cualquier mercado** (Perú/PEN, Malta/EUR en inglés…).
5. Que **resista los cambios del juego del proveedor**.

## Modo hackathon (tiene prioridad sobre las reglas genéricas de ECC)

ECC está copiado en `.claude/`. Sus reglas piden TDD obligatorio y 80 % de cobertura: **aquí no aplican**.
Prioridades, en este orden:
1. Algo que funcione de punta a punta lo antes posible (primer hito a las 13:00).
2. Que la demo sea fiable y las evidencias claras.
3. Tests solo en las piezas críticas: `parse_money`, la regla del saldo, el OCR sobre capturas y el contrato de perfiles.

Usa los agentes de ECC cuando ahorren tiempo (`planner`, `code-reviewer`, `python-reviewer`,
`security-reviewer`, `e2e-runner`), no por sistema. Comandos útiles: `/plan`, `/code-review`, `/build-fix`.

## Reglas de validación
- La prueba principal es **lo visible**: OCR, plantillas o visión sobre el canvas. Un clic nunca es prueba.
- La red del proveedor y el monedero de Betsson solo **confirman**. Nunca sustituyen a la pantalla.
- Leer el DOM de Betsson (login, saldo, lobby) es legítimo. El juego no tiene DOM.
- Lo dudoso es **FAIL** con `reason: "inconclusive: …"`. Nunca un PASS optimista.
- Los ids de las comprobaciones están en `docs/PREPARACION.md` §3. Para añadir uno nuevo, PR al dueño del área C.

## Extensibilidad, multimercado y resistencia
- **Proveedores**:
  - Escenarios, comprobaciones e informe **no conocen ningún proveedor**: solo usan la interfaz `ProviderProfile`.
  - Lo específico de cada proveedor (detección, pantallas de inicio, zonas, plantillas, textos por idioma, patrón de red) vive en `betsson/profiles/<proveedor>/`. La palabra "pragmatic" no aparece fuera de ahí ni de `fixtures/pragmatic/`.
  - Añadir un proveedor = añadir una carpeta y pasar el test de contrato.
  - `generic-vision` es el perfil de respaldo para proveedores desconocidos.
- **Mercados**:
  - Un mercado nuevo = un archivo `config/markets/<mercado>.json`, validado con pydantic.
  - Nada de mercado, moneda, idioma ni formato numérico fijo en el código.
  - Los importes se leen siempre con `parse_money(texto, mercado)`.
- **Cambios del proveedor**:
  - Los importes se localizan por su **etiqueta visible** (OCR) y los botones por plantilla multiescala (OpenCV) o visión. Las zonas fijas son solo una pista.
  - Si el perfil no reconoce el juego, se recalibra. Si no se puede, el resultado es `PROVIDER_UI_CHANGED` (no concluyente, con aviso), **no** un FAIL de integración.

## Seguridad (innegociable)
- **Nunca credenciales ni secretos** en código, logs, capturas, vídeos, trazas, informe ni commits. En local van en `.env` (ya está en `.gitignore`) y en CI, en GitHub Secrets. Tampoco datos privados que nos den los organizadores.
- La traza de Playwright graba lo que se escribe: **se pausa durante el login** y los campos se tapan en capturas y vídeo.
- Apuesta **mínima** siempre. Solo cuentas de prueba de Betsson, nunca personales.
- Sin VPN salvo que la organización lo pida. No intentar saltarse captchas. Ritmo humano: al menos 2 s entre cargas.

## Áreas y propiedad (no tocar fuera de tu área sin PR)
- **A, web de Betsson y mercados (Maiki; también coordina `docs/`)**: `betsson/site/`, `betsson/market/`, `config/markets/`, `docs/`
- **B, ojos sobre el juego y proveedores (Alejandro)**: `betsson/game/`, `betsson/vision/`, `betsson/profiles/`, `fixtures/<proveedor>/`
- **C, escenarios e informe (Migue)**: `betsson/core/` (contratos, dueño único), `betsson/checks/`, `betsson/report/`, `tests/`
- **D, CI e infraestructura (Guilli)**: raíz, `.github/`, `requirements.txt`, `pytest.ini`, `setup-portatil.ps1`

Al arrancar la sesión, el usuario dirá su área. Lee `docs/PLAN_24H.md` §"Arranque en paralelo" y trabaja **solo en tus carpetas**.
Hasta las fusiones, las demás áreas se sustituyen por simulaciones (`Fake…`).

## Entorno
- Todo vive en el disco **D:**. No escribas fuera de D: salvo que sea imprescindible, y avisa si lo es.
- **Modo de un portátil**: las 4 sesiones corren en el portátil de Maiki, cada una en su worktree (`D:\MAIKI\Malackathonrea-<X>-<nombre>`, en su rama `feat/<X>-...`). **Trabaja solo en tu worktree**, no abras ni edites los de los demás. Venv compartido en `D:\MAIKI\Malackathon\.venv`. En otro portátil, el repo va en `D:\Malackaton` con su propio `.venv`.
- Python en el `.venv` indicado arriba (en Windows se activa con `Scripts\Activate.ps1`). Cachés en `D:\DevCache`, configuradas por `setup-portatil.ps1`.
- Las dependencias nuevas se piden a D (`requirements.txt`) y se añaden en los hitos.
- En una sesión en la nube la red está limitada: lo que tenga que entrar en Betsson se ejecuta en el portátil.

## Código
- Python 3.10+ con type hints. pytest + pytest-playwright, navegador visible, viewport 1366×768, DPR 1.
- OCR con RapidOCR, imagen con OpenCV, contratos y configuración con pydantic, informe con Jinja2.
- Zonas y controles del juego en **fracciones del canvas**, dentro del perfil de cada proveedor. Nunca píxeles absolutos.
- Nada de `time.sleep` ni `wait_for_timeout` fijos: esperar a señales (cambio visual, respuesta, texto).
- Resultados y evidencias en `outputs/runs/<runId>/<market>/<scenario>/` (`outputs/` no se sube a git).
- El OCR se prueba contra las capturas reales de `fixtures/<proveedor>/`.
- La CI se ejecuta en un runner propio en España: los runners de GitHub tienen IP de EE. UU. y Betsson geobloquea.

## Git
- Rama `feat/<área>-<tema>` desde `main` actualizado. PR pequeño, revisión rápida (de un compañero o del agente `code-reviewer`) y squash merge.
- Fusiones a `main` en los hitos: 13:00, 14:15, 15:30, 16:30, 17:30 y 18:30 (congelación).
- Mensajes en español, estilo Conventional Commits. Nunca `push --force` a `main` ni `--no-verify`.
