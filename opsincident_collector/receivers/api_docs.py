from __future__ import annotations

import json
import re
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


def extract_metadata(_path: Path, text: str) -> dict[str, object]:
    data = _load_structured(text)
    endpoints: list[str] = []
    if isinstance(data, dict) and isinstance(data.get("paths"), dict):
        endpoints = sorted(str(path) for path in data["paths"].keys())[:100]
    if not endpoints:
        endpoints = sorted(set(re.findall(r"^\s{0,8}(/[A-Za-z0-9_\-/.{}]+):", text, re.MULTILINE)))[:100]
    has_openapi = "openapi" in text.lower() or "swagger" in text.lower()
    return {
        key: value
        for key, value in {
            "source_kind": "api_doc",
            "api_doc_format": "openapi_or_swagger" if has_openapi else None,
            "endpoints": endpoints,
        }.items()
        if value not in (None, [], {}, "")
    }
