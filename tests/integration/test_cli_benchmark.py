from __future__ import annotations

import json
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.cli.main import app


@respx.mock
def test_cli_benchmark_runs_three_syncs_and_writes_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "test-token")
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    output = tmp_path / "benchmark.json"
    project_id = "11111111-1111-1111-1111-111111111111"
    collector_id = "22222222-2222-2222-2222-222222222222"
    source_id = "33333333-3333-3333-3333-333333333333"
    sync_ids = [
        "44444444-4444-4444-4444-444444444441",
        "44444444-4444-4444-4444-444444444442",
        "44444444-4444-4444-4444-444444444443",
    ]
    start_calls = {"count": 0}
    latest_calls = {"count": 0}

    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
    respx.post(f"http://core.test/v1/projects/{project_id}/collectors/register").mock(
        return_value=Response(200, json={"collector_id": collector_id})
    )
    respx.post(f"http://core.test/v1/projects/{project_id}/sources").mock(
        return_value=Response(200, json={"source_id": source_id})
    )

    def start_response(_request):
        index = start_calls["count"]
        start_calls["count"] += 1
        return Response(200, json={"sync_id": sync_ids[index]})

    respx.post(f"http://core.test/v1/sources/{source_id}/syncs/start").mock(side_effect=start_response)
    for sync_id in sync_ids:
        respx.post(f"http://core.test/v1/sources/{source_id}/syncs/{sync_id}/finish").mock(
            return_value=Response(200, json={"sync_id": sync_id, "status": "success"})
        )
    respx.post(f"http://core.test/v1/sources/{source_id}/documents/batch").mock(
        return_value=Response(200, json={"ok": True})
    )

    latest_payloads = [
        {
            "sync_id": sync_ids[0],
            "project_id": project_id,
            "source_id": source_id,
            "status": "success",
            "started_at": "2026-01-01T00:00:00Z",
            "finished_at": "2026-01-01T00:00:01Z",
            "documents_received": 3,
            "chunks_created": 5,
            "diagnostics": {"documents_created": 3, "chunks_created": 5},
            "coverage": {"has_code": True},
        },
        {
            "sync_id": sync_ids[1],
            "project_id": project_id,
            "source_id": source_id,
            "status": "success",
            "started_at": "2026-01-01T00:00:02Z",
            "finished_at": "2026-01-01T00:00:03Z",
            "documents_received": 3,
            "chunks_created": 0,
            "diagnostics": {"skipped_unchanged": 3, "last_batch_chunks_created": 0},
            "coverage": {"has_code": True},
        },
        {
            "sync_id": sync_ids[2],
            "project_id": project_id,
            "source_id": source_id,
            "status": "success",
            "started_at": "2026-01-01T00:00:04Z",
            "finished_at": "2026-01-01T00:00:05Z",
            "documents_received": 3,
            "chunks_created": 1,
            "diagnostics": {"documents_updated": 1, "last_batch_chunks_created": 1},
            "coverage": {"has_code": True},
        },
    ]

    def latest_response(_request):
        index = latest_calls["count"]
        latest_calls["count"] += 1
        return Response(200, json=latest_payloads[index])

    respx.get(f"http://core.test/v1/sources/{source_id}/syncs/latest").mock(side_effect=latest_response)
    respx.post("http://core.test/v1/search").mock(
        return_value=Response(
            200,
            json={
                "query": "Where are routes or authentication configured?",
                "hits": [{"document_path": "app/main.py", "source_type": "code"}],
            },
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "benchmark",
            "--path",
            str(project_path),
            "--core-url",
            "http://core.test",
            "--project-id",
            project_id,
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    report = json.loads(output.read_text(encoding="utf-8"))
    assert [item["label"] for item in report["syncs"]] == [
        "initial",
        "same_content_resync",
        "changed_file_resync",
    ]
    assert report["checks"]["resync_duplicate_chunks"] == 0
    assert report["checks"]["duplicate_chunks_after_update"] == 0
    assert report["checks"]["changed_file_update"] == "pass"
    assert report["search"]["ok"] is True
    assert report["search_queries"][0]["search_result_count"] == 1
    assert report["search_queries"][0]["top_evidence_paths"] == ["app/main.py"]
    assert report["inspection"]["supported_files"] > 0
    assert report["commit_sha"] is None
    assert report["benchmark_started_at"]
