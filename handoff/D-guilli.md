# Traspaso del área D (Guilli: CI e infraestructura)

Estado a 15-oct, al migrar al portátil de Alejandro. Rama `feat/D-infra`.

## Hecho y probado
- **PR #1 fusionado en `main`** (8aad168):
  - Esqueleto: `betsson/` con una carpeta por área (solo `__init__.py`) y `config/markets/`.
  - Configuración de pytest: `pytest.ini` y `conftest.py`.
  - Archivos de repo: `.env.example` (sin valores), `.gitattributes` (eol=lf), plantilla de PR y `CODEOWNERS` (usuarios pendientes).
  - `requirements.txt` ampliado.
  - Workflow `.github/workflows/validacion.yml` y `.github/scripts/scan_secrets.py`.
- **`conftest.py`**:
  - Chromium a 1366×768 con DPR 1.
  - Opción `--market` (o `MARKET`, por defecto `es`).
  - Fixtures `market_id`, `run_id` y `evidence_dir` → `outputs/runs/<runId>/<market>/<test>/`.
  - Carga solo el `.env` del repo y nunca en CI.
  - Fija `PLAYWRIGHT_BROWSERS_PATH` a `D:\DevCache\ms-playwright` si existe esa carpeta.
- **Marcas**: `unit` (sin red) y `real` (entra en Betsson).
- **`scan_secrets.py`**:
  - Busca las credenciales en `outputs/`, tal cual y en forma URL, JSON y base64.
  - Falla cerrado: sale con 2 si faltan credenciales y con 1 si encuentra una fuga.
  - Probado con valores falsos.
- **Revisión de seguridad** (agente `security-reviewer`): los hallazgos críticos y altos están corregidos.
  - El job real nunca se ejecuta con PR.
  - Los secretos solo existen en los pasos que los usan.
  - El artifact solo se publica si el escáner sale en verde.
  - Trazas (`.zip`) y vídeos (`.webm`) quedan fuera del artifact.
- **`pytest -m unit`**: 10 pasan en el `.venv` (Python 3.14).

## En qué punto quedó
- **PR #2 abierto, sin fusionar y fusionable**: https://github.com/gitmobau/Malackaton/pull/2
  1. El job `real` solo se lanza con `workflow_dispatch`. Antes se lanzaba en cada push a `main`, y el coordinador tuvo que cancelar el run 38721371898.
  2. Paso que falla si el runner corre como servicio (sesión 0), porque `--headed` necesita escritorio.
  3. README con una sección CI.
  4. `testpaths = tests betsson`, para recoger los tests de A en `betsson/market/tests/`.
  5. `--browser-channel chrome` en el job real (Chrome del sistema: con él no salió captcha, según A).
  6. Commit de docs `9b46f7b`.
  - **OJO, ya no es correcto con la migración**: el README y los docs dicen "runner en el portátil de Maiki". Hay que cambiarlo a "portátil de Alejandro" en el README (área D) y en los docs (coordinador).
- **Runner**: **NO registrado** en ningún sitio.
  - En el portátil de Maiki solo se descargó (`D:\DevTools\actions-runner`, v2.338.0) y no se llegó a ejecutar `config.cmd`.
  - Se puede borrar esa carpeta. No hay nada que quitar en GitHub.
- **`gh` portable** en el portátil de Maiki: `D:\DevTools\gh\bin\gh.exe`, con sesión de la cuenta `gitmobau`, que es admin del repo.
  - Para cerrar esa sesión en el portátil de Maiki: `gh auth logout`.

## Actualización (ya en el portátil de Alejandro)
- PR #2 fusionado en `main` (67a0846). El README ya dice "portátil de Alejandro".
- El venv compartido funciona aquí: `pytest -m unit` da 10 tests en verde. `gh` está en `C:\Program Files\GitHub CLI`, con la cuenta `gitmobau`.
- **Runner registrado y online**:
  - Nombre `portatil-alejandro`, en `D:\DevTools\actions-runner` (v2.338.0).
  - Etiquetas `self-hosted, Windows, X64, betsson-es`.
  - Arrancado con `run.cmd` en una ventana minimizada, no como servicio.
  - Si se cierra esa ventana o se reinicia el portátil, el runner se cae. Para volver a arrancarlo: `D:\DevTools\actions-runner\run.cmd`.
- Pasos 1 y 2 hechos. Sigue el 3.

