from __future__ import annotations

import re
from pathlib import Path

TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:\.\-+Z]+\b")
COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
TRACE_RE = re.compile(r"\btrace[_-]?id[=: ]([A-Za-z0-9_-]+)\b", re.IGNORECASE)
REQUEST_RE = re.compile(r"\brequest[_-]?id[=: ]([A-Za-z0-9_-]+)\b", re.IGNORECASE)
LOG_LEVEL_RE = re.compile(r"\b(INFO|WARN|WARNING|ERROR|DEBUG|CRITICAL)\b")
ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_\-/.{}]+)")
SERVICE_RE = re.compile(r"\bservice[=: ]([A-Za-z0-9._-]+)\b", re.IGNORECASE)


def _infer_service_name(path: Path, text: str) -> str | None:
    match = SERVICE_RE.search(text)
    if match:
        return match.group(1)
    parts = path.parts
    if "services" in parts:
        idx = parts.index("services")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if path.parent.name and path.parent.name not in {"src", "logs", "deploys", "incidents", "runbooks"}:
        return path.parent.name
    return path.stem if path.stem not in {"README", "openapi", "swagger"} else None


def extract_metadata(path: Path, text: str, detected_type: str | None = None) -> dict[str, object]:
    lowered = path.as_posix().lower()
    endpoints = [f"{method} {route}" for method, route in ENDPOINT_RE.findall(text)]
    timestamps = TIMESTAMP_RE.findall(text)
    commit_match = COMMIT_RE.search(text)
    metadata: dict[str, object] = {
        "service_name": _infer_service_name(path, text),
        "environment": "prod" if "prod" in lowered else "dev" if "dev" in lowered else None,
        "endpoint": endpoints[0] if endpoints else None,
        "deploy_hash": commit_match.group(0) if commit_match and "deploy" in lowered else None,
        "commit_sha": commit_match.group(0) if commit_match else None,
        "timestamp_start": timestamps[0] if timestamps else None,
        "timestamp_end": timestamps[-1] if len(timestamps) > 1 else (timestamps[0] if timestamps else None),
        "log_levels": sorted(set(LOG_LEVEL_RE.findall(text))),
        "trace_ids": sorted(set(TRACE_RE.findall(text)))[:20],
        "request_ids": sorted(set(REQUEST_RE.findall(text)))[:20],
        "file_language": path.suffix.lstrip(".") or None,
        "possible_incident_date": timestamps[0][:10] if timestamps else None,
        "source_kind": detected_type,
    }
    return {key: value for key, value in metadata.items() if value not in (None, [], "")}
