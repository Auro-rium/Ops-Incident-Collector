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
ERROR_CODE_RE = re.compile(r"\b([A-Z]{2,}[A-Z0-9_-]{1,32}|E\d{3,5}|ERR_[A-Z0-9_]+)\b")
PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z0-9_.]+)\s*;?\s*$", re.MULTILINE)
PY_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
PY_CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_]\w*)", re.MULTILINE)
JS_DEF_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(|^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\(", re.MULTILINE)
JS_CLASS_RE = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_]\w*)", re.MULTILINE)
JAVA_METHOD_RE = re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract)\s+)+(?:[A-Za-z_][\w<>, \[\]]+)\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
JAVA_CLASS_RE = re.compile(r"^\s*(?:public\s+)?(?:class|interface|enum|record)\s+([A-Za-z_]\w*)", re.MULTILINE)
GO_FUNC_RE = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", re.MULTILINE)
GO_TYPE_RE = re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+", re.MULTILINE)
PROTO_SERVICE_RE = re.compile(r"^\s*service\s+([A-Za-z_]\w*)\s*\{?", re.MULTILINE)
PROTO_MESSAGE_RE = re.compile(r"^\s*message\s+([A-Za-z_]\w*)\s*\{?", re.MULTILINE)
RELEASE_RE = re.compile(r"\b(release[-_ ]?\d[\w.-]*|v\d+\.\d+(?:\.\d+)?)\b", re.IGNORECASE)


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
    function_names, class_names = _extract_symbols(path, text)
    package_path = _extract_package_path(text)
    module_path = path.as_posix().rsplit(".", 1)[0]
    release_markers = sorted(set(RELEASE_RE.findall(text)))[:20]
    error_codes = sorted(set(ERROR_CODE_RE.findall(text)))[:20]
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
        "module_path": module_path,
        "package_path": package_path,
        "function_names": function_names,
        "class_names": class_names,
        "symbol_names": sorted(set([*function_names, *class_names]))[:100],
        "possible_incident_date": timestamps[0][:10] if timestamps else None,
        "incident_date": timestamps[0][:10] if detected_type == "incident_report" and timestamps else None,
        "severity": severity_match.group(1).lower() if severity_match else None,
        "title": title_match.group(1).strip() if title_match else None,
        "headings": headings,
        "config_keys_summary": config_keys if detected_type == "config" else [],
        "error_codes": error_codes,
        "release_markers": release_markers,
        "source_kind": detected_type,
    }
    return {key: value for key, value in metadata.items() if value not in (None, [], "")}


def _extract_package_path(text: str) -> str | None:
    match = PACKAGE_RE.search(text)
    return match.group(1) if match else None


def _extract_symbols(path: Path, text: str) -> tuple[list[str], list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return sorted(set(PY_DEF_RE.findall(text)))[:100], sorted(set(PY_CLASS_RE.findall(text)))[:100]
    if suffix in {".js", ".ts", ".jsx", ".tsx"}:
        function_names = []
        for groups in JS_DEF_RE.findall(text):
            for name in groups:
                if name:
                    function_names.append(name)
        return sorted(set(function_names))[:100], sorted(set(JS_CLASS_RE.findall(text)))[:100]
    if suffix == ".java":
        return sorted(set(JAVA_METHOD_RE.findall(text)))[:100], sorted(set(JAVA_CLASS_RE.findall(text)))[:100]
    if suffix == ".go":
        return sorted(set(GO_FUNC_RE.findall(text)))[:100], sorted(set(GO_TYPE_RE.findall(text)))[:100]
    if suffix == ".proto":
        symbols = sorted(set([*PROTO_SERVICE_RE.findall(text), *PROTO_MESSAGE_RE.findall(text)]))[:100]
        return symbols, []
    return [], []
