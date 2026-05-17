from __future__ import annotations

from pathlib import Path

import respx
from httpx import Response

from opsincident_collector.config.settings import AppSettings, SourceConfig
from opsincident_collector.core.pipeline import run_sync
from opsincident_collector.state.sqlite_store import SQLiteStore


def _settings(tmp_path: Path, project_path: Path) -> AppSettings:
    settings = AppSettings()
    settings.api.base_url = "http://core.test"
    settings.project.id = "proj_123"
    settings.state.sqlite_path = tmp_path / "state.sqlite"
    settings.security.allow_paths = [str(project_path)]
    settings.sources = [SourceConfig(name="fixture", path=str(project_path))]
    return settings


def _mock_core_success() -> respx.Router:
    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
    respx.post("http://core.test/v1/projects/proj_123/sources").mock(
        return_value=Response(200, json={"source_id": "src_123"})
    )
    respx.post("http://core.test/v1/sources/src_123/syncs").mock(
        return_value=Response(200, json={"sync_id": "sync_123"})
    )
    respx.patch("http://core.test/v1/sources/src_123/syncs/sync_123").mock(
        return_value=Response(200, json={"status": "completed"})
    )
    return respx.post("http://core.test/v1/projects/proj_123/sources/src_123/documents:batch")


@respx.mock
def test_api_exporter_syncs_with_mocked_core(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "test-token")
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    upload_route = _mock_core_success().mock(return_value=Response(200, json={"ok": True}))

    summary = run_sync(
        path=project_path,
        settings=_settings(tmp_path, project_path),
        export_target="api",
        project_id="proj_123",
        source_name="fixture",
        output=None,
        dry_run=False,
        force=False,
        no_redact=False,
    )

    payload = upload_route.calls[0].request.read()
    assert summary.documents_synced > 0
    assert summary.bytes_uploaded > 0
    assert b'"collector_version"' in payload
    assert b'"schema_version":"incidentops.normalized_document.v1"' in payload
    assert upload_route.calls[0].request.headers["authorization"] == "Bearer test-token"


@respx.mock
def test_api_transient_failure_queues_and_retry_succeeds(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "test-token")
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    upload_calls = {"count": 0}

    def upload_response(_request):
        upload_calls["count"] += 1
        if upload_calls["count"] == 1:
            return Response(500, json={"error": "temporary"})
        return Response(200, json={"ok": True})

    upload_route = _mock_core_success().mock(side_effect=upload_response)
    settings = _settings(tmp_path, project_path)
    settings.sync.batch_size = 100
    settings.sync.retry_backoff_seconds = 0

    first = run_sync(
        path=project_path,
        settings=settings,
        export_target="api",
        project_id="proj_123",
        source_name="fixture",
        output=None,
        dry_run=False,
        force=False,
        no_redact=False,
    )
    store = SQLiteStore(settings.state.sqlite_path)
    queued = store.list_failed_uploads()
    assert first.documents_synced == 0
    assert first.failed_uploads > 0
    assert store.failed_upload_queue_depth("fixture") > 0
    assert "top-secret" not in queued[0]["payload_json"]
    assert "unsafe-demo-secret" not in queued[0]["payload_json"]
    store.close()

    second = run_sync(
        path=project_path,
        settings=settings,
        export_target="api",
        project_id="proj_123",
        source_name="fixture",
        output=None,
        dry_run=False,
        force=True,
        no_redact=False,
    )
    store = SQLiteStore(settings.state.sqlite_path)
    assert second.retry_attempted > 0
    assert second.retry_succeeded > 0
    assert store.failed_upload_queue_depth("fixture") == 0
    assert upload_route.call_count > 1
    store.close()


@respx.mock
def test_api_validation_failure_does_not_retry_forever(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "test-token")
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    _mock_core_success().mock(return_value=Response(422, json={"error": "bad schema"}))
    settings = _settings(tmp_path, project_path)
    settings.sync.batch_size = 100
    settings.sync.retry_count = 3

    summary = run_sync(
        path=project_path,
        settings=settings,
        export_target="api",
        project_id="proj_123",
        source_name="fixture",
        output=None,
        dry_run=False,
        force=True,
        no_redact=False,
    )

    store = SQLiteStore(settings.state.sqlite_path)
    queued = store.list_failed_uploads()
    assert summary.failed_uploads > 0
    assert queued[0]["reason"] == "non_retryable_upload_error"
    assert queued[0]["retry_count"] == settings.sync.retry_count
    assert store.get_due_failed_uploads("fixture", settings.sync.retry_count) == []
    store.close()
