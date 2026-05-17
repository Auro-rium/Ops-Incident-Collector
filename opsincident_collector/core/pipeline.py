from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from uuid import uuid4

from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.limits import DEFAULT_MAX_FILE_SIZE_MB
from opsincident_collector.core.models import RawDocument, SkippedFile, SourceInspection, SyncSummary
from opsincident_collector.exporters.console_exporter import ConsoleExporter
from opsincident_collector.exporters.incidentops_api import IncidentOpsAPIExporter
from opsincident_collector.exporters.jsonl_exporter import JSONLExporter
from opsincident_collector.exporters.sqlite_exporter import SQLiteExporter
from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.processors.content_classifier import classify_content
from opsincident_collector.processors.file_filter import (
    detect_possible_secret_count,
    is_binary_file,
    is_supported_extension,
)
from opsincident_collector.processors.normalizer import normalize_document
from opsincident_collector.processors.path_policy import ensure_path_allowed, is_denied_path
from opsincident_collector.receivers.filesystem import discover_files
from opsincident_collector.security.audit import record_audit_event
from opsincident_collector.state.checkpoints import should_process_item
from opsincident_collector.state.sqlite_store import SQLiteStore

API_TOKEN_REQUIRED_MESSAGE = (
    "IncidentOps API sync requires a token. Set INCIDENTOPS_TOKEN or configure api.token_env."
)


