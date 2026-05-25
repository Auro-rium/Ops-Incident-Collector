from __future__ import annotations

import re
from pathlib import Path


def classify_content(
    path: Path,
    extension: str,
    relative_path: str | None = None,
    text: str | None = None,
) -> str:
    semantic_path = (relative_path or path.name).lower()
    absolute_path = path.as_posix().lower()
    name = Path(relative_path or path.name).name.lower()
    content = (text or "")[:20000].lower()

    if extension in {".py", ".js", ".ts", ".go", ".java", ".rs"}:
        return "code"
    if extension == ".proto":
        return "api_doc"
    if extension in {".patch", ".diff"}:
        return "patch"
    if extension == ".log" or any(token in semantic_path for token in ("logs/", "/logs")):
        return "logs"
    if "deploy" in semantic_path or "deploy-history" in name:
        return "deploy_history"
    if "openapi" in name or "swagger" in name or re.search(r"(^|\n)\s*(openapi|swagger)\s*:", content):
        return "api_doc"
    if "runbook" in semantic_path or "operations" in semantic_path:
        return "runbook"
    if (
        "incident" in semantic_path
        or "postmortem" in semantic_path
        or "outage" in semantic_path
        or re.search(r"(^|\n)#+\s*(summary|timeline|root cause|resolution)\b", content)
    ):
        return "incident_report"
    if any(signal in content for signal in (" trace_id", " request_id", " error ", " warn ", " info ")):
        return "logs"
    if "docs/" in semantic_path or "/docs" in semantic_path:
        return "runbook"
    if extension in {".toml", ".ini", ".yaml", ".yml", ".json"}:
        return "config"
    if not relative_path and any(token in absolute_path for token in ("incident", "postmortem", "outage")):
        return "incident_report"
    return "unknown_text"
