from __future__ import annotations

from typing import Any, TypedDict


class SourceOnboardingState(TypedDict, total=False):
    run_id: str
    path: str
    project_id: str | None
    config_path: str | None
    export_target: str
    output: str | None
    dry_run: bool
    approved: bool
    require_approval: bool
    config_loaded: bool
    config_summary: dict[str, Any] | None
    path_policy: dict[str, Any] | None
    inspection: dict[str, Any] | None
    redaction_preview: dict[str, Any] | None
    coverage: dict[str, Any] | None
    rag_readiness: dict[str, Any] | None
    sync_plan: dict[str, Any] | None
    approval_request: dict[str, Any] | None
    sync_summary: dict[str, Any] | None
    post_sync_quality: dict[str, Any] | None
    final_report: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]
    status: str


class RAGReadinessState(TypedDict, total=False):
    run_id: str
    path: str
    config_path: str | None
    config_loaded: bool
    path_policy: dict[str, Any] | None
    inspection: dict[str, Any] | None
    coverage: dict[str, Any] | None
    rag_readiness: dict[str, Any] | None
    eval_seed_preview: list[dict[str, Any]]
    final_report: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]
    status: str


class SyncQualityState(TypedDict, total=False):
    run_id: str
    path: str
    project_id: str | None
    config_path: str | None
    config_loaded: bool
    path_policy: dict[str, Any] | None
    sync_summary: dict[str, Any] | None
    failed_uploads: dict[str, Any] | None
    coverage: dict[str, Any] | None
    rag_readiness: dict[str, Any] | None
    final_report: dict[str, Any] | None
    errors: list[str]
    warnings: list[str]
    status: str


class InvestigationBridgeState(TypedDict, total=False):
    run_id: str
    path: str | None
    project_id: str
    query: str
    config_path: str | None
    top_k: int | None
    debug: bool
    export_target: str
    dry_run: bool
    sync_approved: bool
    config_loaded: bool
    config_summary: dict[str, Any] | None
    core_health: dict[str, Any] | None
    core_capabilities: dict[str, Any] | None
    local_inspection: dict[str, Any] | None
    coverage: dict[str, Any] | None
    rag_readiness: dict[str, Any] | None
    sync_required: bool
    approval_request: dict[str, Any] | None
    sync_summary: dict[str, Any] | None
    core_investigation_result: dict[str, Any] | None
    core_run_result: dict[str, Any] | None
    final_report: dict[str, Any] | None
    missing_data: list[str]
    errors: list[str]
    warnings: list[str]
    status: str


GraphState = dict[str, Any]
