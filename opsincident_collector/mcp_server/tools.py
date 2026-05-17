from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.adapters.core_contract_validator import (
    validate_core_contract as run_core_contract_validation,
)
from opsincident_collector.config.loader import load_settings, load_settings_optional
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.analysis import (
    build_rag_readiness_report,
    build_source_coverage_report,
    generate_eval_seed_cases,
    write_eval_seed_jsonl,
)
from opsincident_collector.core.pipeline import inspect_source, run_sync
from opsincident_collector.processors.path_policy import ensure_path_allowed, is_denied_path
from opsincident_collector.processors.secret_redactor import redact_text
from opsincident_collector.security.audit import record_audit_event
from opsincident_collector.security.permission_policy import (
    PermissionDecision,
    check_tool_permission,
    permission_level_for_tool,
)
from opsincident_collector.state.sqlite_store import SQLiteStore
from opsincident_collector.mcp_server.schemas import (
    EvalSeedInput,
    ExportReportInput,
    InspectFolderInput,
    InvestigateIncidentInput,
    PreviewRedactionInput,
    RAGReadinessInput,
    RunLookupInput,
    SearchEvidenceInput,
    SourceCoverageInput,
    SyncSourceInput,
    ValidateCoreContractInput,
    ValidateSourceConfigInput,
    WorkflowRunInput,
)


CORE_UNAVAILABLE_GUIDANCE = (
    "Run get_rag_readiness or sync_source first; Core investigation remains in Core."
)


def inspect_folder(
    path: str,
    max_depth: int = 8,
    config_path: str | None = None,
    format: str = "json",
) -> dict:
    request = InspectFolderInput(
        path=path,
        max_depth=max_depth,
        config_path=config_path,
        format=format,
    )
    settings = _load_settings(request.config_path)
    result = inspect_source(Path(request.path), settings, max_depth=request.max_depth or 8)
    coverage = build_source_coverage_report(
        Path(request.path),
        settings,
        max_depth=request.max_depth or 8,
    )
    _audit(settings, "inspect_folder", PermissionDecision(True, "allowed"), path=request.path)
    payload = {
        "ok": True,
        "inspection": result.model_dump(mode="json"),
        "coverage": coverage.model_dump(mode="json"),
        "warnings": result.warnings + coverage.warnings,
    }
    # Backward-compatible summary fields for callers that used the v1 MCP helper directly.
    payload.update(
        {
            "supported_files": result.supported_files,
            "total_files": result.total_files,
            "denied_files": result.denied_files,
        }
    )
    return payload


def validate_source_config(config_path: str) -> dict:
    request = ValidateSourceConfigInput(config_path=config_path)
    settings = load_settings(Path(request.config_path))
    errors: list[str] = []
    warnings: list[str] = []

    for allow_path in settings.security.allow_paths:
        resolved = Path(allow_path).expanduser().resolve()
        if not resolved.exists():
            warnings.append(f"allowed path does not exist: {allow_path}")
        if resolved == Path.home().resolve():
            warnings.append("allowing the entire home directory is unsafe for MCP tools")
        if resolved == Path("/"):
            warnings.append("allowing the filesystem root is unsafe for MCP tools")

    for source in settings.sources:
        source_path = Path(source.path).expanduser().resolve()
        if not source_path.exists():
            errors.append(f"source path does not exist: {source.path}")

    if settings.api.base_url and not settings.api.token_env and settings.api.auth_required:
        warnings.append("api.token_env is not configured; prefer env-based Core tokens")
    if not settings.security.deny_patterns:
        errors.append("security.deny_patterns is empty")
    if settings.sync.max_file_size_mb <= 0:
        errors.append("sync.max_file_size_mb must be positive")

    return {
        "ok": not errors,
        "valid": not errors,
        "source_count": len(settings.sources),
        "collector_mode": settings.collector.mode,
        "api_url_configured": bool(settings.api.base_url),
        "token_env": settings.api.token_env,
        "token_present": bool(settings.api.resolve_token()),
        "deny_patterns_count": len(settings.security.deny_patterns),
        "errors": errors,
        "warnings": warnings,
    }


