# Investigación

Consultado el 2026-10-10. «Publicado» es lo que afirma la fuente; «inferencia» es nuestra
lectura. No se copió código de ninguna referencia. Las licencias marcadas *n/v* no se
verificaron porque solo se extrajeron ideas.

## Comprobaciones propias (entorno temporal, Python 3.12)

| Hecho | Evidencia |
|-------|-----------|
| `orjson==3.9.14` es vulnerable | `pip-audit 2.10.1 -r requirements.txt` → PYSEC-2024-40 (CVE-2024-27454, corrige 3.9.15) y PYSEC-2026-107 (CVE-2025-67221, corrige 3.11.6) |
| `@app.on_event` está deprecado en `fastapi==0.143.0` | `python -W error::DeprecationWarning -c "import app.main"` falla con «on_event is deprecated, use lifespan event handlers instead»; el warning apunta a `app/main.py` |
| El filtro por módulo también funciona | `python -W error::DeprecationWarning:app.main -c "import app.main"` sale con 1 antes de corregir y con 0 después; es el comando de CI |
| pip-audit no ve la deprecación | El mismo reporte no menciona FastAPI: son dos detectores distintos |
| `claude-agent-sdk==0.2.165` (PyPI, 2026-10-08) incluye el CLI | wheels `manylinux` aarch64/x86_64; README: «automatically bundled» |
| `tools=[...]` limita las herramientas existentes | Sonda real: el mensaje `init` lista solo `Edit, Glob, Grep, Read, Write, StructuredOutput`; el modelo reporta Bash «unavailable» |
| Un `Write` preaprobado no queda confinado al `cwd` | Sonda real: escribió un archivo en una ruta absoluta fuera del directorio de trabajo; el límite de rutas debe ponerlo el SO |
| Con login de claude.ai aparecen conectores MCP de la cuenta | Sonda real: el modelo listó tools `mcp__claude_ai_*`; con `disallowed_tools=["mcp__*"]` el modelo los reporta como no disponibles (ejecución en el host) |
| `output_format` devuelve `structured_output` validado | Misma sonda: `ResultMessage.subtype == "success"`, 3 turnos, `total_cost_usd` presente (estimación del cliente) |

## Spotify (Honk)

