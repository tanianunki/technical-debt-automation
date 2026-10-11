"""Guardrail 1: el único lugar con `git push` y `gh`.

Corre en el host, fuera del proceso agéntico. Usa la sesión de `gh` o GH_TOKEN del
entorno; nunca recibe un token como argumento. Título y cuerpo los genera el host.
"""

import os
import re
import subprocess
from pathlib import Path

from tda.report import Report

TITLE = "Corrige deuda de dependencias (automatizado)"
REQUIRED_CHECK = "verify"
SLUG = re.compile(r"[\w-][\w.-]*/[\w-][\w.-]*")  # owner/repo; nunca una ruta


def sh(*cmd: str) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # sin credencial, fallar en vez de preguntar
    return subprocess.run(cmd, check=True, capture_output=True, text=True, env=env).stdout.strip()


def publish(report: Report, git_dir: Path, branch: str) -> tuple[str, str]:
    """Abre el PR del commit validado. Devuelve (URL, nota sobre el auto-merge)."""
    if report.decision != "verified":
        raise PermissionError(f"decisión {report.decision!r}: solo `verified` puede publicarse")
    slug = report.repo
    if not SLUG.fullmatch(slug):
        raise ValueError("el repositorio debe tener la forma owner/repo para publicar")

    # Se empuja exactamente el commit validado, a una rama: nunca a main.
    # La credencial la entrega `gh` (sesión o GH_TOKEN) al hacer push: se descartan otros
    # helpers del sistema, y el token no se guarda ni viaja en la URL.
    use_gh = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
    sh("git", f"--git-dir={git_dir}", *use_gh, "push", "--quiet",
       f"https://github.com/{slug}.git", f"{report.head_sha}:refs/heads/{branch}")  # fmt: skip
    body = "\n".join([
        f"Commit validado: `{report.head_sha}`", "",
        "Hallazgos corregidos: " + ", ".join(f.id for f in report.findings),
        "Archivos: " + ", ".join(report.changed_files),
        "Revisión local: " + report.review, "",
        "El check `verify` vuelve a validar este commit antes de integrarlo.",
    ])  # fmt: skip
    url = sh("gh", "pr", "create", "--repo", slug, "--base", "main", "--head", branch,
             "--title", TITLE, "--body", body)  # fmt: skip

    # El merge lo hace GitHub. Sin un check requerido, `--auto` integraría de inmediato:
    # por eso se comprueba antes de pedirlo.
    try:
        required = sh("gh", "api", f"repos/{slug}/branches/main",
                      "--jq", ".protection.required_status_checks.contexts[]")  # fmt: skip
    except subprocess.CalledProcessError:
        required = ""
    if REQUIRED_CHECK not in required.split():
        return url, f"sin auto-merge: `{REQUIRED_CHECK}` no es un check requerido en main"
    try:
        sh("gh", "pr", "merge", url, "--auto", "--squash")
    except subprocess.CalledProcessError as error:
        return url, f"sin auto-merge: {error.stderr.strip()[:200]}"
    return url, f"auto-merge solicitado: GitHub integrará cuando pase `{REQUIRED_CHECK}`"
