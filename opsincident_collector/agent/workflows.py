from __future__ import annotations

from pathlib import Path

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.pipeline import inspect_source, run_sync


def run_investigation_workflow(
    settings: AppSettings,
    project_id: str,
    query: str,
    sync_if_stale: bool = False,
    approved: bool = False,
) -> dict:
    coverage: list[dict] = []
    missing_data: list[str] = []
    for source in settings.sources:
        inspection = inspect_source(Path(source.path), settings)
        coverage.append({"source": source.name, "inspection": inspection.model_dump(mode="json")})
        kinds = set(inspection.likely_source_types.keys())
        if "logs" not in kinds:
            missing_data.append(f"{source.name}: no logs")
        if "code" not in kinds:
            missing_data.append(f"{source.name}: no code")
        if "deploy_history" not in kinds:
            missing_data.append(f"{source.name}: no deploys")
        if "incident_report" not in kinds:
            missing_data.append(f"{source.name}: no incidents")
        if "runbook" not in kinds:
            missing_data.append(f"{source.name}: no runbooks")

    sync_summary = None
    if sync_if_stale and settings.sources:
        source = settings.sources[0]
        sync_result = run_sync(
            path=Path(source.path),
            settings=settings,
            export_target="api" if settings.api.base_url else "console",
            project_id=project_id,
            source_name=source.name,
            dry_run=not approved and not settings.api.base_url,
            force=False,
            no_redact=False,
            source_type=source.type,
        )
        sync_summary = sync_result.model_dump(mode="json")

    investigation = None
    if settings.api.base_url:
        client = CoreClient(settings.api.base_url, token=settings.api.resolve_token())
        try:
            client.health()
            investigation = client.investigate({"project_id": project_id, "query": query, "debug": True})
        except Exception as exc:
            investigation = {"error": str(exc)}
        finally:
            client.close()

    return {
        "project_id": project_id,
        "query": query,
        "coverage": coverage,
        "missing_data": sorted(set(missing_data)),
        "sync": sync_summary,
        "investigation": investigation,
        "confidence": "medium" if investigation and "error" not in investigation else "low",
        "next_steps": [
            "sync missing sources" if missing_data else "review current evidence",
            (
                "query IncidentOps Core investigate endpoint"
                if settings.api.base_url and not (investigation and "error" in investigation)
                else "bring IncidentOps Core online or continue in local-only mode"
            ),
        ],
    }
