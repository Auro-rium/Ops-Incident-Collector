from __future__ import annotations

from pathlib import Path
from typing import Any

from opsincident_collector.adapters.core_contract_validator import validate_core_contract
from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.analysis import (
    build_rag_readiness_report,
    build_source_coverage_report,
)
from opsincident_collector.mcp_server.tools import get_source_coverage
from opsincident_collector.state.sqlite_store import SQLiteStore


def get_resource_map(config_path: Path | None = None) -> dict[str, object]:
    settings = load_settings_optional(config_path)
    return {
        "incidentops://local/config": get_local_config(config_path),
        "incidentops://local/last-inspection": get_last_inspection(config_path),
        "incidentops://local/last-sync": get_last_sync(config_path),
        "incidentops://local/rag-readiness": get_local_rag_readiness(config_path),
        "incidentops://local/failed-uploads": get_failed_uploads(config_path),
        "incidentops://project/{project_id}/sources": {
            "description": "Core project source registry, fetched by project id.",
        },
        "incidentops://project/{project_id}/coverage": {
            "description": "Core source list or local coverage fallback for a project.",
        },
        "incidentops://project/{project_id}/core-capabilities": {
            "description": "Core capability and NormalizedDocument ingest compatibility report.",
            "api_url_configured": bool(settings.api.base_url),
        },
    }


def get_local_config(config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    return _redacted_config(settings)


def get_last_inspection(config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        checkpoint = store.get_source_checkpoint("default")
    finally:
        store.close()
    if not checkpoint:
        return {"ok": False, "message": "No local inspection checkpoint is available."}
    return {"ok": True, "last_inspection": checkpoint}


def get_last_sync(config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        last_sync = store.get_last_sync_summary()
    finally:
        store.close()
    if not last_sync:
        return {"ok": False, "message": "No sync runs recorded in local SQLite state."}
    return {"ok": True, "last_sync": _safe_sync_summary(last_sync)}


def get_local_rag_readiness(config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    path = _first_existing_source_path(settings)
    if not path:
        return {"ok": False, "message": "No existing configured source path is available."}
    report = build_rag_readiness_report(path, settings)
    return {"ok": True, "path": str(path), "rag_readiness": report.model_dump(mode="json")}


def get_failed_uploads(config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        rows = store.list_failed_uploads()
        depth = store.failed_upload_queue_depth()
    finally:
        store.close()
    safe_rows = [
        {
            "id": row.get("id"),
            "sync_id": row.get("sync_id"),
            "source_name": row.get("source_name"),
            "path": row.get("path"),
            "document_external_id": row.get("document_external_id"),
            "reason": row.get("reason"),
            "retry_count": row.get("retry_count"),
            "next_retry_at": row.get("next_retry_at"),
            "last_error": row.get("last_error"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]
    return {"ok": True, "queue_depth": depth, "failed_uploads": safe_rows}


def get_project_sources(project_id: str, config_path: Path | None = None) -> dict[str, Any]:
    return get_source_coverage(
        project_id=project_id,
        config_path=str(config_path) if config_path else None,
    )


def get_project_coverage(project_id: str, config_path: Path | None = None) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    path = _first_existing_source_path(settings)
    if path:
        coverage = build_source_coverage_report(path, settings)
        return {
            "ok": True,
            "project_id": project_id,
            "local_path": str(path),
            "coverage": coverage.model_dump(mode="json"),
        }
    return get_source_coverage(
        project_id=project_id,
        config_path=str(config_path) if config_path else None,
    )


def get_project_core_capabilities(
    project_id: str,
    config_path: Path | None = None,
) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    if not settings.api.base_url:
        return {"ok": False, "error": "IncidentOps Core API is not configured"}
    report = validate_core_contract(
        api_url=settings.api.base_url,
        project_id=project_id,
        token=settings.api.resolve_token(),
        with_sample=False,
    )
    return {"ok": bool(report.get("compatible")), "report": report}


# Backward-compatible aliases for callers that imported the Phase 3 helper names.
local_config_resource = get_local_config
local_last_inspection_resource = get_last_inspection
local_last_sync_resource = get_last_sync
local_rag_readiness_resource = get_local_rag_readiness
local_failed_uploads_resource = get_failed_uploads
project_sources_resource = get_project_sources
project_coverage_resource = get_project_coverage
project_core_capabilities_resource = get_project_core_capabilities


def _redacted_config(settings: AppSettings) -> dict[str, Any]:
    data = settings.model_dump(mode="json")
    api = data.setdefault("api", {})
    api.pop("token", None)
    api["token_present"] = bool(settings.api.resolve_token())
    if settings.api.token_env:
        api["token_env"] = settings.api.token_env
    return data


def _safe_sync_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key not in {"payload_json", "token"}}


def _first_existing_source_path(settings: AppSettings) -> Path | None:
    for source in settings.sources:
        path = Path(source.path).expanduser()
        if path.exists():
            return path
    return None
