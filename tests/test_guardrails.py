"""Escenarios de aceptación de los guardrails. No usan el modelo.

Los que ejecutan contenedores necesitan Docker y la imagen `tda-sandbox` (`make test`).
"""

from pathlib import Path

import pytest

from tda import publish, run, sandbox, scope
from tda.report import AgentResult, AgentRun, Checks, Finding, Report

NEWS_API = Path(__file__).parent.parent.parent / "news-api"
FINDING = Finding(id="PYSEC-0000-1", kind="vulnerable", file="requirements.txt", detail="x")
PROBE = """
touch /repo/probe 2>/dev/null && echo WROTE_REPO
touch /opt/tda/probe 2>/dev/null && echo WROTE_IMAGE
command -v git gh
env
"""


@pytest.mark.parametrize("decision", ["no_change", "blocked", "inconclusive", "failed"])
def test_only_verified_publishes(decision, monkeypatch):
    """Guardrail 1: el publicador rechaza cualquier decisión distinta de `verified`."""
    monkeypatch.setattr(publish, "sh", lambda *cmd: pytest.fail("no debe ejecutar git ni gh"))
    report = Report(run_id="t", repo="owner/repo", head_sha="abc", decision=decision)
    with pytest.raises(PermissionError):
        publish.publish(report, Path("git"), "debt/t")


@pytest.mark.parametrize(
    ("path", "status", "is_violation"),
    [
        ("requirements.txt", " M", False),  # lo nombra un hallazgo
        ("tests/test_regression.py", "??", False),  # prueba de regresión nueva
        ("app/main.py", " M", True),  # ningún hallazgo lo nombra
        ("tests/test_api.py", " M", True),  # juez previo
        (".github/workflows/ci.yml", " M", True),  # CI
        ("tests/conftest.py", "??", True),  # podría alterar al juez
        ("tests/test_x/conftest.py", "??", True),
        ("tests/test_ignored.py", "!!", True),  # no llegaría al commit
        (".git", "??", True),
    ],
)
def test_scope_rules(path, status, is_violation, tmp_path):
    """Guardrail 2: solo archivos de los hallazgos y tests nuevos; protegidos, nunca."""
    (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / path).write_text("x")
    tracked = {"requirements.txt", "app/main.py", "tests/test_api.py", ".github/workflows/ci.yml"}
    allowed = scope.allowed_files([FINDING], tracked)
    assert bool(scope.violations({path: status}, allowed, tracked, tmp_path)) is is_violation


def test_finding_cannot_unprotect_or_symlink(tmp_path):
    """Ni un hallazgo falso desprotege al juez, ni un symlink sustituye a un archivo permitido."""
    tracked = {"tests/test_api.py", "requirements.txt"}
    on_judge = FINDING.model_copy(update={"file": "tests/test_api.py"})
    allowed = scope.allowed_files([on_judge], tracked)
    assert scope.violations({"tests/test_api.py": " M"}, allowed, tracked, tmp_path)
    (tmp_path / "requirements.txt").symlink_to("/etc/hostname")
    assert scope.violations({"requirements.txt": " T"}, {"requirements.txt"}, tracked, tmp_path)


@pytest.mark.parametrize("target", [".github/workflows/ci.yml", ".git"])
def test_out_of_scope_change_blocks(target, tmp_path, monkeypatch):
    """Un agente que toca un archivo protegido termina en `blocked`, sin commit ni PR."""

    def rogue_agent(work, findings, reason):
        (work / target).write_text("contenido del agente\n")
        return AgentRun(result=AgentResult(outcome="fixed", summary="todo en orden"))

    healthy = Checks(findings=[FINDING], judge_passed=4, judge_catches_break=True, tests_passed=4)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sandbox, "checks", lambda work: healthy)
    monkeypatch.setattr(sandbox, "fix", rogue_agent)
    monkeypatch.setattr(publish, "sh", lambda *cmd: pytest.fail("no debe publicar"))

    report = run.run(str(NEWS_API), do_publish=True)
    assert report.decision == "blocked" and target in report.reason
    assert report.head_sha == "" and report.pr_url == ""


def test_inconclusive_validation_never_commits(tmp_path, monkeypatch):
    """Una validación que no pudo completarse no es un éxito."""
    results = iter([
        Checks(findings=[FINDING], judge_passed=4, judge_catches_break=True, tests_passed=4),
        Checks(errors=["pip-audit no produjo un resultado legible"]),
    ])  # fmt: skip

    def agent(work, findings, reason):
        (work / "requirements.txt").write_text("orjson==3.11.6\n")
        return AgentRun(result=AgentResult(outcome="fixed", summary="ok"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sandbox, "checks", lambda work: next(results))
    monkeypatch.setattr(sandbox, "fix", agent)
    monkeypatch.setattr(publish, "sh", lambda *cmd: pytest.fail("no debe publicar"))

    report = run.run(str(NEWS_API), do_publish=True)
    assert report.decision == "inconclusive" and report.head_sha == ""


def test_sandbox_profiles(tmp_path, monkeypatch):
    """Aislamiento del SO: qué puede escribir y qué secretos ve cada contenedor."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-del-modelo")
    monkeypatch.setenv("GH_TOKEN", "token-de-github")

    checks = sandbox.docker_run(f"{tmp_path}:/repo:ro", ["sh", "-c", PROBE])
    assert "HOME=/tmp" in checks  # el contenedor sí se ejecutó
    assert "WROTE" not in checks and "clave-del-modelo" not in checks and "token-de-github" not in checks

    agent = sandbox.docker_run(f"{tmp_path}:/repo:rw", ["sh", "-c", PROBE], sandbox.MODEL_ENV)
    assert "WROTE_REPO" in agent and "clave-del-modelo" in agent
    assert "WROTE_IMAGE" not in agent and "token-de-github" not in agent
    assert "/git" not in agent and "/gh" not in agent  # no hay con qué publicar


def test_seeded_findings_and_judge():
    """El estado inicial de news-api: ambos detectores encuentran algo y el juez funciona."""
    result = sandbox.checks(NEWS_API)
    assert {finding.kind for finding in result.findings} == {"vulnerable", "deprecated"}
    assert result.judge_passed == result.tests_passed > 0 and result.judge_catches_break
    assert not result.errors
