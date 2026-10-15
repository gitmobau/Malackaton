# Malackaton

Repositorio del equipo para la **Malachathon** (Málaga). Retos y orden de preferencia en
[`docs/retos.md`](docs/retos.md). Instrucciones para Claude en [`CLAUDE.md`](CLAUDE.md).

## Qué hay aquí

| Ruta | Qué es |
| --- | --- |
| `CLAUDE.md` | Contexto del hackathon y reglas de trabajo para Claude Code |
| `docs/PREPARACION.md` | **Reto Betsson**: requisitos, arquitectura, incógnitas, decisiones y riesgos (documento vivo) |
| `docs/PLAN_24H.md` | Áreas del equipo, arranque en paralelo, bloques horarios e hitos |
| `docs/PREGUNTAS.md` | Preguntas abiertas a mentores, organización y equipo |
| `docs/recon/` | Capturas de la exploración de la web pública de Betsson |
| `docs/retos.md` | Texto oficial de los 6 retos y nuestro orden |
| `.claude/` | [ECC](https://github.com/affaan-m/ECC) copiado dentro del proyecto: agentes, skills, comandos y reglas. Funciona igual en local y en sesiones en la nube |
| `setup-portatil.ps1` | Deja el portátil listo con todo en el disco D: |
| `requirements.txt` | Dependencias de Python comunes a los retos |

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
- **Tests `unit`** (sin red): en los runners de GitHub, en cada PR y en cada push a `main`.
- **Job `real`** (entra en Betsson): **solo a mano**, en Actions → *Validación de juegos* → *Run workflow*, indicando los mercados (por defecto `es`; `com` y `pe` están configurados pero desactivados por falta de cuenta). Se ejecuta en el runner propio del portátil de Alejandro, porque los runners de GitHub tienen IP de EE. UU. y Betsson los geobloquea.
- El job real usa **Chrome del sistema** (`--browser-channel chrome`): con él no salió captcha en el reconocimiento.
- El runner `portatil-alejandro` (`D:\DevTools\actions-runner`) lleva las etiquetas `self-hosted, windows, betsson-es` y **se arranca con `run.cmd` en una terminal, no como servicio**. Un servicio no tiene escritorio y el navegador visible (`--headed`) falla; el workflow lo comprueba.
- **Tras un reinicio o si se cierra su ventana, el runner se cae.** Para volver a arrancarlo:
  `start "runner" /min cmd /c "D:\DevTools\actions-runner\run.cmd"`.
  Para que arranque solo al iniciar sesión, el dueño del portátil puede añadir esa línea al final de `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\unidad-D.cmd`, después del `subst`, que crea la unidad D:. Claude no lo hace porque es una persistencia fuera del repo.
- **Lanzar la validación (demo)**, con `gh` y la sesión iniciada:
  ```bash
  gh workflow run "Validación de juegos" -R gitmobau/Malackaton --ref main -f markets=es
  gh run watch -R gitmobau/Malackaton "$(gh run list -R gitmobau/Malackaton -w 'Validación de juegos' -L 1 --json databaseId -q '.[0].databaseId')"
  gh run download -R gitmobau/Malackaton -n "evidencias-es-<runId>-<intento>" -D outputs/ci   # el nombre aparece en el resumen del run
  ```
  Abre Chrome en el portátil del runner y gasta saldo: avisar al equipo antes.
- Secretos en *Settings → Secrets → Actions*: `BETSSON_<MERCADO>_USERNAME` y `BETSSON_<MERCADO>_PASSWORD` (y `..._EMPTY_...` para el escenario 2). Mismos nombres que en `.env.example`.
- Antes de publicar el artifact, `.github/scripts/scan_secrets.py` busca las credenciales en `outputs/`. Si encuentra alguna, no se publica nada. Las trazas y los vídeos quedan fuera del artifact hasta que el login esté tapado.
- **Informe web**: tras una ejecución a mano, el job `pages` genera `index.html` con el resumen PASS/FAIL y los enlaces a `report.html` y `results.json` de cada mercado (`.github/scripts/build_pages.py`). Solo usa evidencias que ya pasaron el escáner de secretos y nunca publica trazas ni vídeos. Siempre se sube como artifact `informe-web-<runId>-<intento>`.
- **GitHub Pages**: el plan de la cuenta no lo permite en un repo privado (HTTP 422). Si el repo pasa a público o la cuenta a Pro: *Settings → Pages → Source: GitHub Actions* y variable del repo `PAGES_ENABLED=true`. Ojo: la web de Pages es pública.
- **Probar el despliegue sin gastar saldo**: `gh workflow run "Validación de juegos" -R gitmobau/Malackaton -f markets=` (ningún mercado activo: no abre Chrome).
- `.github/CODEOWNERS`: el equipo usa una única cuenta compartida (`gitmobau`), así que todo es suyo. El reparto por áreas queda documentado en comentarios.

## Sesiones en la nube

ECC funciona también en claude.ai/code porque está dentro de `.claude/`. La red de esas sesiones está
limitada: lo que tenga que entrar en webs de Betsson o en la red del evento hay que ejecutarlo en el
portátil.
