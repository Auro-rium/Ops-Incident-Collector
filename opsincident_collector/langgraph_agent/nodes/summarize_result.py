from __future__ import annotations

from typing import Any

from opsincident_collector.mcp_server.prompt_loader import load_prompt


def summarize_source_onboarding_node(state: dict[str, Any]) -> dict[str, Any]:
    status = state.get("status", "completed")
    if status not in {"failed", "pending_approval", "rejected"}:
        status = "completed"
    return {
        "status": status,
        "final_report": {
            "type": "source_onboarding",
            "path": state.get("path"),
            "readiness_score": (state.get("rag_readiness") or {}).get("score"),
            "source_coverage": state.get("coverage"),
            "sync_decision": state.get("sync_plan"),
            "approval_status": status if status == "pending_approval" else "not_pending",
            "approval_request": state.get("approval_request"),
            "sync_summary": state.get("sync_summary"),
            "post_sync_quality": state.get("post_sync_quality"),
            "failed_upload_queue_depth": (
                state.get("failed_uploads") or {}
            ).get("queue_depth"),
            "missing_data": (state.get("coverage") or {}).get("missing_recommended_sources", []),
            "next_steps": _next_steps(state),
            "prompt_assets": [
                _prompt_meta("sync_decision"),
                _prompt_meta("post_sync_quality_gate"),
            ],
        },
    }


def summarize_rag_readiness_node(state: dict[str, Any]) -> dict[str, Any]:
    status = "failed" if state.get("errors") else "completed"
    return {
        "status": status,
        "final_report": {
            "type": "rag_readiness",
            "path": state.get("path"),
            "inspection": state.get("inspection"),
            "coverage": state.get("coverage"),
            "rag_readiness": state.get("rag_readiness"),
            "eval_seed_preview": state.get("eval_seed_preview", []),
            "prompt_assets": [
                _prompt_meta("source_coverage_review"),
                _prompt_meta("rag_readiness_report"),
            ],
        },
    }


def summarize_sync_quality_node(state: dict[str, Any]) -> dict[str, Any]:
    quality = state.get("post_sync_quality") or {}
    return {
        "status": "completed" if not state.get("errors") else "failed",
        "final_report": {
            "type": "sync_quality",
            "path": state.get("path"),
            "sync_summary": state.get("sync_summary"),
            "failed_uploads": state.get("failed_uploads"),
            "coverage": state.get("coverage"),
            "rag_readiness": state.get("rag_readiness"),
            "sync_quality": quality.get("sync_quality", "weak"),
            "blocking_issues": quality.get("blocking_issues", []),
            "warnings": quality.get("warnings", []),
            "recommended_next_actions": quality.get("recommended_next_actions", []),
            "prompt_assets": [_prompt_meta("post_sync_quality_gate")],
        },
    }


def summarize_investigation_bridge_node(state: dict[str, Any]) -> dict[str, Any]:
    status = state.get("status", "completed")
    if status == "running":
        status = "completed"
    core_result = state.get("core_investigation_result")
    return {
        "status": status,
        "final_report": {
            "type": "investigation_bridge",
            "project_id": state.get("project_id"),
            "query": state.get("query"),
            "core_reachable": bool(state.get("core_health")) and status != "core_unavailable",
            "source_readiness": state.get("rag_readiness"),
            "sync_required": state.get("sync_required"),
            "sync_summary": state.get("sync_summary"),
            "core_investigation_status": "called" if core_result else "not_called",
            "core_investigation_result": core_result,
            "missing_data": state.get("missing_data", []),
            "next_steps": _investigation_next_steps(state),
            "local_diagnosis": None,
            "note": "Collector did not diagnose locally; Core remains the investigation brain.",
            "prompt_assets": [
                _prompt_meta("core_investigation_bridge"),
                _prompt_meta("missing_data_advisor"),
            ],
        },
    }


def _next_steps(state: dict[str, Any]) -> list[str]:
    if state.get("status") == "pending_approval":
        approval = state.get("approval_request") or {}
        approval_id = approval.get("approval_id", "<approval_id>")
        return [f"approve or reject DATA_EXPORT approval {approval_id}"]
    if state.get("errors"):
        return ["fix reported errors", "rerun graph"]
    quality = state.get("post_sync_quality") or {}
    return quality.get("recommended_next_actions") or ["review readiness report"]


def _investigation_next_steps(state: dict[str, Any]) -> list[str]:
    if state.get("status") == "core_unavailable":
        return ["bring IncidentOps Core online", "review local readiness and missing data"]
    if state.get("status") == "pending_approval":
        return ["approve sync if you want Collector to upload evidence before Core investigation"]
    if not state.get("core_investigation_result"):
        return ["call Core investigate after sync/readiness requirements are met"]
    return ["review Core investigation result and citations returned by Core"]


def _prompt_meta(name: str) -> dict[str, str]:
    prompt = load_prompt(name)
    return {"name": prompt.name, "version": prompt.version}
