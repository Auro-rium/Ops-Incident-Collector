from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

from opsincident_collector.adapters.core_capabilities import supports_feature
from opsincident_collector.adapters.core_client import (
    CoreClient,
    MissingBatchEndpointError,
    is_retryable_api_error,
)
from opsincident_collector.core.core_payload import to_core_document_payload
from opsincident_collector.core.models import NormalizedDocument, SyncSummary
from opsincident_collector.core.protocol import collector_version
from opsincident_collector.processors.batcher import batch_items

if TYPE_CHECKING:
    from opsincident_collector.state.sqlite_store import SQLiteStore


class IncidentOpsAPIExporter:
    def __init__(
        self,
        client: CoreClient,
        project_id: str,
        collector_name: str,
        collector_environment: str,
        source_name: str,
        source_type: str,
        batch_size: int = 50,
        store: "SQLiteStore | None" = None,
        retry_count: int = 3,
        retry_backoff_seconds: int = 5,
    ):
        self.client = client
        self.project_id = project_id
        self.collector_name = collector_name
        self.collector_environment = collector_environment
        self.source_name = source_name
        self.source_type = source_type
        self.batch_size = batch_size
        self.store = store
        self.retry_count = retry_count
        self.retry_backoff_seconds = retry_backoff_seconds
        self.failed_external_ids: set[str] = set()
        self.collector_id: str | None = None

    def export_documents(self, documents: list[NormalizedDocument], summary: SyncSummary) -> int:
        capabilities = self.client.capabilities()
        if capabilities and capabilities.limits.get("max_batch_size"):
            self.batch_size = min(self.batch_size, capabilities.limits["max_batch_size"])
        collector = self.client.register_collector(
            project_id=self.project_id,
            payload={
                "name": self.collector_name,
                "environment": self.collector_environment,
                "version": collector_version(),
            },
            capabilities=capabilities,
        )
        self.collector_id = (
            collector.get("collector_id")
            or collector.get("id")
            or collector.get("uuid")
            or self.collector_name
        )
        summary.collector_id = self.collector_id
        source = self.client.register_source(
            project_id=self.project_id,
            payload={"name": self.source_name, "source_type": self.source_type, "type": self.source_type},
            capabilities=capabilities,
        )
        summary.source_id = source.source_id
        remote_sync_id = summary.sync_id
        uploaded_bytes = 0
        sync_started = False
        try:
            if _supports_sync_lifecycle(capabilities):
                sync_response = self.client.create_sync(
                    source_id=source.source_id,
                    payload={
                        "sync_id": summary.sync_id,
                        "status": "started",
                        "project_id": self.project_id,
                        "collector_id": self.collector_id,
                        "diagnostics": _sync_diagnostics(summary, documents),
                    },
                    capabilities=capabilities,
                )
                sync_started = True
                remote_sync_id = sync_response.get("sync_id", summary.sync_id)

            uploaded_bytes += self._retry_due_uploads(summary, capabilities, remote_sync_id)

            for batch in batch_items(documents, self.batch_size):
                payload = [to_core_document_payload(document) for document in batch]
                try:
                    self.client.batch_upload_documents(
                        project_id=self.project_id,
                        source_id=source.source_id,
                        documents=payload,
                        sync_id=remote_sync_id,
                        collector_id=self.collector_id,
                        capabilities=capabilities,
                    )
                    uploaded_bytes += sum(document.size_bytes for document in batch)
                except MissingBatchEndpointError:
                    raise
                except Exception as exc:
                    retryable = is_retryable_api_error(exc)
                    summary.failed_uploads += len(batch)
                    summary.warnings.append(
                        f"queued {len(batch)} failed upload(s)"
                        if retryable
                        else f"recorded {len(batch)} non-retryable upload failure(s)"
                    )
                    self._record_failed_batch(summary.sync_id, batch, exc, retryable)
            if _supports_sync_lifecycle(capabilities):
                self.client.update_sync(
                    source_id=source.source_id,
                    sync_id=remote_sync_id,
                    payload={
                        "status": _core_finish_status(summary.failed_uploads),
                        "documents_synced": len(documents) - len(self.failed_external_ids),
                        "failed_uploads": summary.failed_uploads,
                        "collector_id": self.collector_id,
                        "diagnostics": _sync_diagnostics(
                            summary,
                            documents,
                            failed_external_ids=self.failed_external_ids,
                        ),
                    },
                    capabilities=capabilities,
                )
        except Exception:
            if sync_started and _supports_sync_lifecycle(capabilities):
                try:
                    self.client.update_sync(
                        source_id=source.source_id,
                        sync_id=remote_sync_id,
                        payload={
                            "status": "failed",
                            "failed_uploads": summary.failed_uploads,
                            "collector_id": self.collector_id,
                            "diagnostics": _sync_diagnostics(
                                summary,
                                documents,
                                failed_external_ids=self.failed_external_ids,
                            ),
                        },
                        capabilities=capabilities,
                    )
                except Exception:
                    pass
            raise
        return uploaded_bytes

    def _record_failed_batch(
        self,
        sync_id: str,
        batch: list[NormalizedDocument],
        exc: Exception,
        retryable: bool,
    ) -> None:
        for document in batch:
            self.failed_external_ids.add(document.external_id)
            if not self.store:
                continue
            self.store.record_failed_upload(
                sync_id=sync_id,
                source_name=self.source_name,
                path=document.path,
                document_external_id=document.external_id,
                payload_json=json.dumps(to_core_document_payload(document)),
                reason="retryable_upload_error" if retryable else "non_retryable_upload_error",
                last_error=str(exc),
                retry_count=0 if retryable else self.retry_count,
            )

    def _retry_due_uploads(self, summary: SyncSummary, capabilities, sync_id: str) -> int:
        if not self.store:
            return 0
        uploaded_bytes = 0
        rows = self.store.get_due_failed_uploads(self.source_name, self.retry_count)
        for row in rows:
            summary.retry_attempted += 1
            payload = json.loads(row["payload_json"])
            try:
                self.client.batch_upload_documents(
                    project_id=self.project_id,
                    source_id=summary.source_id or self.source_name,
                    documents=[payload],
                    sync_id=sync_id,
                    collector_id=self.collector_id,
                    capabilities=capabilities,
                )
            except Exception as exc:
                if is_retryable_api_error(exc):
                    self.store.update_failed_upload_retry(
                        failed_upload_id=row["id"],
                        last_error=str(exc),
                        retry_backoff_seconds=self.retry_backoff_seconds,
                        max_retry_count=self.retry_count,
                    )
                else:
                    self.store.mark_failed_upload_non_retryable(
                        failed_upload_id=row["id"],
                        last_error=str(exc),
                        max_retry_count=self.retry_count,
                    )
                summary.failed_uploads += 1
                continue

            self.store.delete_failed_upload(row["id"])
            self.store.upsert_file_record(
                source_name=self.source_name,
                path=payload.get("path") or row["path"],
                relative_path=payload.get("relative_path") or payload.get("path") or row["path"],
                checksum=payload.get("checksum") or payload.get("content_hash") or "",
                size_bytes=int(payload.get("size_bytes") or 0),
                modified_at=payload.get("modified_at"),
                last_status="synced",
            )
            summary.retry_succeeded += 1
            uploaded_bytes += int(payload.get("size_bytes") or 0)
        return uploaded_bytes


