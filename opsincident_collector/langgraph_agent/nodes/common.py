from __future__ import annotations

from pathlib import Path
from typing import Any

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.analysis import (
    build_rag_readiness_report,
    build_source_coverage_report,
    generate_eval_seed_cases,
)
from opsincident_collector.core.pipeline import inspect_source, run_sync
from opsincident_collector.mcp_server.prompt_loader import load_prompt
from opsincident_collector.processors.path_policy import is_allowed_path
from opsincident_collector.state.sqlite_store import SQLiteStore


def load_settings_for_state(state: dict[str, Any]) -> AppSettings:
    config_path = state.get("config_path")
    return load_settings_optional(Path(config_path) if config_path else None)


def append_error(state: dict[str, Any], error: str) -> dict[str, Any]:
    errors = [*state.get("errors", []), error]
    return {"errors": errors, "status": "failed"}


def append_warning(state: dict[str, Any], warning: str) -> dict[str, Any]:
    return {"warnings": [*state.get("warnings", []), warning]}


def load_config_node(state: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings_for_state(state)
    return {
        "config_loaded": True,
        "config_summary": {
            "api_url_configured": bool(settings.api.base_url),
            "project_id": settings.project.id,
            "collector_mode": settings.collector.mode,
            "source_count": len(settings.sources),
            "token_present": bool(settings.api.resolve_token()),
            "token_env": settings.api.token_env,
            "state_path": str(settings.state.sqlite_path),
        },
        "status": "running",
    }


def validate_path_policy_node(state: dict[str, Any]) -> dict[str, Any]:
    path = state.get("path")
    if not path:
        return {"path_policy": {"allowed": True, "reason": "no local path supplied"}}
    settings = load_settings_for_state(state)
    resolved = Path(path).expanduser().resolve()
    allowed = is_allowed_path(resolved, settings.security.allow_paths)
    policy = {
        "path": str(resolved),
        "allowed": allowed,
        "allow_paths": list(settings.security.allow_paths),
    }
    if not allowed:
        return {
            "path_policy": policy | {"reason": "path not allowlisted"},
            "errors": [*state.get("errors", []), f"path is not allowlisted: {resolved}"],
            "status": "failed",
        }
    return {"path_policy": policy | {"reason": "allowed"}}


def inspect_sources_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "failed" or not state.get("path"):
        return {}
    settings = load_settings_for_state(state)
    inspection = inspect_source(Path(state["path"]), settings)
    warnings = [*state.get("warnings", []), *inspection.warnings]
    return {
        "inspection": inspection.model_dump(mode="json"),
        "local_inspection": inspection.model_dump(mode="json"),
        "warnings": sorted(set(warnings)),
    }


def preview_redaction_summary_node(state: dict[str, Any]) -> dict[str, Any]:
    inspection = state.get("inspection") or state.get("local_inspection")
    if not inspection:
        return {}
    settings = load_settings_for_state(state)
    return {
        "redaction_preview": {
            "enabled": settings.security.redact_secrets,
            "possible_secrets_detected": inspection.get("possible_secrets_detected", 0),
            "note": "Graph state stores counts only; raw preview text is not persisted.",
        }
    }


def compute_coverage_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "failed" or not state.get("path"):
        return {}
    settings = load_settings_for_state(state)
    report = build_source_coverage_report(Path(state["path"]), settings)
    warnings = [*state.get("warnings", []), *report.warnings]
    return {
        "coverage": report.model_dump(mode="json"),
        "missing_data": report.missing_recommended_sources,
        "warnings": sorted(set(warnings)),
    }


def compute_rag_readiness_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "failed" or not state.get("path"):
        return {}
    settings = load_settings_for_state(state)
    report = build_rag_readiness_report(Path(state["path"]), settings)
    warnings = [*state.get("warnings", []), *report.weaknesses]
    return {
        "rag_readiness": report.model_dump(mode="json"),
        "warnings": sorted(set(warnings)),
    }


def generate_eval_seed_preview_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "failed" or not state.get("path"):
        return {}
    settings = load_settings_for_state(state)
    cases = generate_eval_seed_cases(Path(state["path"]), settings)
    return {"eval_seed_preview": [case.model_dump(mode="json") for case in cases[:5]]}


def plan_sync_node(state: dict[str, Any]) -> dict[str, Any]:
    inspection = state.get("inspection") or {}
    readiness = state.get("rag_readiness") or {}
    redaction = state.get("redaction_preview") or {}
    path_policy = state.get("path_policy") or {}
    prompt = load_prompt("sync_decision")
    decision = "sync"
    reasons: list[str] = []
    risks: list[str] = []
    if not path_policy.get("allowed", True):
        decision = "do_not_sync"
        reasons.append("path policy failed")
    elif inspection.get("supported_files", 0) == 0:
        decision = "do_not_sync"
        reasons.append("no supported documents found")
    elif not redaction.get("enabled", True) and inspection.get("possible_secrets_detected", 0) > 0:
        decision = "do_not_sync"
        risks.append("secret redaction disabled while possible secrets were detected")
    elif readiness.get("grade") in {"poor", "weak"}:
        decision = "dry_run_first"
        reasons.append("RAG readiness is weak; dry-run recommended first")
    else:
        reasons.append("source has supported, redacted, investigation-ready documents")
    return {
        "sync_plan": {
            "decision": decision,
            "requires_human_approval": bool(
                state.get("export_target") == "api" and not state.get("dry_run", False)
            ),
            "reasons": reasons,
            "risks": risks,
            "prompt_asset": {"name": prompt.name, "version": prompt.version},
        }
    }


def approval_gate_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") in {"failed", "core_unavailable"}:
        return {}
    export_target = state.get("export_target", "api")
    dry_run = bool(state.get("dry_run", False))
    approved = bool(state.get("approved") or state.get("sync_approved"))
    should_sync = bool(state.get("sync_required", True))
    requires = (
        bool(state.get("require_approval", True))
        and should_sync
        and export_target == "api"
        and not dry_run
    )
    if requires and not approved:
        return {
            "status": "pending_approval",
            "approval_request": {
                "action": "sync_source",
                "reason": "API sync uploads normalized documents to IncidentOps Core.",
                "risk_level": "medium",
                "payload_summary": {
                    "path": state.get("path"),
                    "project_id": state.get("project_id"),
                    "export_target": export_target,
                    "dry_run": dry_run,
                    "supported_files": (state.get("inspection") or {}).get("supported_files"),
                },
            },
        }
    return {"status": "approved" if requires else state.get("status", "running")}


def sync_source_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") in {"failed", "pending_approval", "rejected", "core_unavailable"}:
        return {}
    if not state.get("path"):
        return {}
    settings = load_settings_for_state(state)
    export_target = state.get("export_target", "api")
    dry_run = bool(state.get("dry_run", False))
    output = state.get("output")
    summary = run_sync(
        path=Path(state["path"]),
        settings=settings,
        export_target=export_target,
        project_id=state.get("project_id") or settings.project.id,
        source_name=Path(state["path"]).name,
        output=Path(output) if output else None,
        dry_run=dry_run,
        force=False,
        no_redact=False,
        source_type="filesystem",
    )
    return {"sync_summary": summary.model_dump(mode="json")}


def verify_sync_node(state: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings_for_state(state)
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        queue_depth = store.failed_upload_queue_depth()
        last_sync = store.get_last_sync_summary()
        failed_uploads = store.list_failed_uploads()
    finally:
        store.close()
    sync_summary = state.get("sync_summary") or last_sync
    blocking: list[str] = []
    warnings: list[str] = []
    if sync_summary and sync_summary.get("errors_json"):
        blocking.append("sync recorded errors")
    if queue_depth:
        warnings.append(f"{queue_depth} failed upload(s) remain queued")
    readiness = state.get("rag_readiness") or {}
    quality = "strong"
    if blocking:
        quality = "failed"
    elif readiness.get("grade") in {"poor", "weak"} or queue_depth:
        quality = "weak"
    elif readiness.get("grade") == "usable":
        quality = "usable"
    return {
        "sync_summary": sync_summary,
        "failed_uploads": {
            "queue_depth": queue_depth,
            "items": [_safe_failed_upload(row) for row in failed_uploads],
        },
        "post_sync_quality": {
            "sync_quality": quality,
            "blocking_issues": blocking,
            "warnings": warnings,
            "retry_queue_depth": queue_depth,
            "rag_readiness_score": readiness.get("score"),
            "recommended_next_actions": _quality_next_actions(quality, queue_depth),
        },
        "warnings": sorted(set([*state.get("warnings", []), *warnings])),
    }


def check_core_health_node(state: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings_for_state(state)
    if not settings.api.base_url:
        return {
            "core_health": None,
            "status": "core_unavailable",
            "errors": [*state.get("errors", []), "IncidentOps Core API is not configured"],
        }
    client = CoreClient(
        settings.api.base_url,
        token=settings.api.resolve_token(),
        timeout_seconds=settings.api.timeout_seconds,
        verify_tls=settings.api.verify_tls,
    )
    try:
        return {"core_health": client.health(), "status": "running"}
    except Exception as exc:
        return {
            "core_health": {"error": str(exc)},
            "status": "core_unavailable",
            "errors": [*state.get("errors", []), f"Core health check failed: {exc}"],
        }
    finally:
        client.close()


def get_core_capabilities_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "core_unavailable":
        return {}
    settings = load_settings_for_state(state)
    if not settings.api.base_url:
        return {}
    client = CoreClient(
        settings.api.base_url,
        token=settings.api.resolve_token(),
        timeout_seconds=settings.api.timeout_seconds,
        verify_tls=settings.api.verify_tls,
    )
    try:
        capabilities = client.capabilities()
        return {"core_capabilities": capabilities.model_dump(mode="json") if capabilities else None}
    except Exception as exc:
        return {"warnings": [*state.get("warnings", []), f"Core capabilities unavailable: {exc}"]}
    finally:
        client.close()


def decide_if_sync_needed_node(state: dict[str, Any]) -> dict[str, Any]:
    readiness = state.get("rag_readiness") or {}
    coverage = state.get("coverage") or {}
    missing = coverage.get("missing_recommended_sources", [])
    sync_required = bool(state.get("path")) and (
        not readiness.get("ready_for_investigation", False) or bool(missing)
    )
    return {"sync_required": sync_required, "missing_data": missing}


def sync_source_if_needed_node(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("sync_required"):
        return {}
    return sync_source_node(state)


def call_core_investigate_node(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") in {"failed", "pending_approval", "rejected", "core_unavailable"}:
        return {}
    settings = load_settings_for_state(state)
    if not settings.api.base_url:
        return {"status": "core_unavailable"}
    client = CoreClient(
        settings.api.base_url,
        token=settings.api.resolve_token(),
        timeout_seconds=settings.api.timeout_seconds,
        verify_tls=settings.api.verify_tls,
    )
    payload: dict[str, Any] = {
        "project_id": state["project_id"],
        "query": state["query"],
        "debug": bool(state.get("debug", False)),
    }
    if state.get("top_k") is not None:
        payload["top_k"] = state.get("top_k")
    try:
        return {
            "core_investigation_result": client.investigate(payload),
            "status": "core_investigation_complete",
        }
    except Exception as exc:
        return {
            "core_investigation_result": {"error": str(exc)},
            "status": "core_unavailable",
            "errors": [*state.get("errors", []), f"Core investigate failed: {exc}"],
        }
    finally:
        client.close()


def _quality_next_actions(quality: str, queue_depth: int) -> list[str]:
    if quality == "failed":
        return ["fix sync errors", "rerun sync"]
    if queue_depth:
        return ["retry failed uploads", "verify Core ingestion endpoint health"]
    if quality == "weak":
        return ["add missing recommended source types", "rerun readiness report"]
    return ["proceed to Core investigation when needed"]


def _safe_failed_upload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "sync_id": row.get("sync_id"),
        "source_name": row.get("source_name"),
        "path": row.get("path"),
        "document_external_id": row.get("document_external_id"),
        "reason": row.get("reason"),
        "retry_count": row.get("retry_count"),
        "next_retry_at": row.get("next_retry_at"),
        "last_error": row.get("last_error"),
    }
