from __future__ import annotations

from pathlib import Path

from opsincident_collector.receivers import api_docs, deploy_history, git_local, incidents, logs_folder, runbooks


def extract_receiver_metadata(
    source_type: str,
    detected_type: str,
    path: Path,
    relative_path: str,
    text: str,
) -> dict[str, object]:
    semantic_path = Path(relative_path)
    kind = source_type if source_type != "filesystem" else detected_type
    if kind == "logs":
        return logs_folder.extract_metadata(semantic_path, text)
    if kind == "logs_folder":
        return logs_folder.extract_metadata(semantic_path, text)
    if kind == "git_local":
        return git_local.extract_metadata(path, text)
    if kind == "code":
        return git_local.extract_metadata(path, text)
    if kind == "deploy_history":
        return deploy_history.extract_metadata(semantic_path, text)
    if kind == "runbook":
        return runbooks.extract_metadata(semantic_path, text)
    if kind == "runbooks":
        return runbooks.extract_metadata(semantic_path, text)
    if kind == "incident_report":
        return incidents.extract_metadata(semantic_path, text)
    if kind == "incidents":
        return incidents.extract_metadata(semantic_path, text)
    if kind == "api_doc":
        return api_docs.extract_metadata(semantic_path, text)
    if kind == "api_docs":
        return api_docs.extract_metadata(semantic_path, text)
    return {"source_kind": detected_type}
