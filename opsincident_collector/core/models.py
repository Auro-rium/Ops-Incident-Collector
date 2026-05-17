from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version


class RedactionSummary(BaseModel):
    enabled: bool = False
    redacted_count: int = 0
    patterns_matched: list[str] = Field(default_factory=list)
    had_possible_secret: bool = False


class SkippedFile(BaseModel):
    path: str
    reason: str
    size_bytes: int | None = None


class SourceInspection(BaseModel):
    path: str
    total_files: int = 0
    supported_files: int = 0
    unsupported_files: int = 0
    oversized_files: int = 0
    denied_files: int = 0
    empty_files: int = 0
    likely_source_types: dict[str, int] = Field(default_factory=dict)
    supported_extensions: dict[str, int] = Field(default_factory=dict)
    unsupported_extensions: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)
    possible_secrets_detected: int = 0
    binary_files: int = 0


class SyncSummary(BaseModel):
    sync_id: str
    source_name: str | None = None
    source_id: str | None = None
    project_id: str | None = None
    export_target: str
    files_seen: int = 0
    files_uploaded: int = 0
    files_skipped: int = 0
    documents_synced: int = 0
    bytes_processed: int = 0
    bytes_uploaded: int = 0
    duration_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    checkpoint_updated: bool = False
    failed_uploads: int = 0
    retry_attempted: int = 0
    retry_succeeded: int = 0


class SourceItem(BaseModel):
    path: Path
    relative_path: str
    size_bytes: int
    modified_at: datetime | None = None
    extension: str
    detected_type: str | None = None


class RawDocument(BaseModel):
    source_item: SourceItem
    content: str
    encoding: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class NormalizedDocument(BaseModel):
    document_id: str | None = None
    source_name: str
    source_type: str
    external_id: str
    path: str
    relative_path: str | None = None
    content: str
    content_type: str
    checksum: str
    size_bytes: int
    modified_at: datetime | None = None
    discovered_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    redaction: RedactionSummary = Field(default_factory=RedactionSummary)


class NormalizedDocumentEnvelope(BaseModel):
    collector_version: str = Field(default_factory=collector_version)
    schema_version: str = SCHEMA_VERSION
    core_api_version: str | None = CORE_API_VERSION
    document: NormalizedDocument
