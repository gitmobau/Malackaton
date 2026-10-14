# Malackaton

Repositorio del equipo para la **Malachathon** (Málaga). Retos y orden de preferencia en
[`docs/retos.md`](docs/retos.md). Instrucciones para Claude en [`CLAUDE.md`](CLAUDE.md).

## Qué hay aquí

| Ruta | Qué es |
| --- | --- |
| `CLAUDE.md` | Contexto del hackathon y reglas de trabajo para Claude Code |
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

5. **Comprueba que ECC está cargado** preguntándole a Claude: *"¿Qué skills y agentes de ECC tienes?"*.
   Los comandos van sin prefijo: `/plan`, `/code-review`, `/build-fix`.

### Dónde queda cada cosa

| Carpeta | Contenido |
| --- | --- |
| `D:\Malackaton` | Este repo y el entorno virtual de Python (`.venv`) |
| `D:\ClaudeCode` | Configuración, historial y plugins de Claude Code (`CLAUDE_CONFIG_DIR`) |
| `D:\DevTools` | Claude Code (`npm-global`) y, si el instalador lo permite, Git, Python, Node.js y Ollama |
| `D:\DevCache` | Cachés de pip y npm, navegadores de Playwright, modelos de Ollama y Hugging Face |

Si algún programa no admite instalarse en D:, el script lo instala en su carpeta por defecto y lo
avisa al final.

## Sesiones en la nube

ECC funciona también en claude.ai/code porque está dentro de `.claude/`. La red de esas sesiones está
limitada: lo que tenga que entrar en webs de Betsson o en la red del evento hay que ejecutarlo en el
portátil.
