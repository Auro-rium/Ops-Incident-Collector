from __future__ import annotations

import re
from pathlib import Path

TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:\.\-+Z]+\b")
COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
TRACE_RE = re.compile(r"\btrace[_-]?id[=: ]([A-Za-z0-9_-]+)\b", re.IGNORECASE)
REQUEST_RE = re.compile(r"\brequest[_-]?id[=: ]([A-Za-z0-9_-]+)\b", re.IGNORECASE)
LOG_LEVEL_RE = re.compile(r"\b(INFO|WARN|WARNING|ERROR|DEBUG|CRITICAL)\b")
ENDPOINT_RE = re.compile(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_\-/.{}]+)")
API_PATH_RE = re.compile(r"\b(/(?:api|v\d+)/[A-Za-z0-9_\-/.{}]*)")
SERVICE_RE = re.compile(r"\bservice[=: ]([A-Za-z0-9._-]+)\b", re.IGNORECASE)
TITLE_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.+)$", re.MULTILINE)
SEVERITY_RE = re.compile(r"\bseverity[=: ](sev[0-5]|critical|high|medium|low)\b", re.IGNORECASE)
CONFIG_KEY_RE = re.compile(r"^\s*([A-Za-z0-9_.-]{2,64})\s*[:=]", re.MULTILINE)


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
    api_paths = API_PATH_RE.findall(text)
    timestamps = TIMESTAMP_RE.findall(text)
    commit_matches = sorted(set(COMMIT_RE.findall(text)))[:20]
    headings = [heading.strip() for heading in HEADING_RE.findall(text)][:50]
    title_match = TITLE_RE.search(text)
    severity_match = SEVERITY_RE.search(text)
    config_keys = sorted(set(CONFIG_KEY_RE.findall(text)))[:50]
    metadata: dict[str, object] = {
        "service_name": _infer_service_name(path, text),
        "environment": "prod" if "prod" in lowered else "dev" if "dev" in lowered else None,
        "endpoint": endpoints[0] if endpoints else None,
        "endpoint_candidates": sorted(set([*endpoints, *api_paths]))[:50],
        "api_paths": sorted(set(api_paths))[:50],
        "deploy_hash": commit_matches[0] if commit_matches and "deploy" in lowered else None,
        "deploy_hashes": commit_matches if "deploy" in lowered else [],
        "commit_sha": commit_matches[0] if commit_matches else None,
        "commit_shas": commit_matches,
        "timestamp_start": timestamps[0] if timestamps else None,
        "timestamp_end": timestamps[-1] if len(timestamps) > 1 else (timestamps[0] if timestamps else None),
        "log_levels": sorted(set(LOG_LEVEL_RE.findall(text))),
        "trace_ids": sorted(set(TRACE_RE.findall(text)))[:20],
        "request_ids": sorted(set(REQUEST_RE.findall(text)))[:20],
        "file_language": path.suffix.lstrip(".") or None,
        "language": path.suffix.lstrip(".") or None,
        "possible_incident_date": timestamps[0][:10] if timestamps else None,
        "incident_date": timestamps[0][:10] if detected_type == "incident_report" and timestamps else None,
        "severity": severity_match.group(1).lower() if severity_match else None,
        "title": title_match.group(1).strip() if title_match else None,
        "headings": headings,
        "config_keys_summary": config_keys if detected_type == "config" else [],
        "source_kind": detected_type,
    }
    return {key: value for key, value in metadata.items() if value not in (None, [], "")}
