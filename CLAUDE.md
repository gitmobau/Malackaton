# Malackaton — instrucciones para Claude

Somos un equipo compitiendo en la **Malachathon** (hackathon de Málaga, ~24 h, entrega con demo y pitch).
El uso de IA está permitido por la organización. Responde siempre en **español**.

## Modo hackathon (tiene prioridad sobre las reglas genéricas de ECC)

ECC está copiado en `.claude/` (agentes, skills, comandos y reglas). Sus reglas piden TDD obligatorio y
80 % de cobertura: **aquí no aplican**. Prioridades, en este orden:

1. Algo que funcione de punta a punta lo antes posible (demo mínima en las primeras horas).
2. Que la demo sea fiable y vistosa para el jurado.
3. Calidad de código y tests solo en las piezas críticas (lo que, si falla, rompe la demo).

Usa los agentes de ECC cuando ahorren tiempo (`planner`, `code-reviewer`, `python-reviewer`,
`security-reviewer`, `e2e-runner`), no por sistema. Comandos útiles: `/plan`, `/code-review`, `/build-fix`.

## Retos (orden de preferencia)

1. **Betsson** — app que, en webs reales de Betsson, verifica que un juego nuevo aparece en el lobby,
   lo lanza, juega una partida y deja capturas + veredicto.
2. **Google** — SOC de emergencia: repositorio de datos + consola web para 30 días de telemetría
   sintética, reconstruir la intrusión y contener al atacante en vivo.
3. **Mercedes-Benz** — clustering de clientes y estrategias de marketing.

Reserva: NICS Lab (honeypots), NTT DATA (detector de alucinaciones con LLM local), Indra (incendio en
imágenes Sentinel-2). Texto completo en `docs/retos.md`. La investigación previa, cuando exista, está en
`docs/investigacion-malacaton.md`.

## Entorno

- Portátil **Windows**, todo vive en el disco **D:** (`D:\Malackaton`). No escribas fuera de D: salvo
  que sea imprescindible, y avisa si lo es.
- Python en el entorno virtual `D:\Malackaton\.venv` (actívalo con `.venv\Scripts\Activate.ps1`).
- Cachés en `D:\DevCache` (pip, npm, navegadores de Playwright, modelos de Ollama y Hugging Face),
  configuradas como variables de entorno por `setup-portatil.ps1`.
- Si una dependencia nueva hace falta, añádela a `requirements.txt`.
- Si trabajas en una sesión en la nube, la red está limitada: lo que necesite entrar en webs de Betsson
  o en la red del evento hay que ejecutarlo en el portátil.

## Convenciones

- Código de cada reto en su carpeta: `betsson/`, `google/`, `mercedes/` (crea solo la que toque).
- Resultados generados (capturas, informes, modelos) en `outputs/`, que no se sube a git.
- Nunca subas credenciales, tokens ni datos que nos den los organizadores si son privados.
- Commits pequeños y frecuentes en `main`; mensajes en español.
