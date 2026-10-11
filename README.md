# technical-debt-automation

Demo del video *Automatización de deuda técnica con agentes de IA*: un agente de Claude
corrige **deuda de dependencias** en [`news-api`](../news-api) y un flujo determinista decide
si el cambio puede convertirse en un pull request.

La deuda de dependencias (librerías vulnerables, deprecadas u obsoletas) es una categoría
de deuda técnica; este ejemplo no intenta detectar deuda de arquitectura, tests,
documentación ni infraestructura. Es material educativo, no código de producción.

```
detectar → analizar uso → corregir → validar → PR → CI → main
 checks        agente (Claude)     checks   publish  GitHub
```

## Ejecutar

Requisitos: Docker, Python 3.10+, `make`, y una clave del modelo en `.env` o en el entorno.

```sh
cp .env.example .env                # escribe ANTHROPIC_API_KEY o CLAUDE_CODE_OAUTH_TOKEN (claude setup-token)
make test                           # guardrails y sandbox; no usa el modelo
make demo-local                     # analiza, corrige y valida ../news-api; no publica
make demo-github TDA_REPO=owner/news-api   # además abre el PR (ver docs/github-setup.md)
```

Cada ejecución clona el repositorio en `runs/<id>/work`, trabaja en la rama `debt/<id>` y
deja la evidencia en `runs/<id>/report.json`. La decisión es una de `verified`,
`no_change`, `blocked`, `inconclusive` o `failed`; solo `verified` puede publicarse.

## Dónde mirar

| Pregunta | Archivo |
|---|---|
| ¿Cuál es el flujo y quién decide repetir o terminar? | [`tda/run.py`](tda/run.py) |
| ¿Cómo se ejecuta la auditoría y cómo se valida la corrección? | [`tda/checks.py`](tda/checks.py) |
| ¿Dónde está el prompt y qué herramientas tiene el agente? | [`tda/agent.py`](tda/agent.py) |
| ¿Qué archivos puede cambiar? | [`tda/scope.py`](tda/scope.py) |
| ¿Cómo se crea el PR y por qué no se escribe en main? | [`tda/publish.py`](tda/publish.py) |
| ¿Qué aísla cada contenedor? | [`tda/sandbox.py`](tda/sandbox.py) |
| ¿Qué datos cruzan entre componentes? | [`tda/report.py`](tda/report.py) |

Qué usa Claude: solo el paso «corregir». Todo lo demás es Python, Git, Docker y GitHub
Actions.

## Documentación

- [docs/architecture.md](docs/architecture.md): el diseño en una página y su comparación con las referencias.
- [docs/demo-run.md](docs/demo-run.md): comandos, salida esperada y limitaciones.
- [docs/github-setup.md](docs/github-setup.md): repositorios remotos, protección de `main` y auto-merge.
- [docs/production-evolution.md](docs/production-evolution.md): qué faltaría para producción.
- [docs/research.md](docs/research.md): fuentes y comprobaciones.
- [`../PLAN.md`](../PLAN.md): fuente de verdad del diseño (vive junto a los dos repositorios).
