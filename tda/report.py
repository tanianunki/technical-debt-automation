"""Contratos de datos: lo único que cruza entre el host, los contenedores y el modelo."""

from typing import Literal

from pydantic import BaseModel, Field


class Finding(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_.:-]+$")
    kind: Literal["vulnerable", "deprecated"]
    file: str  # único archivo existente que este hallazgo autoriza a modificar
    detail: str  # texto del escáner o del warning: dato no confiable


class Checks(BaseModel):
    """Salida del contenedor de checks. Los valores por defecto significan «no comprobado»."""

    findings: list[Finding] = []
    judge_passed: int = 0
    judge_catches_break: bool = False
    tests_passed: int = 0  # 0 también si algún test falla
    errors: list[str] = []
    commands: list[str] = []
    coverage: list[str] = []  # qué se analizó realmente
    gaps: list[str] = []  # qué no cubre esta auditoría
    log: str = ""


class AgentResult(BaseModel):
    """Lo que el modelo debe devolver. Los archivos modificados se leen de Git, no de aquí."""

    outcome: Literal["fixed", "no_safe_fix"]
    summary: str


class AgentRun(BaseModel):
    """Salida del contenedor del agente."""

    result: AgentResult | None = None
    error: str = ""
    usage: dict = {}


class Report(BaseModel):
    run_id: str
    repo: str
    base_sha: str = ""
    head_sha: str = ""
    findings: list[Finding] = []
    coverage: list[str] = []
    gaps: list[str] = []
    changed_files: list[str] = []
    tests_added: list[str] = []
    validation_commands: list[str] = []
    fix_summary: str = ""
    review: str = ""
    agent_usage: list[dict] = []
    pr_url: str = ""
    decision: Literal["verified", "no_change", "blocked", "inconclusive", "failed"] = "failed"
    reason: str = ""
