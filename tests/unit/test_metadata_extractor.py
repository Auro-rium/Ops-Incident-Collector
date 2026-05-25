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
    assert metadata["commit_sha"] == "abcdef1"


def test_metadata_extractor_collects_code_symbols() -> None:
    metadata = extract_metadata(
        Path("service/history/handler.go"),
        "package history\n\ntype Handler struct{}\n\nfunc StartWorkflowTask() error { return nil }\n",
        "code",
    )

    assert metadata["package_path"] == "history"
    assert "StartWorkflowTask" in metadata["function_names"]
    assert "Handler" in metadata["class_names"]
    assert metadata["module_path"] == "service/history/handler"


def test_metadata_extractor_collects_release_markers_and_errors() -> None:
    metadata = extract_metadata(
        Path("CHANGELOG.md"),
        "# Release v1.2.3\nERROR_CODE=ERR_TIMEOUT\n",
        "runbook",
    )

    assert "v1.2.3" in metadata["release_markers"]
    assert "ERR_TIMEOUT" in metadata["error_codes"]
