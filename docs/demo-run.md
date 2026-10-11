# Guion técnico de la demo

No es el libreto narrado: son los comandos, lo que debe verse y lo que no hace.

## Comandos

```sh
# 1. El paciente: tests verdes, dependencias enfermas
cd news-api && python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt pip-audit==2.10.1
python -m pytest -q                                                   # 4 passed
pip-audit -r requirements.txt                                         # orjson 3.9.14: 2 advisories
python -W error::DeprecationWarning:app.main -c "import app.main"     # on_event is deprecated

# 2. La automatización
cd ../technical-debt-automation
cp .env.example .env                         # y escribe la clave del modelo (o expórtala)
make test                                    # guardrails, sin modelo
make demo-local                              # recorrido sin publicar
make demo-github TDA_REPO=OWNER/news-api     # abre el PR (docs/github-setup.md)
```

## Archivos para mostrar (cinco)

1. `tda/run.py`: el flujo, los límites y los estados.
2. `tda/checks.py`: dos detectores distintos, el juez y la copia rota.
3. `tda/agent.py`: el prompt y las cinco herramientas.
4. `tda/scope.py`: qué puede cambiar.
5. `tda/publish.py`: quién publica y por qué nunca en `main`.

`news-api/app/main.py` se enseña como diff del PR; `tda/sandbox.py`, con la tabla de su
cabecera.

## Salida esperada de `make demo-local`

```
[1] Analizando dependencias
[2] Corrigiendo repositorio (intento 1 de 2)
[3] Validando cambio
[4] Resultado local
  Problema:   PYSEC-2024-40 en requirements.txt; PYSEC-2026-107 en requirements.txt; DEPRECATED:app.main en app/main.py
  Corrección: Fijado orjson==3.11.6 en requirements.txt y sustituido @app.on_event("startup") por un handler lifespan en app/main.py [...]
  Prueba:     tests/test_regression.py
  Resultado:  determinista: alcance respetado; juez 4/4; 7 tests; sin hallazgos de pip-audit ni deprecaciones
  Agente:     1 sesión(es), 11 turnos
  Decisión:   verified — validado localmente; no se publicó (demo local)
  PR:         -
  Reporte:    .../runs/20261011-000807/report.json
```

Es la salida de una ejecución real del 2026-10-11 con `claude-sonnet-5-5` (alrededor de un
minuto). **En esa ejecución el agente corrió en el host**, con la sesión local de Claude
Code, porque no había clave del modelo para el contenedor; los checks sí corrieron en
Docker. Con la clave en `.env`, `make demo-local` ejecuta el mismo código con el agente
dentro del contenedor: ese camino solo se comprobó hasta la autenticación. El texto de
«Corrección» y el nombre del test los elige el modelo y varían. Para ver el diff:
`git --git-dir=runs/<id>/git show`. `make demo-github` no se ha ejecutado contra GitHub.

## Qué usa Claude y qué es determinista

| Paso | Quién |
|---|---|
| Encontrar la vulnerabilidad y la deprecación | determinista: `pip-audit` y un `DeprecationWarning` |
| Comprobar que el juez funciona | determinista: pytest contra una copia rota |
| Entender el uso, cambiar versión y código, escribir la prueba de regresión | **Claude** (Agent SDK, solo herramientas de archivos) |
| Decidir si el cambio está dentro del alcance | determinista: `scope.py` sobre `git status` |
| Validar la corrección | determinista: los mismos comandos, checkout de solo lectura |
| Commit, push, PR | determinista: `run.py` y `publish.py` |
| Revalidar e integrar | GitHub Actions y auto-merge |

## Limitaciones

- Solo deuda de dependencias, un repositorio, dos casos sembrados.
- La auditoría depende de bases públicas: un advisory nuevo sobre cualquier dependencia
  cambiará los hallazgos (y puede dejar `main` en rojo después del merge).
- Solo se detectan deprecaciones emitidas al importar `app.main`.
- El contenedor reduce el daño, no lo elimina: red sin restricción de destino y kernel
  compartido. El agente puede leer su propia clave del modelo.
- La validación comprueba efectos (tests, escáner, warning), no intención: silenciar el
  warning pasaría el detector. Nadie revisa el diff salvo que se exija revisión humana.
- `checks.py` conoce tres datos de `news-api` (juez, módulo y mutación); no es genérico.
- El resultado del modelo no es reproducible bit a bit.
