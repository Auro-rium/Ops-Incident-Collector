from __future__ import annotations

from typing import Any

from opsincident_collector.core.models import NormalizedDocument

CORE_SOURCE_TYPE_ALIASES = {
    "filesystem": None,
    "logs_folder": "logs",
    "git_local": "code",
    "deploy_history": "deploy",
    "incident_report": "incident",
    "incidents": "incident",
    "runbooks": "runbook",
    "patch": "deploy",
}

CORE_KNOWN_SOURCE_TYPES = {
    "logs",
    "code",
    "deploy",
    "incident",
    "runbook",
    "api_doc",
    "config",
    "unknown_text",
}


def normalize_core_source_type(document: NormalizedDocument) -> str:
    candidates = [document.content_type, document.source_type]
    for candidate in candidates:
        if not candidate:
            continue
        value = candidate.strip().lower()
        value = CORE_SOURCE_TYPE_ALIASES.get(value, value)
        if value in CORE_KNOWN_SOURCE_TYPES:
            return value
    return "unknown_text"


def to_core_document_payload(document: NormalizedDocument) -> dict[str, Any]:
    path = document.relative_path or document.path
    return {
        "external_id": document.external_id,
        "path": path,
        "source_type": normalize_core_source_type(document),
        "content": document.content,
        "content_hash": document.checksum,
        "metadata": document.metadata,
        "size_bytes": document.size_bytes,
        "modified_at": document.modified_at.isoformat() if document.modified_at else None,
    }
