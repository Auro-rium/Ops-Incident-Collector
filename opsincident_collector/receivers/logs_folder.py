from __future__ import annotations

import re
from pathlib import Path

from opsincident_collector.processors.metadata_extractor import (
    ENDPOINT_RE,
    LOG_LEVEL_RE,
    REQUEST_RE,
    TIMESTAMP_RE,
    TRACE_RE,
)


def extract_metadata(path: Path, text: str) -> dict[str, object]:
    timestamps = TIMESTAMP_RE.findall(text)
    endpoints = [f"{method} {route}" for method, route in ENDPOINT_RE.findall(text)]
    api_paths = re.findall(r"\b(/(?:api|v\d+)/[A-Za-z0-9_\-/.{}]*)", text)
    return {
        key: value
        for key, value in {
            "source_kind": "logs",
            "timestamp_start": timestamps[0] if timestamps else None,
            "timestamp_end": timestamps[-1] if timestamps else None,
            "log_level_counts": {
                level: len(re.findall(rf"\b{level}\b", text)) for level in sorted(set(LOG_LEVEL_RE.findall(text)))
            },
            "trace_ids": sorted(set(TRACE_RE.findall(text)))[:20],
            "request_ids": sorted(set(REQUEST_RE.findall(text)))[:20],
            "endpoints": sorted(set([*endpoints, *api_paths]))[:50],
        }.items()
        if value not in (None, [], {}, "")
    }
