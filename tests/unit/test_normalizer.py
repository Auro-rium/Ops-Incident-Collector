from datetime import datetime
from pathlib import Path

from opsincident_collector.core.models import RawDocument, SourceItem
from opsincident_collector.processors.normalizer import normalize_document


def test_normalizer_redacts_content_and_sets_metadata(tmp_path: Path) -> None:
    path = tmp_path / "app.log"
    path.write_text("Bearer abc123\nservice=orders", encoding="utf-8")
    item = SourceItem(
        path=path,
        relative_path="app.log",
        size_bytes=path.stat().st_size,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        extension=".log",
        detected_type=None,
    )
    raw = RawDocument(source_item=item, content=path.read_text(), encoding="utf-8", metadata={})

    document = normalize_document(raw, source_name="test", source_type="filesystem")

    assert document.content_type == "logs"
    assert "[REDACTED_SECRET]" in document.content
    assert document.metadata["service_name"] == "orders"
