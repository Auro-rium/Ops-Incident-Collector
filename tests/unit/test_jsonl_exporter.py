import json
from datetime import datetime, timezone
from pathlib import Path

from opsincident_collector.core.models import NormalizedDocument, RedactionSummary, SyncSummary
from opsincident_collector.exporters.jsonl_exporter import JSONLExporter


def test_jsonl_exporter_writes_documents(tmp_path: Path) -> None:
    output = tmp_path / "out.jsonl"
    exporter = JSONLExporter(output)
    document = NormalizedDocument(
        source_name="src",
        source_type="filesystem",
        external_id="src:file.md",
        path="/tmp/file.md",
        relative_path="file.md",
        content="hello",
        content_type="runbook",
        checksum="abc",
        size_bytes=5,
        discovered_at=datetime.now(timezone.utc),
        metadata={},
        redaction=RedactionSummary(enabled=True),
    )
    exporter.export_documents([document], SyncSummary(sync_id="s1", export_target="jsonl"))

    line = output.read_text(encoding="utf-8").strip()
    payload = json.loads(line)
    assert payload["schema_version"] == "incidentops.normalized_document.v1"
    assert payload["core_api_version"] == "v1"
    assert payload["document"]["external_id"] == "src:file.md"
