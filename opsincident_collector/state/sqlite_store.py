from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from opsincident_collector.core.models import NormalizedDocument, SyncSummary
from opsincident_collector.state.migrations import run_migrations


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        run_migrations(self.conn)

    def close(self) -> None:
        self.conn.close()

    def get_file_record(self, source_name: str, relative_path: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM files WHERE source_name = ? AND relative_path = ?",
            (source_name, relative_path),
        ).fetchone()
        return dict(row) if row else None

    def upsert_file_record(
        self,
        source_name: str,
        path: str,
        relative_path: str,
        checksum: str,
        size_bytes: int,
        modified_at: str | None,
        last_status: str,
        last_error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO files (
                source_name, path, relative_path, checksum, size_bytes, modified_at,
                last_synced_at, last_status, last_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_name, relative_path) DO UPDATE SET
                path = excluded.path,
                checksum = excluded.checksum,
                size_bytes = excluded.size_bytes,
                modified_at = excluded.modified_at,
                last_synced_at = excluded.last_synced_at,
                last_status = excluded.last_status,
                last_error = excluded.last_error
            """,
            (
                source_name,
                path,
                relative_path,
                checksum,
                size_bytes,
                modified_at,
                now,
                last_status,
                last_error,
            ),
        )
        self.conn.commit()

    def save_source_checkpoint(self, source_name: str, checkpoint: dict[str, Any]) -> None:
        self.conn.execute(
            """
            INSERT INTO source_checkpoints (source_name, checkpoint_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(source_name) DO UPDATE SET
                checkpoint_json = excluded.checkpoint_json,
                updated_at = excluded.updated_at
            """,
            (source_name, json.dumps(checkpoint), datetime.now(timezone.utc).isoformat()),
        )
        self.conn.commit()

    def get_source_checkpoint(self, source_name: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT checkpoint_json FROM source_checkpoints WHERE source_name = ?",
            (source_name,),
        ).fetchone()
        return json.loads(row["checkpoint_json"]) if row else None

    def record_sync_run(self, summary: SyncSummary, status: str) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO sync_runs (
                sync_id, source_name, project_id, export_target, status,
                started_at, finished_at, files_seen, files_uploaded, files_skipped,
                documents_synced, bytes_processed, bytes_uploaded, warnings_json, errors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.sync_id,
                summary.source_name or summary.source_id,
                summary.project_id,
                summary.export_target,
                status,
                None,
                datetime.now(timezone.utc).isoformat(),
                summary.files_seen,
                summary.files_uploaded,
                summary.files_skipped,
                summary.documents_synced,
                summary.bytes_processed,
                summary.bytes_uploaded,
                json.dumps(summary.warnings),
                json.dumps(summary.errors),
            ),
        )
        self.conn.commit()

    def record_failed_upload(
        self,
        sync_id: str,
        source_name: str,
        path: str,
        document_external_id: str,
        payload_json: str,
        reason: str,
        last_error: str,
        retry_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        existing = self.conn.execute(
            """
            SELECT id FROM failed_uploads
            WHERE source_name = ? AND document_external_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (source_name, document_external_id),
        ).fetchone()
        if existing:
            self.conn.execute(
                """
                UPDATE failed_uploads
                SET sync_id = ?, path = ?, payload_json = ?, reason = ?, retry_count = ?,
                    next_retry_at = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    sync_id,
                    path,
                    payload_json,
                    reason,
                    retry_count,
                    now,
                    last_error,
                    now,
                    existing["id"],
                ),
            )
            self.conn.commit()
            return

        self.conn.execute(
            """
            INSERT INTO failed_uploads (
                sync_id, source_name, path, document_external_id, payload_json, reason,
                retry_count, next_retry_at, last_error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sync_id,
                source_name,
                path,
                document_external_id,
                payload_json,
                reason,
                retry_count,
                now,
                last_error,
                now,
                now,
            ),
        )
        self.conn.commit()

    def get_due_failed_uploads(self, source_name: str, max_retry_count: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        rows = self.conn.execute(
            """
            SELECT * FROM failed_uploads
            WHERE source_name = ?
              AND payload_json IS NOT NULL
              AND retry_count < ?
              AND (next_retry_at IS NULL OR next_retry_at <= ?)
            ORDER BY created_at ASC, id ASC
            """,
            (source_name, max_retry_count, now),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_failed_upload_retry(
        self,
        failed_upload_id: int,
        last_error: str,
        retry_backoff_seconds: int,
        max_retry_count: int,
    ) -> None:
        row = self.conn.execute(
            "SELECT retry_count FROM failed_uploads WHERE id = ?",
            (failed_upload_id,),
        ).fetchone()
        if not row:
            return
        retry_count = min(int(row["retry_count"] or 0) + 1, max_retry_count)
        delay = retry_backoff_seconds * (2 ** max(retry_count - 1, 0))
        next_retry_at = (
            datetime.now(timezone.utc) + timedelta(seconds=max(delay, 0))
        ).isoformat()
        self.conn.execute(
            """
            UPDATE failed_uploads
            SET retry_count = ?, next_retry_at = ?, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                retry_count,
                next_retry_at,
                last_error,
                datetime.now(timezone.utc).isoformat(),
                failed_upload_id,
            ),
        )
        self.conn.commit()

    def mark_failed_upload_non_retryable(
        self,
        failed_upload_id: int,
        last_error: str,
        max_retry_count: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE failed_uploads
            SET retry_count = ?, reason = ?, next_retry_at = NULL, last_error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                max_retry_count,
                "non_retryable_upload_error",
                last_error,
                datetime.now(timezone.utc).isoformat(),
                failed_upload_id,
            ),
        )
        self.conn.commit()

    def delete_failed_upload(self, failed_upload_id: int) -> None:
        self.conn.execute("DELETE FROM failed_uploads WHERE id = ?", (failed_upload_id,))
        self.conn.commit()

    def failed_upload_queue_depth(self, source_name: str | None = None) -> int:
        if source_name:
            row = self.conn.execute(
                "SELECT COUNT(*) AS count FROM failed_uploads WHERE source_name = ?",
                (source_name,),
            ).fetchone()
        else:
            row = self.conn.execute("SELECT COUNT(*) AS count FROM failed_uploads").fetchone()
        return int(row["count"] if row else 0)

    def list_failed_uploads(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM failed_uploads ORDER BY id ASC").fetchall()
        return [dict(row) for row in rows]

    def save_normalized_document(self, document: NormalizedDocument) -> None:
        document_id = document.document_id or document.external_id
        self.conn.execute(
            """
            INSERT OR REPLACE INTO normalized_documents (
                document_id, source_name, source_type, external_id, path, relative_path,
                content, content_type, checksum, size_bytes, modified_at, discovered_at,
                metadata_json, redaction_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                document.source_name,
                document.source_type,
                document.external_id,
                document.path,
                document.relative_path,
                document.content,
                document.content_type,
                document.checksum,
                document.size_bytes,
                document.modified_at.isoformat() if document.modified_at else None,
                document.discovered_at.isoformat(),
                json.dumps(document.metadata),
                document.redaction.model_dump_json(),
            ),
        )
        self.conn.commit()

    def get_last_sync_summary(self) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM sync_runs ORDER BY finished_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