def preview_redaction(path: str, max_lines: int = 100, config_path: str | None = None) -> dict:
    request = PreviewRedactionInput(path=path, max_lines=max_lines, config_path=config_path)
    settings = _load_settings(request.config_path)
    file_path = Path(request.path).expanduser().resolve()
    decision = check_tool_permission(settings, "preview_redaction", path=file_path)
    if not decision.allowed:
        _audit(settings, "preview_redaction", decision, path=str(file_path))
        raise PermissionError(decision.reason)
    _ensure_not_denied(file_path, settings)

    raw_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    selected_lines = raw_lines[: max(request.max_lines, 0)]
    preview, summary = redact_text("\n".join(selected_lines), enabled=True)
    _audit(
        settings,
        "preview_redaction",
        decision,
        path=str(file_path),
        redacted_count=summary.redacted_count,
        truncated=len(raw_lines) > len(selected_lines),
    )
    return {
        "ok": True,
        "redaction_summary": summary.model_dump(mode="json"),
        "preview": preview,
        "truncated": len(raw_lines) > len(selected_lines),
        "warning": None,
    }


def sync_source(
    path: str,
    export_target: str = "api",
    project_id: str | None = None,
    source_name: str | None = None,
    dry_run: bool = False,
    approved: bool = False,
    yes: bool = False,
    config_path: str | None = None,
    output: str | None = None,
) -> dict:
    request = SyncSourceInput(
        path=path,
        export_target=export_target,
        project_id=project_id,
        source_name=source_name,
        dry_run=dry_run,
        approved=approved,
        yes=yes,
        config_path=config_path,
        output=output,
    )
    settings = _load_settings(request.config_path)
    approved_for_export = request.approved or request.yes
    decision = check_tool_permission(
        settings,
        "sync_source",
        path=Path(request.path).expanduser().resolve(),
        approved=approved_for_export,
        dry_run=request.dry_run,
    )
    if not decision.allowed:
        _audit(
            settings,
            "sync_source",
            decision,
            path=request.path,
            export_target=request.export_target,
        )
        raise PermissionError(decision.reason)
    if request.export_target == "api" and not request.dry_run and not approved_for_export:
        decision = PermissionDecision(False, "approval required for API upload")
        _audit(
            settings,
            "sync_source",
            decision,
            path=request.path,
            export_target=request.export_target,
        )
        raise PermissionError(decision.reason)

    summary = run_sync(
        path=Path(request.path),
        settings=settings,
        export_target=request.export_target,
        project_id=request.project_id or settings.project.id,
        source_name=request.source_name or Path(request.path).name,
        output=Path(request.output) if request.output else None,
        dry_run=request.dry_run,
        force=False,
        no_redact=False,
        source_type="filesystem",
    )
    _audit(
        settings,
        "sync_source",
        decision,
        path=request.path,
        project_id=request.project_id or settings.project.id,
        export_target=request.export_target,
        documents_synced=summary.documents_synced,
        failed_uploads=summary.failed_uploads,
    )
    payload = {"ok": True, "summary": summary.model_dump(mode="json"), "warnings": summary.warnings}
    payload.update(summary.model_dump(mode="json"))
    return payload


def get_source_coverage(
    path: str | None = None,
    project_id: str | None = None,
    config_path: str | None = None,
) -> dict:
    request = SourceCoverageInput(path=path, project_id=project_id, config_path=config_path)
    settings = _load_settings(request.config_path)
    if request.path:
        coverage = build_source_coverage_report(Path(request.path), settings)
        return {
            "ok": True,
            "coverage": coverage.model_dump(mode="json"),
            "warnings": coverage.warnings,
        }

    if request.project_id and settings.api.base_url:
        client_or_error = _core_client(settings)
        if isinstance(client_or_error, dict):
            return client_or_error
        client = client_or_error
        try:
            sources = client.list_sources(request.project_id)
            return {
                "ok": True,
                "project_id": request.project_id,
                "core_sources": sources,
                "coverage": None,
                "warnings": ["Core source list returned; local coverage requires a path."],
            }
        except Exception as exc:
            return _core_error("Core source coverage unavailable", exc)
        finally:
            client.close()

    source_path = _first_configured_source_path(settings)
    if source_path:
        coverage = build_source_coverage_report(source_path, settings)
        return {
            "ok": True,
            "coverage": coverage.model_dump(mode="json"),
            "warnings": coverage.warnings,
        }

    checkpoint = _local_checkpoint(settings)
    if checkpoint:
        return {
            "ok": True,
            "coverage": None,
            "local_checkpoint": checkpoint,
            "warnings": ["No path supplied; returning last local checkpoint only."],
        }
    return {
        "ok": False,
        "error": "No path, Core project, or local coverage checkpoint is available.",
    }


