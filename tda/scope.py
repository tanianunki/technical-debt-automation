"""Guardrail 2: política de alcance.

Se evalúa en el host sobre lo que Git dice que cambió, nunca sobre lo que afirma el
agente. Decide la copia del host; la de la imagen es de solo lectura y no participa:
el evaluado no puede relajar a su evaluador.
"""

import os
import re
from pathlib import Path

PROTECTED = (".github/", "tests/test_api.py")  # CI y juez previo
NEW_TEST = re.compile(r"tests/test_[A-Za-z0-9_]+\.py")  # dónde va la prueba de regresión


def allowed_files(findings: list, tracked: set[str]) -> set[str]:
    """Procedencia: solo archivos ya versionados que nombra un hallazgo de esta ejecución."""
    return {finding.file for finding in findings} & tracked


def violations(
    changes: dict[str, str], allowed: set[str], tracked: set[str], work: Path
) -> list[str]:
    """Rutas cambiadas que no están autorizadas. `changes` es {ruta: estado de git status}."""
    bad = []
    for path, status in changes.items():
        file = work / path
        if path not in tracked and not os.path.lexists(file):
            continue  # archivo nuevo que el propio agente retiró en el reintento
        new_test = path not in tracked and NEW_TEST.fullmatch(path) and file.is_file()
        if (
            path.startswith(PROTECTED)  # primero: un hallazgo nunca desprotege
            or status == "!!"  # ignorado por Git: se validaría pero no llegaría al commit
            or file.is_symlink()
            or not (path in allowed or new_test)
        ):
            bad.append(path)
    return sorted(bad)
