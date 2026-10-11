"""Los dos perfiles de contenedor. Comparten el endurecimiento y difieren en tres cosas:

            checkout    secretos            ejecuta código del repo
  checks    solo lectura  ninguno             sí (pip install, pytest)
  agente    escritura     clave del modelo    no (no tiene shell)
"""

import json
import os
import subprocess
import uuid
from pathlib import Path

from pydantic import ValidationError

from tda.report import AgentRun, Checks, Finding

IMAGE = "tda-sandbox"
TIMEOUT = 600  # segundos por contenedor, aplicado desde el host
MODEL_KEYS = ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")  # basta una
MODEL_ENV = (*MODEL_KEYS, "TDA_MODEL")
HARDENING = [
    "--rm", "--interactive",
    "--user", f"{os.getuid()}:{os.getgid()}",  # sin root
    "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
    "--read-only", "--tmpfs", "/tmp:exec",  # único lugar escribible además del montaje
    "--memory", "2g", "--cpus", "2", "--pids-limit", "256",
    "--env", "HOME=/tmp",
]  # fmt: skip


def docker_run(mount: str, command: list[str], env: tuple[str, ...] = (), stdin: str = "") -> str:
    name = f"tda-{uuid.uuid4().hex[:12]}"
    # `--env=NOMBRE` copia la variable del host; su valor no aparece en la línea de comandos.
    passed = [f"--env={var}" for var in env if os.environ.get(var)]
    cmd = ["docker", "run", f"--name={name}", *HARDENING, *passed, f"--volume={mount}", IMAGE, *command]
    try:
        return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=TIMEOUT).stdout
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return ""


def checks(work: Path) -> Checks:
    try:
        return Checks.model_validate_json(docker_run(f"{work}:/repo:ro", ["python", "-m", "tda.checks"]))
    except ValidationError:
        return Checks(errors=["el contenedor de checks no devolvió un resultado válido"])


def fix(work: Path, findings: list[Finding], reason: str) -> AgentRun:
    payload = json.dumps({"findings": [f.model_dump() for f in findings], "reason": reason})
    try:
        output = docker_run(f"{work}:/repo:rw", ["python", "-m", "tda.agent"], MODEL_ENV, payload)
        return AgentRun.model_validate_json(output)
    except ValidationError:
        return AgentRun(error="el contenedor del agente no devolvió un resultado válido")