def get_rag_readiness(path: str, config_path: str | None = None) -> dict:
    request = RAGReadinessInput(path=path, config_path=config_path)
    settings = _load_settings(request.config_path)
    report = build_rag_readiness_report(Path(request.path), settings)
    return {
        "ok": True,
        "rag_readiness": report.model_dump(mode="json"),
        "warnings": report.weaknesses,
    }


def search_evidence(
    project_id: str,
    query: str,
    top_k: int = 10,
    filters: dict[str, Any] | None = None,
    debug: bool = False,
    config_path: str | None = None,
) -> dict:
    request = SearchEvidenceInput(
        project_id=project_id,
        query=query,
        top_k=top_k,
        filters=filters,
        debug=debug,
        config_path=config_path,
    )
    settings = _load_settings(request.config_path)
    client_or_error = _core_client(settings)
    if isinstance(client_or_error, dict):
        return client_or_error
    client = client_or_error
    payload = {
        "project_id": request.project_id,
        "query": request.query,
        "top_k": request.top_k,
        "debug": request.debug,
    }
    if request.filters:
        payload["filters"] = request.filters
    try:
        return {"ok": True, "response": client.search(payload)}
    except Exception as exc:
        return _core_error("Core search unavailable", exc)
    finally:
        client.close()


def investigate_incident(
    project_id: str,
    query: str,
    top_k: int | None = None,
    debug: bool = False,
    config_path: str | None = None,
) -> dict:
    request = InvestigateIncidentInput(
        project_id=project_id,
        query=query,
        top_k=top_k,
        debug=debug,
        config_path=config_path,
    )
    settings = _load_settings(request.config_path)
    client_or_error = _core_client(settings)
    if isinstance(client_or_error, dict):
        return client_or_error | {"local_guidance": CORE_UNAVAILABLE_GUIDANCE}
    client = client_or_error
    payload: dict[str, Any] = {
        "project_id": request.project_id,
        "query": request.query,
        "debug": request.debug,
    }
    if request.top_k is not None:
        payload["top_k"] = request.top_k
    try:
        return {"ok": True, "response": client.investigate(payload)}
    except Exception as exc:
        return _core_error(
            "Core investigate unavailable",
            exc,
            local_guidance=CORE_UNAVAILABLE_GUIDANCE,
        )
    finally:
        client.close()


def create_workflow_run(
    project_id: str,
    query: str,
    top_k: int | None = None,
    approved: bool = False,
    config_path: str | None = None,
) -> dict:
    request = WorkflowRunInput(
        project_id=project_id,
        query=query,
        top_k=top_k,
        approved=approved,
        config_path=config_path,
    )
    settings = _load_settings(request.config_path)
    decision = check_tool_permission(settings, "create_workflow_run", approved=request.approved)
    if not decision.allowed:
        _audit(settings, "create_workflow_run", decision, project_id=request.project_id)
        raise PermissionError(decision.reason)
    client_or_error = _core_client(settings)
    if isinstance(client_or_error, dict):
        return client_or_error
    client = client_or_error
    payload: dict[str, Any] = {"project_id": request.project_id, "query": request.query}
    if request.top_k is not None:
        payload["top_k"] = request.top_k
    try:
        response = client.create_run(payload)
        _audit(
            settings,
            "create_workflow_run",
            decision,
            project_id=request.project_id,
            run_id=response.get("id") or response.get("run_id"),
        )
        return {"ok": True, "response": response}
    except Exception as exc:
        return _core_error("Core workflow run creation unavailable", exc)
    finally:
        client.close()


