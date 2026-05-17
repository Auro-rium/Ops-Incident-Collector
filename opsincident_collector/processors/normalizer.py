from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from opsincident_collector.core.checksums import sha256_file
from opsincident_collector.core.models import NormalizedDocument, RawDocument
from opsincident_collector.processors.content_classifier import classify_content
from opsincident_collector.processors.metadata_extractor import extract_metadata
from opsincident_collector.processors.secret_redactor import redact_text
from opsincident_collector.receivers import extract_receiver_metadata


def normalize_document(
    raw_document: RawDocument,
    source_name: str,
    source_type: str,
    redact_secrets: bool = True,
) -> NormalizedDocument:
    item = raw_document.source_item
    detected_type = item.detected_type or classify_content(
        item.path,
        item.extension,
        relative_path=item.relative_path,
        text=raw_document.content,
    )
    relative_path = item.relative_path or item.path.name
    base_metadata = extract_metadata(Path(relative_path), raw_document.content, detected_type)
    receiver_metadata = extract_receiver_metadata(
        source_type=source_type,
        detected_type=detected_type,
        path=item.path,
        relative_path=relative_path,
        text=raw_document.content,
    )
    metadata = raw_document.metadata | base_metadata | receiver_metadata
    content, redaction = redact_text(raw_document.content, enabled=redact_secrets)
    checksum = sha256_file(item.path)
    return NormalizedDocument(
        source_name=source_name,
        source_type=source_type,
        external_id=f"{source_name}:{item.relative_path}",
        path=str(item.path),
        relative_path=item.relative_path,
        content=content,
        content_type=detected_type,
        checksum=checksum,
        size_bytes=item.size_bytes,
        modified_at=item.modified_at,
        discovered_at=datetime.now(timezone.utc),
        metadata=metadata,
        redaction=redaction,
    )
