from pathlib import Path

from opsincident_collector.receivers import api_docs, deploy_history, git_local, incidents, logs_folder, runbooks


def test_logs_receiver_extracts_operational_metadata() -> None:
    metadata = logs_folder.extract_metadata(
        Path("logs/app.log"),
        "2026-05-05T10:00:00Z ERROR trace_id=tr1 request_id=req1 GET /api/orders",
    )

    assert metadata["source_kind"] == "logs"
    assert metadata["trace_ids"] == ["tr1"]
    assert metadata["request_ids"] == ["req1"]
    assert "GET /api/orders" in metadata["endpoints"]


def test_git_receiver_gracefully_handles_non_repo(tmp_path: Path) -> None:
    path = tmp_path / "service.py"
    path.write_text("print('ok')", encoding="utf-8")

    metadata = git_local.extract_metadata(path)

    assert metadata["source_kind"] == "code"
    assert "git_available" in metadata


def test_deploy_receiver_extracts_deploy_fields() -> None:
    metadata = deploy_history.extract_metadata(
        Path("deploys/deploy-history.json"),
        '{"service":"orders","environment":"prod","commit_sha":"abcdef1","deployed_at":"2026-05-05T10:00:00Z"}',
    )

    assert metadata["source_kind"] == "deploy_history"
    assert metadata["service_name"] == "orders"
    assert metadata["commit_sha"] == "abcdef1"


def test_runbook_receiver_extracts_headings_and_kind() -> None:
    metadata = runbooks.extract_metadata(Path("runbooks/restart-service.md"), "# Restart Service\n## Rollback")

    assert metadata["source_kind"] == "runbook"
    assert metadata["headings"] == ["Restart Service", "Rollback"]


def test_incident_receiver_extracts_date_and_sections() -> None:
    metadata = incidents.extract_metadata(
        Path("incidents/incident-2026-05-05.md"),
        "# Summary\n## Timeline\n## Root Cause\n## Resolution",
    )

    assert metadata["source_kind"] == "incident_report"
    assert metadata["incident_date"] == "2026-05-05"
    assert metadata["has_root_cause"] is True


def test_api_docs_receiver_extracts_openapi_paths() -> None:
    metadata = api_docs.extract_metadata(
        Path("openapi.yaml"),
        "openapi: 3.0.0\npaths:\n  /api/orders:\n    get:\n      responses: {}\n",
    )

    assert metadata["source_kind"] == "api_doc"
    assert "/api/orders" in metadata["endpoints"]
