from __future__ import annotations

import sqlite3


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            source_name TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            checksum TEXT,
            size_bytes INTEGER,
            modified_at TEXT,
            last_synced_at TEXT,
            last_status TEXT,
            last_error TEXT,
            UNIQUE(source_name, relative_path)
        );

        CREATE TABLE IF NOT EXISTS sync_runs (
            sync_id TEXT PRIMARY KEY,
            source_name TEXT,
            project_id TEXT,
            export_target TEXT,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            files_seen INTEGER,
            files_uploaded INTEGER,
            files_skipped INTEGER,
            documents_synced INTEGER,
            bytes_processed INTEGER,
            bytes_uploaded INTEGER,
            warnings_json TEXT,
            errors_json TEXT
        );

        CREATE TABLE IF NOT EXISTS failed_uploads (
            id INTEGER PRIMARY KEY,
            sync_id TEXT,
            source_name TEXT,
            path TEXT,
            document_external_id TEXT,
            payload_json TEXT,
            reason TEXT,
            retry_count INTEGER,
            next_retry_at TEXT,
            last_error TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS source_checkpoints (
            source_name TEXT PRIMARY KEY,
            checkpoint_json TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS normalized_documents (
            document_id TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            external_id TEXT NOT NULL,
            path TEXT NOT NULL,
            relative_path TEXT,
            content TEXT NOT NULL,
            content_type TEXT NOT NULL,
            checksum TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            modified_at TEXT,
            discovered_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            redaction_json TEXT NOT NULL
        );
        """
    )
    _ensure_columns(
        conn,
        "failed_uploads",
        {
            "source_name": "TEXT",
            "document_external_id": "TEXT",
            "payload_json": "TEXT",
            "next_retry_at": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        },
    )
    conn.commit()
