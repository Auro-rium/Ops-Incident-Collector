from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def record_audit_event(base_dir: Path, event_type: str, payload: dict[str, Any]) -> None:
    audit_path = base_dir / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
