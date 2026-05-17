from pathlib import Path

from opsincident_collector.processors.metadata_extractor import extract_metadata


def test_metadata_extractor_detects_common_fields() -> None:
    metadata = extract_metadata(
        Path("logs/orders.log"),
        "2026-05-05T10:00:00Z INFO service=orders request_id=req1 GET /api/orders trace_id=tr1 commit abcdef1",
        "logs",
    )

    assert metadata["service_name"] == "orders"
    assert metadata["endpoint"] == "GET /api/orders"
    assert metadata["request_ids"] == ["req1"]
    assert metadata["trace_ids"] == ["tr1"]
