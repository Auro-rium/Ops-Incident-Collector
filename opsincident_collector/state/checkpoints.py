from __future__ import annotations

from dataclasses import dataclass

from opsincident_collector.core.checksums import sha256_file
from opsincident_collector.core.models import SourceItem
from opsincident_collector.state.sqlite_store import SQLiteStore


@dataclass
class CheckpointDecision:
    should_process: bool
    checksum: str | None
    reason: str


def should_process_item(store: SQLiteStore, source_name: str, item: SourceItem) -> CheckpointDecision:
    record = store.get_file_record(source_name, item.relative_path)
    modified_at = item.modified_at.isoformat() if item.modified_at else None
    if not record:
        checksum = sha256_file(item.path)
        return CheckpointDecision(True, checksum, "new_file")

    if record["size_bytes"] == item.size_bytes and record["modified_at"] == modified_at:
        return CheckpointDecision(False, None, "mtime_size_unchanged")

    checksum = sha256_file(item.path)
    if record["checksum"] == checksum:
        return CheckpointDecision(False, checksum, "checksum_unchanged")
    return CheckpointDecision(True, checksum, "changed")
