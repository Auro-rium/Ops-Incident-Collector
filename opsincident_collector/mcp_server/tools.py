from __future__ import annotations

from pathlib import Path

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.loader import load_settings, load_settings_optional
from opsincident_collector.core.pipeline import inspect_source, run_sync
from opsincident_collector.processors.secret_redactor import redact_text
from opsincident_collector.security.permission_policy import check_tool_permission
from opsincident_collector.state.sqlite_store import SQLiteStore


def inspect_folder(path: str, max_depth: int = 8, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    result = inspect_source(Path(path), settings, max_depth=max_depth)
    return result.model_dump(mode="json")


def validate_source_config(config_path: str) -> dict:
    settings = load_settings(Path(config_path))
    return {
        "valid": True,
        "source_count": len(settings.sources),
        "collector_mode": settings.collector.mode,
    }


def preview_redaction(path: str, max_lines: int = 100, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    file_path = Path(path).resolve()
    decision = check_tool_permission(settings, "preview_redaction", path=file_path)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()[:max_lines]
    preview, summary = redact_text("\n".join(lines), enabled=True)
    return {
        "redaction_summary": summary.model_dump(mode="json"),
        "preview": preview,
        "warning": None,
    }


def sync_source(
    path: str,
    export_target: str = "api",
    project_id: str | None = None,
    source_name: str | None = None,
    dry_run: bool = False,
    approved: bool = False,
    config_path: str | None = None,
    output: str | None = None,
) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    decision = check_tool_permission(settings, "sync_source", path=Path(path).resolve(), approved=approved, dry_run=dry_run)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    summary = run_sync(
        path=Path(path),
        settings=settings,
        export_target=export_target,
        project_id=project_id,
        source_name=source_name or Path(path).name,
        output=Path(output) if output else None,
        dry_run=dry_run,
        force=False,
        no_redact=False,
        source_type="filesystem",
    )
    return summary.model_dump(mode="json")


def get_source_coverage(project_id: str, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        checkpoint = store.get_source_checkpoint("default")
    finally:
        store.close()
    return {
        "project_id": project_id,
        "local_checkpoint": checkpoint,
    }


def search_evidence(project_id: str, query: str, top_k: int = 10, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"error": "IncidentOps Core API is not configured"}
    client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
    try:
        return client.search({"project_id": project_id, "query": query, "top_k": top_k})
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        client.close()


def investigate_incident(project_id: str, query: str, debug: bool = False, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"error": "IncidentOps Core API is not configured"}
    client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
    try:
        return client.investigate({"project_id": project_id, "query": query, "debug": debug})
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        client.close()


def create_workflow_run(project_id: str, query: str, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"error": "IncidentOps Core API is not configured"}
    client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
    try:
        return client.create_run({"project_id": project_id, "query": query})
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        client.close()


def get_run_status(run_id: str, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"error": "IncidentOps Core API is not configured"}
    client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
    try:
        return client.get_run_status(run_id)
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        client.close()


def get_run_events(run_id: str, config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"error": "IncidentOps Core API is not configured"}
    client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
    try:
        return client.get_run_events(run_id)
    except Exception as exc:
        return {"error": str(exc)}
    finally:
        client.close()


def export_report(run_id: str, format: str = "markdown", config_path: str | None = None) -> dict:
    settings = load_settings_optional(Path(config_path) if config_path else None)
    if not settings.api.base_url:
        return {"run_id": run_id, "format": format, "content": f"# Run {run_id}\n\nLocal summary unavailable."}
    status = get_run_status(run_id, config_path=config_path)
    return {
        "run_id": run_id,
        "format": format,
        "content": f"# Run {run_id}\n\nStatus: {status.get('status', 'unknown')}",
    }
