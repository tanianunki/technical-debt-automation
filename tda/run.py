"""Flujo determinista de una ejecución. Corre en el host.

    [1] analizar → [2] corregir (agente) → [3] validar → [4] publicar o mostrar

Este archivo decide cuándo repetir y cuándo terminar; el agente solo corrige.
Uso: python -m tda.run <ruta local | owner/repo> [--publish]
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from tda import publish, sandbox, scope
from tda.report import Report

ATTEMPTS = 2  # sesiones del agente por ejecución
BOT = ["-c", "user.name=tda-bot", "-c", "user.email=tda-bot@users.noreply.github.com",
       "-c", "commit.gpgsign=false"]  # fmt: skip


def run(repo: str, do_publish: bool = False) -> Report:
    run_dir = Path("runs", time.strftime("%Y%m%d-%H%M%S")).resolve()
    work, git_dir, branch = run_dir / "work", run_dir / "git", f"debt/{run_dir.name}"
    report = Report(run_id=run_dir.name, repo=repo)

    # --- Ayudas; el flujo empieza en [1] ---

    def git(*args: str) -> str:
        # Rutas explícitas: Git nunca descubre el repositorio a partir del checkout,
        # así que nada de lo que el agente escriba allí se interpreta como configuración.
        cmd = ["git", f"--git-dir={git_dir}", f"--work-tree={work}", *args]
        return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout

    def changes() -> dict[str, str]:
        """{ruta: estado} de todo lo que difiere del commit inicial, incluido lo ignorado."""
        status = git("status", "--porcelain", "-z", "--untracked-files=all", "--ignored", "--no-renames")
        found = {entry[3:]: entry[:2] for entry in status.split("\0") if entry}
        if os.path.lexists(work / ".git"):  # git status nunca lista esta entrada
            found[".git"] = "??"
        return found

    def end(decision: str, reason: str) -> Report:
        report.decision, report.reason = decision, reason
        (run_dir / "report.json").write_text(report.model_dump_json(indent=2))
        show(report, run_dir)
        return report

    print("[1] Analizando dependencias")
    run_dir.mkdir(parents=True)
    source = repo if Path(repo).exists() else f"https://github.com/{repo}.git"
    clone = ["git", "clone", "--quiet", "--separate-git-dir", git_dir, source, work]
    if subprocess.run(clone).returncode != 0:
        sys.exit(f"No se pudo clonar {source}")
    (work / ".git").unlink()  # el puntero al repositorio no queda al alcance del agente
    git("checkout", "--quiet", "-b", branch)  # el trabajo ocurre en una rama, nunca en main
    report.base_sha = git("rev-parse", "HEAD").strip()

    base = sandbox.checks(work)
    report.findings, report.validation_commands = base.findings, base.commands
    report.coverage, report.gaps = base.coverage, base.gaps
    if base.errors:
        return end("inconclusive", "; ".join(base.errors))
    if not base.judge_passed or not base.judge_catches_break:
        return end("inconclusive", "el juez previo no pasa o no detecta una copia rota")
    if not base.tests_passed:  # sin línea base en verde no se puede exigir «un test más»
        return end("inconclusive", "los tests iniciales no pasan todos")
    if not base.findings:
        return end("no_change", "la auditoría no encontró hallazgos")
    # Se congelan ahora: el agente no puede ampliar su propio alcance.
    tracked = set(git("ls-files").splitlines())
    allowed = scope.allowed_files(base.findings, tracked)

    reason = ""
    for attempt in range(1, ATTEMPTS + 1):
        print(f"[2] Corrigiendo repositorio (intento {attempt} de {ATTEMPTS})")
        agent = sandbox.fix(work, base.findings, reason)
        report.agent_usage.append(agent.usage)

        # Lo que cambió se lee de Git, no de lo que afirma el agente.
        changed = changes()
        report.changed_files = sorted(path for path in changed if os.path.lexists(work / path))
        report.tests_added = [path for path in report.changed_files if path not in tracked]
        outside = scope.violations(changed, allowed, tracked, work)
        if outside:
            return end("blocked", "cambios fuera del alcance: " + ", ".join(outside))
        if agent.result is None:
            reason = f"la sesión anterior no terminó: {agent.error}"
            continue
        report.fix_summary = agent.result.summary[:500]
        if agent.result.outcome == "no_safe_fix":
            decision = "failed" if changed else "no_change"
            return end(decision, "el agente no encontró una corrección segura")
        git("add", "--all")
        diff = git("diff", "--cached")
        keys = [os.environ[key] for key in sandbox.MODEL_KEYS if os.environ.get(key)]
        if any(key in diff for key in keys):
            return end("blocked", "la clave del modelo aparece en el diff")

        print("[3] Validando cambio")
        after = sandbox.checks(work)
        if after.errors:
            return end("inconclusive", "; ".join(after.errors))
        problems = []
        if after.findings:
            remaining = "; ".join(f"{f.id} ({f.detail})" for f in after.findings)
            problems.append("siguen presentes: " + remaining)
        if after.judge_passed != base.judge_passed:
            problems.append("el juez previo ya no pasa completo")
        if after.tests_passed <= base.tests_passed:
            problems.append("falta una prueba nueva en tests/test_<nombre>.py que pase con las demás")
        if not problems:
            git(*BOT, "commit", "--quiet", "-m", publish.TITLE)
            report.head_sha = git("rev-parse", "HEAD").strip()
            report.review = (
                f"determinista: alcance respetado; juez {after.judge_passed}/{base.judge_passed}; "
                f"{after.tests_passed} tests; sin hallazgos de pip-audit ni deprecaciones"
            )
            break
        reason = "; ".join(problems) + "\n" + after.log[-1500:]

    if not report.head_sha:
        return end("failed", f"sin validar tras {ATTEMPTS} intentos: {reason[:300]}")
    report.decision = "verified"  # publish.py lo exige antes de empujar nada
    if not do_publish:
        print("[4] Resultado local")
        return end("verified", "validado localmente; no se publicó (demo local)")
    print("[4] Creando PR")
    try:
        report.pr_url, note = publish.publish(report, git_dir, branch)
    except subprocess.CalledProcessError as error:
        # La evidencia de la validación sigue en `review` y `head_sha`; la decisión dice que no hay PR.
        return end("failed", f"validado, pero no se pudo publicar: {error.stderr.strip()[:300]}")
    return end("verified", note)


def show(report: Report, run_dir: Path) -> None:
    usage = [u for u in report.agent_usage if u]
    sessions = f"{len(usage)} sesión(es), {sum(u['num_turns'] for u in usage)} turnos" if usage else "-"
    lines = [
        "Problema:   " + ("; ".join(f"{f.id} en {f.file}" for f in report.findings) or "ninguno"),
        "Corrección: " + (report.fix_summary or "ninguna"),
        "Prueba:     " + (", ".join(report.tests_added) or "ninguna"),
        "Resultado:  " + (report.review or "sin validar"),
        "Agente:     " + sessions,
        f"Decisión:   {report.decision} — {report.reason}",
        f"PR:         {report.pr_url or '-'}",
        f"Reporte:    {run_dir / 'report.json'}",
    ]
    for line in lines:  # el texto viene del repo y del modelo: sin caracteres de control
        print("  " + "".join(char for char in line if char.isprintable()))


if __name__ == "__main__":
    target = next(arg for arg in sys.argv[1:] if arg != "--publish")
    to_github = "--publish" in sys.argv
    if not any(os.environ.get(key) for key in sandbox.MODEL_KEYS):
        sys.exit("Falta la clave del modelo: define ANTHROPIC_API_KEY o CLAUDE_CODE_OAUTH_TOKEN.")
    if to_github and not publish.SLUG.fullmatch(target):
        sys.exit("Para publicar, el repositorio debe indicarse como owner/repo (TDA_REPO=owner/repo).")
    final = run(target, to_github)
    sys.exit(0 if final.decision in ("verified", "no_change") else 1)
