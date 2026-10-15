# Coordinación: montar el equipo en un portátil

Todo el equipo trabaja en **un solo portátil**: una sesión de Claude coordinadora y una por área, cada una en su worktree de git. Cada persona se conecta a su sesión con Remote Control.
Esta carpeta sirve para recrear esa estructura en otro portátil. El 15-oct se migró del portátil de Maiki al de Alejandro.

| Archivo | Para qué |
|---|---|
| `CLAUDE.md` | Se copia a la raíz (`D:\MAIKI\Malackathon\CLAUDE.md`). Indica a cada sesión su papel según la carpeta en la que se abre |
| `montar-portatil.ps1` | Crea `equipo\` (clon), los 4 worktrees (`area-*`), el `.venv` compartido, Chromium y el plugin ECC con hooks `standard` |
| `exportar-conversaciones.ps1` | En el portátil **viejo**: empaqueta las conversaciones de Claude en un zip |
| `importar-conversaciones.ps1` | En el portátil **nuevo**: deja las conversaciones donde Claude las busca, para retomarlas con `claude --resume` |

## Pasos para migrar

**En el portátil viejo**
1. Cada área deja su trabajo en un punto salvable, escribe `handoff/<X>.md` y hace push de su rama (`feat/A-betsson-web`, `feat/B-vision`, `feat/C-core`, `feat/D-infra`).
2. Cuando las 4 hayan terminado, cierra las sesiones y ejecuta:
   `powershell -ExecutionPolicy Bypass -File D:\MAIKI\Malackathon\equipo\coordinacion\exportar-conversaciones.ps1 -Destino D:\traspaso-conversaciones.zip`
3. Lleva al portátil nuevo el zip y los `.env` que haya **por USB o por un canal privado, nunca por git**.

**En el portátil nuevo** (hacen falta Git, Node, Python y Claude Code; si falta algo, ejecuta antes `setup-portatil.ps1` del repo)
1. Clona el repo y monta la estructura:
   ```powershell
   git clone https://github.com/gitmobau/Malackaton.git D:\MAIKI\Malackathon\equipo
   powershell -ExecutionPolicy Bypass -File D:\MAIKI\Malackathon\equipo\coordinacion\montar-portatil.ps1
   ```
2. Copia los `.env` en las carpetas `area-*` que los usen.
3. Retoma las conversaciones (opcional, pero recomendado):
   `powershell -ExecutionPolicy Bypass -File D:\MAIKI\Malackathon\equipo\coordinacion\importar-conversaciones.ps1 -Zip <ruta>\traspaso-conversaciones.zip`
4. Abre una terminal por sesión y conecta cada una por Remote Control:
   ```powershell
   cd D:\MAIKI\Malackathon               # coordinador
   cd D:\MAIKI\Malackathon\area-A-maiki  # y lo mismo con B, C y D
   claude --resume                       # elige la conversación; si no hay zip, usa "claude" y la frase de retomar
   /remote-control
   ```
   Frase para retomar sin la conversación: *"Soy el área X. Lee CLAUDE.md, docs/PLAN_24H.md y handoff/X-nombre.md, y continúa desde donde quedó."*
5. Área D: registra el runner de GitHub Actions en el portátil nuevo (`run.cmd` en una terminal, no como servicio).
