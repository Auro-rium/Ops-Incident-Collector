from __future__ import annotations

import re
from pathlib import Path

HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


def extract_metadata(path: Path, text: str) -> dict[str, object]:
    headings = [heading.strip() for heading in HEADING_RE.findall(text)]
    service_name = None
    for heading in headings:
        if heading.lower().startswith(("service:", "service ")):
            service_name = heading.split(":", 1)[-1].strip()
            break
    return {
        key: value
        for key, value in {
            "source_kind": "runbook",
            "headings": headings[:30],
            "service_name": service_name,
            "failure_mode": path.stem.replace("-", " ").replace("_", " "),
        }.items()
        if value not in (None, [], {}, "")
    }
