from __future__ import annotations

import re
from pathlib import Path

HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
DATE_RE = re.compile(r"\b(20\d{2}[-_/]\d{2}[-_/]\d{2})\b")


def extract_metadata(path: Path, text: str) -> dict[str, object]:
    headings = [heading.strip() for heading in HEADING_RE.findall(text)]
    lowered_headings = {heading.lower() for heading in headings}
    date_match = DATE_RE.search(path.as_posix()) or DATE_RE.search(text)
    return {
        key: value
        for key, value in {
            "source_kind": "incident_report",
            "incident_date": date_match.group(1).replace("_", "-").replace("/", "-") if date_match else None,
            "headings": headings[:30],
            "has_summary": "summary" in lowered_headings,
            "has_timeline": "timeline" in lowered_headings,
            "has_root_cause": "root cause" in lowered_headings,
            "has_resolution": "resolution" in lowered_headings,
        }.items()
        if value not in (None, [], {}, "")
    }
