# Portátil del equipo · Malackathon 2026 (reto Betsson)

Responde siempre en **español**. Este archivo (copia de `equipo/coordinacion/CLAUDE.md`, colocada en la raíz por `montar-portatil.ps1`) lo cargan **todas** las sesiones de Claude de este portátil. Desde el 15-oct todo corre en el **portátil de Alejandro** (más RAM y CPU), con la misma ruta raíz `D:\MAIKI\Malackathon`.
Antes de nada, mira en qué carpeta se abrió tu sesión:

| Carpeta de la sesión | Papel | Qué seguir |
|---|---|---|
| `D:\MAIKI\Malackathon` o `...\equipo` | **Coordinador** | La sección "Coordinador" de abajo, más `equipo\CLAUDE.md` |
| `...\area-A-maiki` | Área A, Maiki (web de Betsson y mercados) | **Solo** el `CLAUDE.md` de tu worktree. Ignora la sección "Coordinador" |
| `...\area-B-alejandro` | Área B, Alejandro (ojos sobre el juego y proveedores) | Ídem |
| `...\area-C-migue` | Área C, Migue (escenarios e informe) | Ídem |
| `...\area-D-guilli` | Área D, Guilli (CI e infraestructura) | Ídem |

Regla para todas las sesiones: **trabaja solo dentro de tu carpeta**. No leas para editar ni modifiques los worktrees de otras áreas, ni `equipo\`, si no eres el coordinador.

## Estructura del portátil
- `equipo\`: clon principal de `gitmobau/Malackaton` (rama `main` o `docs/...`). Lo usa el coordinador para los documentos y para revisar PR.
- `area-A-maiki\`, `area-B-alejandro\`, `area-C-migue\`, `area-D-guilli\`: **worktrees** del mismo repo, uno por área, cada uno en su rama (`feat/A-betsson-web`, `feat/B-vision`, `feat/C-core`, `feat/D-infra`).
- `.venv\`: entorno de Python **compartido** por todos los worktrees (lo crea el área D con `requirements.txt`).
- Cada miembro se conecta a la sesión de su área con **Remote Control** (cuenta compartida del equipo).

## Coordinador (solo la sesión abierta en `D:\MAIKI\Malackathon` o en `equipo\`)
- Documentos vivos, que solo existen en el repo: `equipo\docs\PREPARACION.md`, `PLAN_24H.md` y `PREGUNTAS.md`.
- Con cada "Nueva info: …": actualizar esos documentos, decir qué cambia en el plan y qué decisiones se cierran, y subirlo en la rama `docs/...`.
- Seguir a las áreas: `git -C equipo fetch --all`, revisar ramas y PR antes de cada hito (13:00, 14:15, 15:30, 16:30, 17:30, 18:30) y vigilar las reglas que más puntúan: ver como un jugador, extensibilidad a otros proveedores, multimercado, resistencia a cambios del proveedor y nada de secretos.
- Si hay que volver a migrar: cada área escribe `handoff/<X>.md` y sube su rama; en el portátil nuevo se ejecuta `equipo/coordinacion/montar-portatil.ps1` (ver `coordinacion/README.md`).
- Vigilar los recursos del portátil: límite de uso compartido, navegadores de A y B, ejecuciones de CI. Si hay atasco, proponer pasar un área a un segundo portátil.
- Herramientas: ECC 2.2.3 a nivel de usuario (hooks `standard`); agentes `planner`, `architect`, `code-reviewer`, `e2e-runner`; skills `parallel-execution-optimizer` y `e2e-testing`; MCP `chrome-devtools` (solo páginas públicas de Betsson).
- No hacer push a `main` ni crear issues o PR sin que el equipo lo pida.
