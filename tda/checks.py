"""Auditoría y validación deterministas.

Corre dentro del contenedor de checks: sin secretos y con /repo de solo lectura.
Se ejecuta antes de corregir (para encontrar hallazgos) y después (para validar).
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from tda.report import Checks, Finding

REPO = "/repo"
PY = "/tmp/venv/bin/python"  # dependencias del repo, separadas de pip-audit (imagen)

# Lo único que esta herramienta sabe del repositorio analizado.
JUDGE = "tests/test_api.py"
MODULE, MODULE_FILE = "app.main", "app/main.py"
MUTATION = ("data/news.json", "[]")  # alteración deliberada que el juez debe detectar

# Los mismos comandos que ejecuta .github/workflows/ci.yml en el repositorio.
INSTALL = [PY, "-m", "pip", "install", "-q", "-r", "requirements.txt", "-r", "requirements-dev.txt"]
RUN_JUDGE = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", JUDGE]
RUN_TESTS = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
AUDIT = ["pip-audit", "-r", "requirements.txt", "-f", "json", "--progress-spinner", "off"]
DEPRECATIONS = [PY, "-W", f"error::DeprecationWarning:{MODULE}", "-c", f"import {MODULE}"]

COVERAGE = [
    "requirements.txt con dependencias transitivas (pip-audit)",
    f"DeprecationWarning al importar {MODULE}",
]
GAPS = [
    "requirements-dev.txt no se audita",
    "deprecaciones que solo se emiten al atender peticiones",
    "paquetes abandonados sin advisory ni warning",
]


def sh(cmd: list[str], cwd: str = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def passed(pytest_run: subprocess.CompletedProcess) -> int:
    """Tests que pasaron; 0 si alguno falló. Contar evita aceptar una ejecución vacía."""
    count = re.search(r"(\d+) passed", pytest_run.stdout)
    return int(count.group(1)) if pytest_run.returncode == 0 and count else 0


def main() -> Checks:
    commands = [" ".join(c) for c in (INSTALL, RUN_JUDGE, RUN_TESTS, AUDIT, DEPRECATIONS)]
    out = Checks(commands=commands, coverage=COVERAGE, gaps=GAPS)

    sh([sys.executable, "-m", "venv", "/tmp/venv"])
    install = sh(INSTALL)
    if install.returncode != 0:
        out.errors.append("no se pudieron instalar las dependencias")
        out.log = install.stderr[-2000:]
        return out

    # 1. Juez previo, en su propia invocación: un test nuevo no puede alterar su veredicto.
    out.judge_passed = passed(sh(RUN_JUDGE))

    # 2. ¿El juez detecta un comportamiento roto? Se prueba en una copia desechable.
    shutil.copytree(REPO, "/tmp/broken", symlinks=True, ignore=shutil.ignore_patterns(".venv"))
    Path("/tmp/broken", MUTATION[0]).write_text(MUTATION[1])
    out.judge_catches_break = sh(RUN_JUDGE, cwd="/tmp/broken").returncode != 0

    # 3. Todos los tests, incluida la prueba de regresión nueva.
    tests = sh(RUN_TESTS)
    out.tests_passed = passed(tests)
    if not out.tests_passed:
        out.log += tests.stdout[-1500:]

    vulnerable(sh(AUDIT), out)
    deprecated(sh(DEPRECATIONS), out)
    return out


def vulnerable(audit: subprocess.CompletedProcess, out: Checks) -> None:
    """4. Dependencias vulnerables: base de advisories por paquete y versión."""
    try:
        for dep in json.loads(audit.stdout)["dependencies"]:
            # pip-audit puede repetir un advisory con distintas versiones corregidas: se unen.
            fixes: dict[str, set[str]] = {}
            for vuln in dep["vulns"]:  # una dependencia omitida no trae esta clave
                fixes.setdefault(vuln["id"], set()).update(vuln["fix_versions"])
            for vuln_id, versions in fixes.items():
                fixed = ", ".join(sorted(versions)) or "ninguna"
                detail = f"{dep['name']} {dep['version']}; versiones corregidas: {fixed}"
                finding = Finding(id=vuln_id, kind="vulnerable", file="requirements.txt", detail=detail)
                out.findings.append(finding)
        if audit.returncode != (1 if out.findings else 0):  # 0 = limpio, 1 = con hallazgos
            raise ValueError
    except (ValueError, KeyError):  # «sin hallazgos» solo vale si la auditoría fue completa
        out.errors.append("pip-audit no produjo un resultado completo")
        out.log += audit.stderr[-500:]


def deprecated(imported: subprocess.CompletedProcess, out: Checks) -> None:
    """5. APIs deprecadas: las declara el propio código al ejecutarse; un escáner no las ve."""
    if "DeprecationWarning" in imported.stderr:
        warning = imported.stderr[imported.stderr.rfind("DeprecationWarning") :]
        detail = " ".join(warning.split())[:400]
        finding = Finding(id=f"DEPRECATED:{MODULE}", kind="deprecated", file=MODULE_FILE, detail=detail)
        out.findings.append(finding)
    elif imported.returncode != 0:  # falló por otra causa: no se sabe si hay deprecaciones
        out.errors.append(f"no se pudo importar {MODULE} para buscar deprecaciones")
        out.log += imported.stderr[-500:]


if __name__ == "__main__":
    print(main().model_dump_json())
