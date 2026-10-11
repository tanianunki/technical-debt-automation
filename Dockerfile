# Imagen única para los dos perfiles de sandbox (ver tda/sandbox.py).
# No contiene git ni gh: desde aquí no se puede publicar.
FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt /opt/tda/
RUN pip install -r /opt/tda/requirements.txt
COPY tda /opt/tda/tda
# El código de la herramienta se importa desde aquí, no desde /repo.
WORKDIR /opt/tda
