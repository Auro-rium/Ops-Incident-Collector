from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.models import SyncSummary
from opsincident_collector.core.pipeline import API_TOKEN_REQUIRED_MESSAGE
from opsincident_collector.exporters.incidentops_api import IncidentOpsAPIExporter
from opsincident_collector.state.sqlite_store import SQLiteStore


def get_queue_status(settings: AppSettings) -> dict:
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        return store.failed_upload_queue_status(settings.sync.retry_count)
    finally:
        store.close()


def retry_queue(
    settings: AppSettings,
    *,
    project_id: str | None = None,
    source_name: str | None = None,
) -> dict:
    if not settings.api.base_url:
        raise ValueError("queue retry requires api.base_url")
    resolved_project_id = project_id or settings.project.id
    if not resolved_project_id:
        raise ValueError("queue retry requires project.id or --project-id")
    token = settings.api.resolve_token()
    if settings.api.auth_required and not token:
        raise ValueError(API_TOKEN_REQUIRED_MESSAGE)

    store = SQLiteStore(settings.state.sqlite_path)
    summaries: list[dict] = []
    try:
        status = store.failed_upload_queue_status(settings.sync.retry_count)
        sources = [source_name] if source_name else sorted(status["by_source"].keys())
        for current_source in sources:
            if not current_source or current_source == "<unknown>":
                continue
            due = store.get_due_failed_uploads(current_source, settings.sync.retry_count)
            if not due:
                continue
            source_type = _source_type_for(settings, current_source)
            client = CoreClient(
                settings.api.base_url,
                token=token,
                timeout_seconds=settings.api.timeout_seconds,
                verify_tls=settings.api.verify_tls,
            )
            summary = SyncSummary(
                sync_id=f"retry_{uuid4().hex[:12]}",
                source_name=current_source,
                source_id=current_source,
                project_id=resolved_project_id,
                export_target="api",
            )
            try:
                exporter = IncidentOpsAPIExporter(
                    client=client,
                    project_id=resolved_project_id,
                    source_name=current_source,
                    source_type=source_type,
                    batch_size=settings.sync.batch_size,
                    store=store,
                    retry_count=settings.sync.retry_count,
                    retry_backoff_seconds=settings.sync.retry_backoff_seconds,
                )
                exporter.export_documents([], summary)
                summary.failed_uploads = store.failed_upload_queue_depth(current_source)
                store.record_sync_run(summary, status="completed")
            finally:
                client.close()
            summaries.append(summary.model_dump(mode="json"))
        return {
            "ok": True,
            "summaries": summaries,
            "queue": store.failed_upload_queue_status(settings.sync.retry_count),
        }
    finally:
        store.close()


def clear_queue(settings: AppSettings, *, failed_before_days: int) -> dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=failed_before_days)).isoformat()
    store = SQLiteStore(settings.state.sqlite_path)
    try:
        cleared = store.clear_failed_uploads_before(cutoff)
        return {
            "ok": True,
            "cleared": cleared,
            "queue": store.failed_upload_queue_status(settings.sync.retry_count),
        }
    finally:
        store.close()


def _source_type_for(settings: AppSettings, source_name: str) -> str:
    for source in settings.sources:
        if source.name == source_name:
            return source.type
    return "filesystem"

