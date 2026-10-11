# Arquitectura

Un agente con herramientas dentro de un flujo determinista. Las decisiones y sus razones
están en [PLAN.md](../../PLAN.md); la evidencia, en [research.md](research.md).

```
HOST  run.py ──────────────────────────────────────────────────────────────────────┐
  │ clona → rama debt/RUN        (git siempre con --git-dir y --work-tree explícitos) │
  │                                                                                  │
  ├─▶ CONTENEDOR B · checks.py     /repo solo lectura · sin secretos · ejecuta código │
  │      hallazgos, juez previo, copia rota                                          │
  ├─▶ CONTENEDOR A · agent.py      /repo escritura · clave del modelo · sin shell     │
  │      Claude edita archivos y devuelve AgentResult                                │
  ├─▶ scope.py                     ¿lo cambiado está autorizado por los hallazgos?    │
  ├─▶ CONTENEDOR B · checks.py     misma validación sobre el resultado               │
  │      commit → head_sha → report.json                                             │
  └─▶ publish.py (solo `verified`) push de head_sha a una rama + PR con gh ───────────┘
                                          │
GITHUB  Actions `verify` (required) ──▶ auto-merge ──▶ main
```

**¿Por qué un agente?** Solo «entender cómo se usa la dependencia y reescribir el código»
necesita razonamiento ([PLAN §3](../../PLAN.md#3-agentes-y-componentes-deterministas)).
Detectar es consultar un escáner y ejecutar un comando; validar es repetirlos; publicar es
`git push` y `gh`. Quien modifica no revisa su propio cambio: lo revisan `scope.py`,
`checks.py` y, de forma independiente, CI. No hay agente revisor porque su «APPROVE» no
podría autorizar nada ([PLAN §9](../../PLAN.md#9-validación-pr-ci-y-fallos)).

**Estados terminales:** `verified`, `no_change`, `blocked`, `inconclusive`, `failed`
([PLAN §4](../../PLAN.md#4-patrón-de-ejecución)). Permisos y límites reconocidos:
[PLAN §7](../../PLAN.md#7-herramientas-permisos-y-guardrails).

## Comparación con las referencias

**[financial-services](https://github.com/anthropics/financial-services)** separa lector
de contenido no confiable, orquestador y un único escritor, con entregas JSON validadas y
publicación externa. Aquí hay un solo escritor (el agente), sin lector aparte: el agente
lee contenido no confiable pero no tiene herramientas con efectos fuera del checkout, y
quien ejecuta ese contenido (contenedor B) no tiene secretos. Las entregas son `Finding`,
`Checks` y `AgentResult`, validadas con Pydantic. Publica `publish.py`, fuera del agente.

**[commerce-agents](https://github.com/anthropics/commerce-agents)** aplica las reglas en
el ejecutor de herramientas y condiciona las escrituras a ids devueltos en la sesión.
Aquí la regla vive en código (`scope.py`), no en el prompt, y la procedencia son los
hallazgos congelados al inicio de la ejecución. La rama es el cambio «staged»; la
aprobación externa es el check requerido; `blocked` es un resultado explícito. Diferencia:
la regla se evalúa sobre el diff acumulado, no en cada invocación de herramienta.

**[code-migration-kit](https://github.com/anthropics/code-migration-kit-with-claude-code)**
exige un juez definido antes de cambiar código, probado contra una copia rota, que el
evaluado no puede relajar. Aquí `tests/test_api.py` existe desde el commit inicial, cada
ejecución comprueba que falla ante una mutación, corre en una invocación propia y debe
pasar el mismo número de tests antes y después. `no_change` es un cierre válido.

**[codex-security](https://github.com/openai/codex-security)** separa escanear, validar,
parchear y verificar, y no trata un resultado parcial como éxito. Aquí: `checks` (scan) →
agente (patch) → `checks` con el checkout de solo lectura (verify); cobertura y huecos se
reportan aparte de los hallazgos; `inconclusive` nunca publica. No se valida cada hallazgo
por separado ni se abre el PR como borrador: lo retiene el check requerido.
