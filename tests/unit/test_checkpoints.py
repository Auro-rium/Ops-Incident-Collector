from datetime import datetime
from pathlib import Path

from opsincident_collector.core.models import SourceItem
from opsincident_collector.state.checkpoints import should_process_item
from opsincident_collector.state.sqlite_store import SQLiteStore


def test_checkpoint_skips_unchanged_file(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    store = SQLiteStore(db_path)
    file_path = tmp_path / "doc.md"
    file_path.write_text("hello", encoding="utf-8")
    item = SourceItem(
        path=file_path,
        relative_path="doc.md",
        size_bytes=file_path.stat().st_size,
        modified_at=datetime.fromtimestamp(file_path.stat().st_mtime),
        extension=".md",
        detected_type=None,
    )
    first = should_process_item(store, "src", item)
    store.upsert_file_record(
        source_name="src",
        path=str(file_path),
        relative_path="doc.md",
        checksum=first.checksum or "",
        size_bytes=item.size_bytes,
        modified_at=item.modified_at.isoformat() if item.modified_at else None,
        last_status="synced",
    )
    second = should_process_item(store, "src", item)

    assert first.should_process is True
    assert second.should_process is False
