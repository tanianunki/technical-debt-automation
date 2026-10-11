PY := .venv/bin/python
# Credenciales locales opcionales (archivo ignorado por Git); ver .env.example.
-include .env
export
# Ruta local para demo-local; owner/repo para demo-github.
TDA_REPO ?= ../news-api

.PHONY: image demo-local demo-github test clean

.venv: requirements.txt
	python3 -m venv .venv && $(PY) -m pip install -q -r requirements.txt

image:
	docker build -q -t tda-sandbox .

demo-local: .venv image   ## analiza, corrige y valida; no publica
	$(PY) -m tda.run $(TDA_REPO)

demo-github: .venv image  ## igual, y abre el PR (requiere gh autenticado o GH_TOKEN)
	$(PY) -m tda.run $(TDA_REPO) --publish

test: .venv image         ## guardrails y sandbox, sin modelo
	$(PY) -m pytest -q tests

clean:
	rm -rf runs