def get_run_status(run_id: str, config_path: str | None = None) -> dict:
    request = RunLookupInput(run_id=run_id, config_path=config_path)
    settings = _load_settings(request.config_path)
    client_or_error = _core_client(settings)
    if isinstance(client_or_error, dict):
        return client_or_error
    client = client_or_error
    try:
        return {"ok": True, "response": client.get_run_status(request.run_id)}
    except Exception as exc:
        return _core_error("Core run status unavailable", exc)
    finally:
        client.close()


def get_run_events(run_id: str, config_path: str | None = None) -> dict:
    request = RunLookupInput(run_id=run_id, config_path=config_path)
    settings = _load_settings(request.config_path)
    client_or_error = _core_client(settings)
    if isinstance(client_or_error, dict):
        return client_or_error
    client = client_or_error
    try:
        return {"ok": True, "response": client.get_run_events(request.run_id)}
    except Exception as exc:
        return _core_error("Core run events unavailable", exc)
    finally:
        client.close()


def export_report(
    run_id: str | None = None,
    path: str | None = None,
    format: str = "markdown",
    output: str | None = None,
    approved: bool = False,
    config_path: str | None = None,
) -> dict:
    request = ExportReportInput(
        run_id=run_id,
        path=path,
        format=format,
        output=output,
        approved=approved,
        config_path=config_path,
    )
    settings = _load_settings(request.config_path)
    if request.output:
        _require_data_export(settings, "export_report", approved=request.approved)
        ensure_path_allowed(
            Path(request.output).expanduser().resolve(),
            settings.security.allow_paths,
        )

    report_data: dict[str, Any]
    if request.run_id:
        status = get_run_status(request.run_id, config_path=request.config_path)
        events = get_run_events(request.run_id, config_path=request.config_path)
        report_data = {
            "type": "core_run_report",
            "run_id": request.run_id,
            "status": status,
            "events": events,
            "note": "Collector exports Core run data only; it does not diagnose incidents locally.",
        }
    elif request.path:
        coverage = build_source_coverage_report(Path(request.path), settings)
        readiness = build_rag_readiness_report(Path(request.path), settings)
        report_data = {
            "type": "local_rag_readiness_report",
            "coverage": coverage.model_dump(mode="json"),
            "rag_readiness": readiness.model_dump(mode="json"),
            "note": (
                "Core owns retrieval, reranking, investigation, answer generation, "
                "and citations."
            ),
        }
    else:
        return {"ok": False, "error": "export_report requires either run_id or path"}

    content = _format_report(report_data, request.format)
    if request.output:
        Path(request.output).write_text(content, encoding="utf-8")
        _audit(
            settings,
            "export_report",
            PermissionDecision(True, "allowed"),
            permission_level="DATA_EXPORT",
            output=request.output,
            run_id=request.run_id,
            path=request.path,
        )
    return {"ok": True, "format": request.format, "content": content, "output": request.output}


def generate_eval_seed(
    path: str,
    output: str | None = None,
    approved: bool = False,
    config_path: str | None = None,
) -> dict:
    request = EvalSeedInput(path=path, output=output, approved=approved, config_path=config_path)
    settings = _load_settings(request.config_path)
    if request.output:
        _require_data_export(settings, "generate_eval_seed", approved=request.approved)
        ensure_path_allowed(
            Path(request.output).expanduser().resolve(),
            settings.security.allow_paths,
        )
    cases = generate_eval_seed_cases(Path(request.path), settings)
    if request.output:
        write_eval_seed_jsonl(cases, Path(request.output))
        _audit(
            settings,
            "generate_eval_seed",
            PermissionDecision(True, "allowed"),
            permission_level="DATA_EXPORT",
            path=request.path,
            output=request.output,
            cases=len(cases),
        )
    return {
        "ok": True,
        "cases": [case.model_dump(mode="json") for case in cases],
        "case_count": len(cases),
        "output": request.output,
    }


