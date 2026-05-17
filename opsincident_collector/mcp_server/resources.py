from __future__ import annotations

from pathlib import Path

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.state.sqlite_store import SQLiteStore


def get_resource_map(config_path: Path | None = None) -> dict[str, object]:
    settings = load_settings_optional(config_path)
    store = SQLiteStore(settings.state.sqlite_path)
    last_sync = store.get_last_sync_summary()
    checkpoint = store.get_source_checkpoint("default")
    return {
        "incidentops://local/config": settings.model_dump(mode="json"),
        "incidentops://local/last-sync": last_sync,
        "incidentops://local/last-inspection": checkpoint,
        "incidentops://local/redaction-report": {
            "status": "available after sync",
        },
    }
