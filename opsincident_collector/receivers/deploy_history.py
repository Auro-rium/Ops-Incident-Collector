from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def _load_structured(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError:
            return None


def _find_value(data: Any, keys: set[str]) -> Any:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys:
                return value
        for value in data.values():
            found = _find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _find_value(item, keys)
            if found is not None:
                return found
    return None


def extract_metadata(_path: Path, text: str) -> dict[str, object]:
    data = _load_structured(text)
    return {
        key: value
        for key, value in {
            "source_kind": "deploy_history",
            "deploy_hash": _find_value(data, {"deploy_hash", "deploy_id", "version", "release"}),
            "commit_sha": _find_value(data, {"commit_sha", "commit", "sha"}),
            "service_name": _find_value(data, {"service", "service_name", "app"}),
            "environment": _find_value(data, {"environment", "env"}),
            "deployed_at": _find_value(data, {"deployed_at", "timestamp", "time"}),
            "author": _find_value(data, {"author", "deployer", "deployed_by"}),
        }.items()
        if value not in (None, [], {}, "")
    }
