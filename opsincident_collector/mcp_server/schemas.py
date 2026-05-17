from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class InspectFolderInput(BaseModel):
    path: str
    config_path: str | None = None
    max_depth: int | None = 8
    format: Literal["json"] = "json"


class ValidateSourceConfigInput(BaseModel):
    config_path: str


class PreviewRedactionInput(BaseModel):
    path: str
    config_path: str | None = None
    max_lines: int = 100


class SyncSourceInput(BaseModel):
    path: str
    project_id: str | None = None
    source_name: str | None = None
    config_path: str | None = None
    export_target: Literal["api", "jsonl", "sqlite", "console"] = "api"
    output: str | None = None
    dry_run: bool = False
    yes: bool = False
    approved: bool = False


class SourceCoverageInput(BaseModel):
    path: str | None = None
    project_id: str | None = None
    config_path: str | None = None


class RAGReadinessInput(BaseModel):
    path: str
    config_path: str | None = None


class SearchEvidenceInput(BaseModel):
    project_id: str
    query: str
    top_k: int = 10
    filters: dict[str, Any] | None = None
    debug: bool = False
    config_path: str | None = None


class InvestigateIncidentInput(BaseModel):
    project_id: str
    query: str
    top_k: int | None = None
    debug: bool = False
    config_path: str | None = None


class WorkflowRunInput(BaseModel):
    project_id: str
    query: str
    top_k: int | None = None
    approved: bool = False
    config_path: str | None = None


class RunLookupInput(BaseModel):
    run_id: str
    config_path: str | None = None


class ExportReportInput(BaseModel):
    run_id: str | None = None
    path: str | None = None
    format: Literal["markdown", "json"] = "markdown"
    output: str | None = None
    approved: bool = False
    config_path: str | None = None


class EvalSeedInput(BaseModel):
    path: str
    output: str | None = None
    approved: bool = False
    config_path: str | None = None


class ValidateCoreContractInput(BaseModel):
    api_url: str | None = None
    project_id: str | None = None
    with_sample: bool = False
    approved: bool = False
    config_path: str | None = None


class ToolResult(BaseModel):
    ok: bool
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
