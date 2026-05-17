from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.adapters.core_contract_validator import MISSING_BATCH_MESSAGE, validate_core_contract
from opsincident_collector.cli.main import app
from opsincident_collector.config.settings import AppSettings
from opsincident_collector.core.analysis import (
    build_rag_readiness_report,
    build_source_coverage_report,
    collect_normalized_documents,
    generate_eval_seed_cases,
)
from opsincident_collector.core.core_payload import to_core_document_payload
from opsincident_collector.core.pipeline import run_sync


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"


def _settings(path: Path, tmp_path: Path | None = None) -> AppSettings:
    settings = AppSettings()
    settings.security.allow_paths = [str(path)]
    if tmp_path:
        settings.state.sqlite_path = tmp_path / "state.sqlite"
    return settings


def test_citation_and_chunking_hints_exist_for_fixture_documents() -> None:
    project_path = _fixture_path()
    documents = collect_normalized_documents(project_path, _settings(project_path))
    by_type = {document.content_type: document for document in documents}

    for content_type in ["logs", "code", "incident_report", "runbook"]:
        document = by_type[content_type]
        citation_hints = document.metadata["citation_hints"]
        chunking_hints = document.metadata["chunking_hints"]
        assert citation_hints
        assert chunking_hints
        assert citation_hints[0]["path"]
        assert citation_hints[0]["start_line"] is not None

    serialized = json.dumps([document.metadata for document in documents])
    assert "unsafe-demo-secret" not in serialized


def test_richer_metadata_is_json_serializable_and_secret_safe() -> None:
    project_path = _fixture_path()
    documents = collect_normalized_documents(project_path, _settings(project_path))
    log_doc = next(document for document in documents if document.content_type == "logs")
    code_doc = next(document for document in documents if document.content_type == "code")
    deploy_doc = next(document for document in documents if document.content_type == "deploy_history")

    assert log_doc.metadata.get("endpoint_candidates") or log_doc.metadata.get("log_levels")
    assert log_doc.metadata["request_ids"] == ["req-1"]
    assert code_doc.metadata["language"] == "py"
    assert deploy_doc.metadata["commit_shas"] == ["abcdef1234567890"]
    assert "unsafe-demo-secret" not in json.dumps(log_doc.metadata)
    json.dumps([document.model_dump(mode="json") for document in documents])


def test_source_coverage_and_rag_readiness_reports_change_with_sources(tmp_path: Path) -> None:
    project_path = _fixture_path()
    full_report = build_rag_readiness_report(project_path, _settings(project_path))
    full_coverage = build_source_coverage_report(project_path, _settings(project_path))

    logs_only = tmp_path / "logs_only"
    logs_only.mkdir()
    (logs_only / "app.log").write_text("2026-05-05T10:00:00Z ERROR service=orders timeout", encoding="utf-8")
    partial_report = build_rag_readiness_report(logs_only, _settings(logs_only))

    assert full_coverage.has_logs is True
    assert full_coverage.has_code is True
    assert full_coverage.has_api_docs is False
    assert "api_docs" in full_coverage.missing_recommended_sources
    assert full_report.score > partial_report.score
    assert partial_report.ready_for_core_sync is True
    assert "code" in partial_report.recommended_next_sources


def test_eval_seed_generation_is_deterministic_and_references_real_files(tmp_path: Path) -> None:
    project_path = _fixture_path()
    cases = generate_eval_seed_cases(project_path, _settings(project_path))
    output = tmp_path / "eval_seed.jsonl"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["eval-seed", "--path", str(project_path), "--output", str(output), "--format", "json"],
    )

    assert result.exit_code == 0, result.stdout
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(cases)
    assert {case["source_type"] for case in lines} >= {"logs", "deploy_history", "incident_report", "runbook"}
    for case in lines:
        for expected_doc in case["expected_documents"]:
            assert (project_path / expected_doc).exists()


@respx.mock
def test_core_contract_validation_with_capabilities_passes_without_upload() -> None:
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(
        return_value=Response(
            200,
            json={
                "version": "0.2.0",
                "features": {
                    "source_registry": True,
                    "collector_registration": True,
                    "sync_lifecycle": True,
                    "document_batch_upload": True,
                    "search": True,
                    "investigate": True,
                },
                "endpoints": {"batch_upload": "/v1/sources/{source_id}/documents/batch"},
            },
        )
    )

    report = validate_core_contract(api_url="http://core.test", project_id="proj_123")

    assert report["compatible"] is True
    assert report["supported_features"]["document_batch_upload"] is True
    assert all(call.request.method == "GET" for call in respx.calls)


@respx.mock
def test_core_contract_validation_without_batch_upload_fails() -> None:
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(
        return_value=Response(200, json={"features": {"source_registry": True}, "endpoints": {}})
    )

    report = validate_core_contract(api_url="http://core.test", project_id="proj_123")

    assert report["compatible"] is False
    assert MISSING_BATCH_MESSAGE in report["errors"]


@respx.mock
def test_core_contract_validation_uses_openapi_when_capabilities_missing() -> None:
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
    respx.get("http://core.test/openapi.json").mock(
        return_value=Response(
            200,
            json={
                "paths": {
                    "/v1/projects/{project_id}/sources": {},
                    "/v1/projects/{project_id}/collectors/register": {},
                    "/v1/sources/{source_id}/syncs/start": {},
                    "/v1/sources/{source_id}/documents/batch": {},
                    "/v1/sources/{source_id}/syncs/{sync_id}/finish": {},
                    "/v1/search": {},
                    "/v1/investigate": {},
                }
            },
        )
    )

    report = validate_core_contract(api_url="http://core.test", project_id="proj_123")

    assert report["compatible"] is True
    assert report["supported_features"]["document_batch_upload"] is True


def test_core_payload_maps_checksum_to_content_hash_and_keeps_hints() -> None:
    project_path = _fixture_path()
    document = collect_normalized_documents(project_path, _settings(project_path))[0]

    payload = to_core_document_payload(document)

    assert payload["content_hash"] == document.checksum
    assert "checksum" not in payload
    assert payload["metadata"]["citation_hints"]
    assert payload["metadata"]["chunking_hints"]
    assert not Path(payload["path"]).is_absolute()


def test_jsonl_and_sqlite_exports_preserve_enriched_metadata(tmp_path: Path) -> None:
    project_path = _fixture_path()
    settings = _settings(project_path, tmp_path)
    jsonl_output = tmp_path / "docs.jsonl"
    sqlite_output = tmp_path / "docs.sqlite"

    run_sync(
        path=project_path,
        settings=settings,
        export_target="jsonl",
        project_id=None,
        source_name="fixture",
        output=jsonl_output,
        force=True,
    )
    line = json.loads(jsonl_output.read_text(encoding="utf-8").splitlines()[0])
    metadata = line["document"]["metadata"]
    assert metadata["citation_hints"]
    assert metadata["chunking_hints"]

    run_sync(
        path=project_path,
        settings=settings,
        export_target="sqlite",
        project_id=None,
        source_name="fixture-sqlite",
        output=sqlite_output,
        force=True,
    )
    conn = sqlite3.connect(sqlite_output)
    row = conn.execute("SELECT metadata_json FROM normalized_documents LIMIT 1").fetchone()
    conn.close()
    sqlite_metadata = json.loads(row[0])
    assert sqlite_metadata["citation_hints"]
    assert sqlite_metadata["chunking_hints"]