def inspect_source(
    path: Path,
    settings: AppSettings,
    max_depth: int = 8,
    max_file_size_mb: int | None = None,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> SourceInspection:
    ensure_path_allowed(path, settings.security.allow_paths)
    max_size_mb = max_file_size_mb or settings.sync.max_file_size_mb or DEFAULT_MAX_FILE_SIZE_MB
    supported_extensions: Counter[str] = Counter()
    unsupported_extensions: Counter[str] = Counter()
    likely_source_types: Counter[str] = Counter()
    skipped_files: list[SkippedFile] = []
    warnings: list[str] = []

    inspection = SourceInspection(path=str(path))
    for item in discover_files(path, max_depth=max_depth, include=include or [], exclude=exclude or []):
        inspection.total_files += 1
        relative_path = item.relative_path
        if is_denied_path(relative_path, settings.security.deny_patterns):
            inspection.denied_files += 1
            skipped_files.append(SkippedFile(path=relative_path, reason="denied", size_bytes=item.size_bytes))
            continue
        if item.size_bytes == 0:
            inspection.empty_files += 1
            skipped_files.append(SkippedFile(path=relative_path, reason="empty", size_bytes=0))
            continue
        if item.size_bytes > max_size_mb * 1024 * 1024:
            inspection.oversized_files += 1
            skipped_files.append(
                SkippedFile(path=relative_path, reason="oversized", size_bytes=item.size_bytes)
            )
            continue
        if is_binary_file(item.path):
            inspection.binary_files += 1
            skipped_files.append(SkippedFile(path=relative_path, reason="binary", size_bytes=item.size_bytes))
            warnings.append(f"binary file skipped: {relative_path}")
            continue
        if is_supported_extension(item.extension):
            inspection.supported_files += 1
            supported_extensions[item.extension] += 1
            detected_type = classify_content(item.path, item.extension, relative_path=relative_path)
            likely_source_types[detected_type] += 1
            inspection.possible_secrets_detected += detect_possible_secret_count(item.path)
        else:
            inspection.unsupported_files += 1
            unsupported_extensions[item.extension or "<none>"] += 1
            skipped_files.append(
                SkippedFile(path=relative_path, reason="unsupported_extension", size_bytes=item.size_bytes)
            )

    inspection.supported_extensions = dict(sorted(supported_extensions.items()))
    inspection.unsupported_extensions = dict(sorted(unsupported_extensions.items()))
    inspection.likely_source_types = dict(sorted(likely_source_types.items()))
    inspection.skipped_files = skipped_files
    inspection.warnings = sorted(set(warnings))
    if inspection.denied_files:
        inspection.warnings.append(f"{inspection.denied_files} denied file(s) skipped by policy")
    if inspection.oversized_files:
        inspection.warnings.append(f"{inspection.oversized_files} oversized file(s) skipped")
    if inspection.unsupported_files:
        inspection.warnings.append(f"{inspection.unsupported_files} unsupported file(s) skipped")
    return inspection


def _read_raw_document(item) -> RawDocument:
    content = item.path.read_text(encoding="utf-8", errors="ignore")
    return RawDocument(source_item=item, content=content, encoding="utf-8", metadata={})


def _build_exporter(
    export_target: str,
    output: Path | None,
    settings: AppSettings,
    project_id: str | None,
    source_name: str,
    source_type: str,
    store: SQLiteStore | None = None,
):
    if export_target == "jsonl":
        if not output:
            raise ValueError("--output is required for jsonl export")
        return JSONLExporter(output)
    if export_target == "sqlite":
        if not output:
            raise ValueError("--output is required for sqlite export")
        return SQLiteExporter(output)
    if export_target == "console":
        return ConsoleExporter()
    if export_target == "api":
        if not settings.api.base_url or not project_id:
            raise ValueError("API export requires configured base_url and project_id")
        token = settings.api.resolve_token()
        if settings.api.auth_required and not token:
            raise ValueError(API_TOKEN_REQUIRED_MESSAGE)
        client = CoreClient(
            settings.api.base_url,
            token=token,
            timeout_seconds=settings.api.timeout_seconds,
            verify_tls=settings.api.verify_tls,
        )
        return IncidentOpsAPIExporter(
            client=client,
            project_id=project_id,
            source_name=source_name,
            source_type=source_type,
            batch_size=settings.sync.batch_size,
            store=store,
            retry_count=settings.sync.retry_count,
            retry_backoff_seconds=settings.sync.retry_backoff_seconds,
        )
    raise ValueError(f"unsupported export target: {export_target}")


def run_sync(
    path: Path,
    settings: AppSettings,
    export_target: str,
    project_id: str | None,
    source_name: str,
    output: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    no_redact: bool = False,
    max_depth: int = 8,
    source_type: str = "filesystem",
) -> SyncSummary:
    ensure_path_allowed(path.resolve(), settings.security.allow_paths)
    start = monotonic()
    sync_id = f"sync_{uuid4().hex[:12]}"
    store = SQLiteStore(settings.state.sqlite_path)
    summary = SyncSummary(
        sync_id=sync_id,
        project_id=project_id,
        export_target=export_target,
        source_name=source_name,
        source_id=source_name,
    )
    documents = []
    exporter = None
    try:
        exporter = (
            None
            if dry_run
            else _build_exporter(
                export_target,
                output,
                settings,
                project_id,
                source_name,
                source_type,
                store=store,
            )
        )
        for item in discover_files(path, max_depth=max_depth):
            summary.files_seen += 1
            if is_denied_path(item.relative_path, settings.security.deny_patterns):
                summary.files_skipped += 1
                continue
            if item.size_bytes == 0 or item.size_bytes > settings.sync.max_file_size_mb * 1024 * 1024:
                summary.files_skipped += 1
                continue
            if is_binary_file(item.path) or not is_supported_extension(item.extension):
                summary.files_skipped += 1
                continue

            decision = should_process_item(store, source_name, item) if not force else None
            if decision and not decision.should_process:
                summary.files_skipped += 1
                continue

            raw_document = _read_raw_document(item)
            document = normalize_document(
                raw_document=raw_document,
                source_name=source_name,
                source_type=source_type,
                redact_secrets=not no_redact and settings.security.redact_secrets,
            )
            documents.append(document)
            summary.bytes_processed += document.size_bytes

        if dry_run:
            summary.documents_synced = len(documents)
            summary.files_uploaded = len(documents)
            summary.checkpoint_updated = False
            summary.duration_ms = int((monotonic() - start) * 1000)
            return summary

        uploaded_bytes = exporter.export_documents(documents, summary) if exporter else 0
        failed_external_ids = getattr(exporter, "failed_external_ids", set())
        synced_documents = [
            document for document in documents if document.external_id not in failed_external_ids
        ]
        summary.documents_synced = len(synced_documents) + summary.retry_succeeded
        summary.files_uploaded = len(synced_documents) + summary.retry_succeeded
        summary.bytes_uploaded = uploaded_bytes
        for document in synced_documents:
            store.upsert_file_record(
                source_name=source_name,
                path=document.path,
                relative_path=document.relative_path or document.path,
                checksum=document.checksum,
                size_bytes=document.size_bytes,
                modified_at=document.modified_at.isoformat() if document.modified_at else None,
                last_status="synced",
            )
        for document in documents:
            if document.external_id in failed_external_ids:
                store.upsert_file_record(
                    source_name=source_name,
                    path=document.path,
                    relative_path=document.relative_path or document.path,
                    checksum=document.checksum,
                    size_bytes=document.size_bytes,
                    modified_at=document.modified_at.isoformat() if document.modified_at else None,
                    last_status="failed",
                    last_error="upload failed; queued for retry",
                )
        summary.failed_uploads = max(summary.failed_uploads, store.failed_upload_queue_depth(source_name))
        summary.checkpoint_updated = bool(synced_documents or summary.retry_succeeded)
        if summary.checkpoint_updated:
            store.save_source_checkpoint(
                source_name,
                {
                    "path": str(path),
                    "files_seen": summary.files_seen,
                    "documents_synced": summary.documents_synced,
                    "failed_uploads": summary.failed_uploads,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        summary.duration_ms = int((monotonic() - start) * 1000)
        store.record_sync_run(summary, status="completed")
        record_audit_event(
            settings.state.sqlite_path.parent,
            "sync",
            {
                "source_name": source_name,
                "path": str(path),
                "export_target": export_target,
                "files_seen": summary.files_seen,
                "documents_synced": summary.documents_synced,
            },
        )
        return summary
    except Exception as exc:
        summary.errors.append(str(exc))
        summary.duration_ms = int((monotonic() - start) * 1000)
        store.record_sync_run(summary, status="failed")
        raise
    finally:
        if exporter and hasattr(exporter, "client"):
            exporter.client.close()
        store.close()