| Fuente | Publicado | Adoptado | Descartado |
|--------|-----------|----------|------------|
| [Parte 1](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1) | El agente sustituye scripts de migración; elegir repos, abrir PR, revisar y fusionar siguen siendo infraestructura determinista | Agente solo en el paso «corregir» | Fleet Management, MCP, trazas MLflow |
| [Parte 2](https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2) | Pocas herramientas; git sin push; describir el estado final y cuándo no actuar; un cambio por prompt | Prompt de estado final con salida «no hay corrección segura»; sin Bash ni búsqueda web | Allowlist de comandos Bash |
| [Parte 3](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3) | Verificadores deterministas antes del PR; si fallan no hay PR; un juez LLM veta ~25 % (sobre todo por salirse del alcance); contenedor con pocos binarios | Validación determinista como puerta; el alcance se comprueba con una regla, no con un LLM | Juez LLM |
| [Parte 4](https://engineering.atspotify.com/2026/4/background-coding-agents-dataset-migrations-honk-part-4) | Sin tests el agente no puede autoverificarse | Juez previo obligatorio en verde antes de corregir | Orquestación de flota |
| [Code with Claude](https://engineering.atspotify.com/2026/6/code-with-claude-coding-is-no-longer-the-constraint), [Fleetshift](https://backstage.spotify.com/fleetshift) | Honk usa Claude con el Agent SDK; la mayoría de PR de mantenimiento se auto-fusionan; la revisión es el cuello de botella | Auto-merge de GitHub tras el check requerido | Kubernetes, panel de seguimiento |

Inferencia: su predictibilidad viene de reducir lo que el agente puede hacer, no de un prompt más largo.

## Anthropic

| Fuente | Principio | Adoptado | Descartado |
|--------|-----------|----------|------------|
| [claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python), [referencia](https://code.claude.com/docs/en/agent-sdk/python) | `query()` ejecuta el bucle agéntico | `query()` + `ClaudeAgentOptions`; ningún bucle manual | `ClaudeSDKClient`, MCP, subagentes |
| [Permisos](https://code.claude.com/docs/en/agent-sdk/permissions) | `allowed_tools` solo preaprueba, no limita; `dontAsk` niega lo que pediría permiso; un `Write` preaprobado no queda confinado al `cwd` | `tools` + `allowed_tools` + `dontAsk` + `setting_sources=[]`; el confinamiento de rutas lo da el montaje Docker | Hooks `PreToolUse`, `can_use_tool` |
| [Structured outputs](https://code.claude.com/docs/en/agent-sdk/structured-outputs) | Esquema JSON desde Pydantic; `success` sin `structured_output` es fallo | `AgentResult` Pydantic, un reintento | — |
| [Secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment) | Contenedor: `--cap-drop ALL`, `no-new-privileges`, `--read-only`, tmpfs, usuario sin root, límites; «setup dependent»; credenciales por proxy | Esos flags de `docker run` | Proxy de credenciales, `--network none`, gVisor (documentados) |
| [claude-code-action](https://github.com/anthropics/claude-code-action/blob/main/docs/solutions.md) | Claude dentro de Actions con permisos por workflow; sus ejemplos reportan dependencias, no las corrigen | Nada: el agente corre fuera de CI y CI solo valida | Dar a CI la clave del modelo |
| [financial-services](https://github.com/anthropics/financial-services/blob/main/managed-agent-cookbooks/market-researcher/README.md) (*n/v*) | Tres niveles: lector de no confiables sin escritura, orquestador, un único escritor; JSON con esquema y longitud limitada; destinos en allowlist ([orchestrate.py](https://github.com/anthropics/financial-services/blob/main/scripts/orchestrate.py)) | Un único escritor; entregas con esquema y texto truncado; el publicador es externo | Managed Agents, tres subagentes, conectores |
| [commerce-agents](https://github.com/anthropics/commerce-agents/blob/main/docs/safety.md) (*n/v*) | Reglas en el ejecutor, no en el prompt; writes solo sobre ids devueltos en la sesión; cambios staged; aprobación del host; resultado `blocked` | Regla de alcance en código derivada de los hallazgos de la ejecución; rama como «staged»; estado `blocked` | Tres runtimes, MCP, memoria, UI |
| [code-migration-kit](https://github.com/anthropics/code-migration-kit-with-claude-code/blob/main/prompts/00b-judge-setup.md) (*n/v*) | Juez antes de cambiar; debe fallar ante mutaciones; «the graded party does not relax its own grader»; negar por configuración | Juez previo protegido y probado contra copia rota en cada ejecución; cierre `no_change` | Seis fases, fan-out, revisores dobles |
| [tech-debt skill](https://github.com/anthropics/knowledge-work-plugins/blob/main/engineering/skills/tech-debt/SKILL.md) | Taxonomía: code, architecture, test, **dependency**, documentation, infrastructure | Nombre de la categoría | Fórmula `(Impact+Risk)×(6−Effort)`: con dos hallazgos no aporta |

## OpenAI (solo comparación)

| Fuente | Principio | Adoptado | Descartado |
|--------|-----------|----------|------------|
| [codex-security](https://github.com/openai/codex-security/blob/main/README.md) (*n/v*) | Validar hallazgos, parchear y verificar son pasos separados; un escaneo parcial no es un éxito | Verificación independiente con checkout de solo lectura; cobertura y huecos separados de los hallazgos; `inconclusive` no publica | SARIF, threat model, deduplicación |
| [codex-action security](https://github.com/openai/codex-action/blob/main/docs/security.md) | Archivos de instrucciones del repo, títulos y cuerpos de PR son entrada no confiable; el agente puede dejar `.git/hooks` | `setting_sources=[]`; el agente no ve `.git`; CI con `contents: read` y `persist-credentials: false` | Bubblewrap, `drop-sudo` |
| [Agents SDK guardrails](https://github.com/openai/openai-agents-python/blob/main/docs/guardrails.md) | Validar cada invocación con efectos, no solo entrada y salida | Ningún tool con efectos externos; el efecto acumulado (diff) se valida antes de publicar | Guardrail por invocación (evolución: hook `PreToolUse`) |

## Otras implementaciones

| Fuente | Idea | Decisión |
|--------|------|----------|
| [Dependabot + agentes](https://github.blog/changelog/2026-04-07-dependabot-alerts-are-now-assignable-to-ai-agents-for-remediation/) | Analiza advisory y uso, abre PR borrador; exige revisar | Mismo recorrido; es la alternativa gestionada |
| [gh-aw](https://github.com/github/gh-aw) (MIT) | Agente de solo lectura; otro job aplica las escrituras validadas | Mismo patrón con `publish.py` |
| [OSV-Scanner](https://github.com/google/osv-scanner) | OSV.dev; también marca paquetes deprecados vía deps.dev | Evolución; pip-audit basta y se instala con pip |
| [Renovate](https://github.com/renovatebot/renovate) (AGPL-3.0) | Sube versiones; no adapta código | No se usa; cubre la mitad determinista |
| [TestGen-LLM](https://arxiv.org/abs/2402.09171) | Un test generado se acepta solo si compila y pasa | El test nuevo debe pasar en la validación; cobertura y mutación quedan fuera |

No consultadas a fondo: copilot-modernization, emend, upgrade-dependencies-agent y el
artículo de Meta sobre mutation testing; no cambian ninguna decisión del demo.

## Conclusión

La forma oficial más pequeña es una llamada a `query()` del Claude Agent SDK con cinco
herramientas de archivos, rodeada por Python, Git, Docker y GitHub Actions deterministas.