def validate_core_contract(
    api_url: str | None = None,
    project_id: str | None = None,
    with_sample: bool = False,
    approved: bool = False,
    config_path: str | None = None,
) -> dict:
    request = ValidateCoreContractInput(
        api_url=api_url,
        project_id=project_id,
        with_sample=with_sample,
        approved=approved,
        config_path=config_path,
    )
    settings = _load_settings(request.config_path)
    if request.with_sample:
        _require_data_export(settings, "validate_core_contract", approved=request.approved)
    resolved_api_url = request.api_url or settings.api.base_url
    resolved_project_id = request.project_id or settings.project.id
    if not resolved_api_url or not resolved_project_id:
        return {"ok": False, "error": "validate_core_contract requires api_url and project_id"}
    report = run_core_contract_validation(
        api_url=resolved_api_url,
        project_id=resolved_project_id,
        token=settings.api.resolve_token(),
        with_sample=request.with_sample,
    )
    return {
        "ok": bool(report.get("compatible")),
        "report": report,
        "warnings": report.get("warnings", []),
    }


def _load_settings(config_path: str | None) -> AppSettings:
    return load_settings_optional(Path(config_path) if config_path else None)


def _audit(
    settings: AppSettings,
    tool_name: str,
    decision: PermissionDecision,
    permission_level: str | None = None,
    **metadata: Any,
) -> None:
    payload = {
        "tool_name": tool_name,
        "permission_level": permission_level or permission_level_for_tool(tool_name).value,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "metadata": _safe_metadata(metadata),
    }
    try:
        record_audit_event(settings.state.sqlite_path.parent, "mcp_tool", payload)
    except Exception:
        # Audit must not make read-only MCP tools unusable if local state is unavailable.
        return


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = {"content", "preview", "payload_json", "token", "authorization"}
    return {key: value for key, value in metadata.items() if key not in blocked}


def _ensure_not_denied(path: Path, settings: AppSettings) -> None:
    relative = _relative_to_allowlist(path, settings)
    candidates = [relative, path.name]
    if any(is_denied_path(candidate, settings.security.deny_patterns) for candidate in candidates):
        raise PermissionError("denied files cannot be read through MCP tools")


def _relative_to_allowlist(path: Path, settings: AppSettings) -> str:
    resolved = path.resolve()
    for allowed in settings.security.allow_paths:
        allowed_path = Path(allowed).expanduser().resolve()
        try:
            return resolved.relative_to(allowed_path).as_posix()
        except ValueError:
            continue
    return path.name


def _require_data_export(settings: AppSettings, tool_name: str, approved: bool) -> None:
    if tool_name in settings.mcp.deny_tools:
        decision = PermissionDecision(False, "tool denied by policy")
    elif settings.mcp.require_approval_for_sync or tool_name in settings.mcp.require_approval:
        decision = PermissionDecision(approved, "allowed" if approved else "approval required")
    else:
        decision = PermissionDecision(True, "allowed")
    if not decision.allowed:
        _audit(settings, tool_name, decision, permission_level="DATA_EXPORT")
        raise PermissionError(decision.reason)


def _core_client(settings: AppSettings) -> CoreClient | dict[str, Any]:
    if not settings.api.base_url:
        return {"ok": False, "error": "IncidentOps Core API is not configured"}
    token = settings.api.resolve_token()
    if settings.api.auth_required and not token:
        return {
            "ok": False,
            "error": (
                "IncidentOps API calls require a token. "
                "Set INCIDENTOPS_TOKEN or configure api.token_env."
            ),
        }
    return CoreClient(
        settings.api.base_url,
        token=token,
        timeout_seconds=settings.api.timeout_seconds,
        verify_tls=settings.api.verify_tls,
    )


def _core_error(message: str, exc: Exception, local_guidance: str | None = None) -> dict[str, Any]:
    payload = {"ok": False, "error": f"{message}: {exc}"}
    if local_guidance:
        payload["local_guidance"] = local_guidance
    return payload


def _local_checkpoint(settings: AppSettings) -> dict[str, Any] | None:
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        return store.get_source_checkpoint("default")
    finally:
        store.close()


def _first_configured_source_path(settings: AppSettings) -> Path | None:
    for source in settings.sources:
        path = Path(source.path).expanduser()
        if path.exists():
            return path
    return None


def _format_report(report_data: dict[str, Any], format: str) -> str:
    if format == "json":
        return json.dumps(report_data, indent=2, default=str)
    title = report_data["type"].replace("_", " ").title()
    lines = [
        f"# {title}",
        "",
        report_data.get("note", ""),
        "",
        "```json",
        json.dumps(report_data, indent=2, default=str),
        "```",
    ]
    return "\n".join(lines)