## Siguientes pasos (en orden)
1. ~~Corregir en el README "portátil de Maiki" → "portátil de Alejandro" y fusionar el PR #2.~~ Hecho.
2. ~~Registrar el runner en el portátil de Alejandro.~~ Hecho.
3. Crear los secretos en GitHub (ver abajo) cuando lleguen las cuentas.
4. Lanzar a mano *Actions → Validación de juegos → Run workflow* (mercados: `es`) y comprobar que el artifact `evidencias-es-*` se publica.
5. Rellenar `.github/CODEOWNERS` con los usuarios de GitHub de los cuatro (pedírselos al equipo).
6. Pedir la cuenta de Oracle: encuesta del correo, con un correo `@uma.es` (Guilli). Es un seguro, no una dependencia.
7. Más adelante: publicar `report.html` en GitHub Pages, cuando el escáner y el tapado del login estén garantizados. Volver a meter trazas y vídeos en el artifact solo entonces. A ya pausa la traza en el login (`betsson/site/tracing.py`, `ChunkedTrace`) y tapa los campos con blur.

## Registrar el runner en el portátil nuevo
```powershell
# 1) Descargar (o copiar) el runner en D:\DevTools\actions-runner
#    https://github.com/actions/runner/releases (actions-runner-win-x64-<ver>.zip)
# 2) Token de registro (caduca en 1 h), con gh y permisos de admin:
gh api -X POST repos/gitmobau/Malackaton/actions/runners/registration-token --jq .token
# 3) Configurar SIN servicio, con la etiqueta que usa el workflow:
cd D:\DevTools\actions-runner
.\config.cmd --url https://github.com/gitmobau/Malackaton --token <TOKEN> --name portatil-alejandro --labels betsson-es --unattended
# 4) Arrancarlo en una terminal (NO como servicio: --headed necesita escritorio). Dejar la terminal abierta:
.\run.cmd
```
- Las etiquetas `self-hosted` y `windows` las pone solo. Hay que añadir `betsson-es`.
- El workflow usa por defecto `VENV_PY = D:\MAIKI\Malackathon\.venv\Scripts\python.exe`. Si en el portátil nuevo cambia la ruta, crea una variable del repo (*Settings → Variables → Actions*) `VENV_PY` con la ruta nueva.
- El workflow usa `PLAYWRIGHT_BROWSERS_PATH = D:\DevCache\ms-playwright` y Chrome del sistema (`--browser-channel chrome`): Chrome tiene que estar instalado.
- Para quitar un runner: `.\config.cmd remove --token <TOKEN>`. El token sale de `gh api -X POST repos/gitmobau/Malackaton/actions/runners/remove-token --jq .token`.

## Secretos de GitHub (solo los nombres)
En *Settings → Secrets and variables → Actions*:
- `BETSSON_ES_USERNAME`
- `BETSSON_ES_PASSWORD`
- `BETSSON_ES_EMPTY_USERNAME` (cuenta sin saldo para el escenario 2, si la hay)
- `BETSSON_ES_EMPTY_PASSWORD`
- Futuros: los mismos con `COM` y `PE`; opcional `ANTHROPIC_API_KEY`.

Para crearlos sin que el valor salga en pantalla: `gh secret set BETSSON_ES_PASSWORD -R gitmobau/Malackaton` (lo pide de forma interactiva).

## Recrear el .venv
- **Python 3.14** (el del portátil). No hizo falta 3.12.
- **Hay que evitar `rapidocr-onnxruntime`**: exige Python < 3.13 y pip se queda atascado probando versiones. En su lugar: `rapidocr>=3` + `onnxruntime`, ya cambiado en `requirements.txt`.
- Usé **uv** porque es mucho más rápido, pero pip también vale:
```powershell
$env:UV_CACHE_DIR='D:\DevCache\uv'; $env:PLAYWRIGHT_BROWSERS_PATH='D:\DevCache\ms-playwright'
uv venv D:\MAIKI\Malackathon\.venv --python 3.14 --seed
uv pip install --python D:\MAIKI\Malackathon\.venv\Scripts\python.exe -r requirements.txt
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m playwright install chromium
D:\MAIKI\Malackathon\.venv\Scripts\python.exe -m pytest -m unit
```
- Sin `--only-binary`: con él, el resolvedor se atascó más de 10 min por paquetes de datos sin rueda (`kmodes`). Para ir rápido se puede instalar primero lo crítico: `playwright pytest pytest-playwright opencv-python "rapidocr>=3" onnxruntime imagehash pydantic jinja2 pillow numpy python-dotenv anthropic`.
- La descarga de Chromium falló una vez por `ECONNRESET`; al reintentarla, funcionó.
- Variables de usuario que conviene fijar: `PLAYWRIGHT_BROWSERS_PATH`, `PIP_CACHE_DIR` y `UV_CACHE_DIR`, todas en `D:\DevCache\...` (`setup-portatil.ps1` lo hace).
- Versiones verificadas: opencv 5.0.0, onnxruntime 1.31.0, pydantic 2.14.1, pytest 9.1.1, playwright 1.64.0, anthropic 1.14.0, Chromium 156.
- **No hacer `pip install` en paralelo** desde varias sesiones en el venv compartido: las dependencias se piden al área D.