def _core_finish_status(failed_uploads: int, cancelled: bool = False) -> str:
    if cancelled:
        return "cancelled"
    if failed_uploads > 0:
        return "partial_success"
    return "success"


def _supports_sync_lifecycle(capabilities) -> bool:
    return (
        capabilities is None
        or supports_feature(capabilities, "sync_tracking")
        or supports_feature(capabilities, "sync_lifecycle")
    )


def _sync_diagnostics(
    summary: SyncSummary,
    documents: list[NormalizedDocument],
    failed_external_ids: set[str] | None = None,
) -> dict:
    source_type_counts = Counter(document.content_type or document.source_type for document in documents)
    documents_synced = max(len(documents) - len(failed_external_ids or set()), 0)
    documents_synced += summary.retry_succeeded
    return {
        "total_files_seen": summary.files_seen,
        "files_seen": summary.files_seen,
        "files_skipped": summary.files_skipped,
        "skipped_reasons": dict(sorted(summary.skipped_reasons.items())),
        "unsupported_extensions": dict(sorted(summary.unsupported_extensions.items())),
        "documents_normalized": summary.documents_normalized,
        "documents_synced": documents_synced,
        "failed_uploads": summary.failed_uploads,
        "retry_attempted": summary.retry_attempted,
        "retry_succeeded": summary.retry_succeeded,
        "redaction_count": summary.redaction_count,
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "warnings": list(summary.warnings),
    }
