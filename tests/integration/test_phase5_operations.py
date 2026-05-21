from __future__ import annotations

import json
from pathlib import Path

import httpx
import respx
import yaml
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.cli.main import app
from opsincident_collector.config.loader import load_settings
from opsincident_collector.daemon.health import HealthServer
from opsincident_collector.daemon.metrics import MetricsServer
from opsincident_collector.daemon.service import DaemonService
from opsincident_collector.state.sqlite_store import SQLiteStore


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"


def _config(
    tmp_path: Path,
    project_path: Path,
    *,
    api: bool = False,
    token: bool = False,
    export_target: str = "console",
) -> Path:
    config = tmp_path / "collector.yaml"
    api_block = ""
    project_block = ""
    if api:
        api_block = """
api:
  base_url: "http://core.test"
  token_env: "INCIDENTOPS_TOKEN"
  auth_required: true
"""
        project_block = """
project:
  id: "proj_123"
"""
    if token:
        api_block = api_block.replace("auth_required: true", "auth_required: false")
    config.write_text(
        f"""
{api_block}
{project_block}
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
sync:
  retry_count: 3
  retry_backoff_seconds: 0
security:
  allow_paths:
    - "{project_path}"
  require_confirmation_for_upload: true
daemon:
  enabled: true
  export_target: "{export_target}"
  interval_seconds: 1
  jitter_seconds: 0
  health_host: "127.0.0.1"
  health_port: 0
  metrics_host: "127.0.0.1"
  metrics_port: 0
sources:
  - name: "fixture"
    type: "filesystem"
    path: "{project_path}"
""",
        encoding="utf-8",
    )
    return config


def test_daemon_one_cycle_local_mode_runs(tmp_path: Path) -> None:
    runner = CliRunner()
    config = _config(tmp_path, _fixture_path())

    result = runner.invoke(app, ["daemon", "run", "--config", str(config), "--max-cycles", "1"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout[result.stdout.rfind("{") :])
    assert payload["status"] == "ok"
    assert payload["cycles_completed"] == 1


def test_daemon_api_without_unattended_upload_fails(tmp_path: Path) -> None:
    runner = CliRunner()
    config = _config(tmp_path, _fixture_path(), api=True, export_target="api")

    result = runner.invoke(app, ["daemon", "run", "--config", str(config), "--max-cycles", "1"])

    assert result.exit_code == 1
    assert "daemon API upload requires" in result.stdout or "export_target" not in result.stdout


def test_health_and_metrics_endpoints_are_safe(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)
    settings = load_settings(config)
    store = SQLiteStore(settings.state.sqlite_path)
    store.record_failed_upload(
        sync_id="sync_1",
        source_name="fixture",
        path="logs/app.log",
        document_external_id="logs/app.log",
        payload_json='{"content":"unsafe-demo-secret"}',
        reason="retryable_upload_error",
        last_error="500",
    )
    store.close()
    service = DaemonService(settings, config_path=config)
    health_server = HealthServer("127.0.0.1", 0, service.health_payload)
    metrics_server = MetricsServer("127.0.0.1", 0, service.metrics_payload)
    health_server.start()
    metrics_server.start()
    try:
        health = httpx.get(f"http://127.0.0.1:{health_server.port}/health").json()
        metrics = httpx.get(f"http://127.0.0.1:{metrics_server.port}/metrics").text
    finally:
        health_server.stop()
        metrics_server.stop()

    assert health["status"] == "degraded"
    assert health["pending_failed_uploads"] == 1
    assert "unsafe-demo-secret" not in json.dumps(health)
    assert "collector_retry_queue_depth" in metrics
    assert "unsafe-demo-secret" not in metrics


def test_queue_status_hides_payload_json(tmp_path: Path) -> None:
    runner = CliRunner()
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)
    settings = load_settings(config)
    store = SQLiteStore(settings.state.sqlite_path)
    store.record_failed_upload(
        sync_id="sync_1",
        source_name="fixture",
        path="logs/app.log",
        document_external_id="logs/app.log",
        payload_json='{"content":"unsafe-demo-secret"}',
        reason="retryable_upload_error",
        last_error="500",
    )
    store.close()

    result = runner.invoke(app, ["queue", "status", "--config", str(config), "--format", "json"])

    assert result.exit_code == 0, result.stdout
    assert "payload_json" not in result.stdout
    assert "unsafe-demo-secret" not in result.stdout
    assert json.loads(result.stdout)["total_count"] == 1


@respx.mock
def test_queue_retry_calls_core_and_clears_success(tmp_path: Path) -> None:
    runner = CliRunner()
    project_path = _fixture_path()
    config = _config(tmp_path, project_path, api=True, token=True)
    settings = load_settings(config)
    store = SQLiteStore(settings.state.sqlite_path)
    store.record_failed_upload(
        sync_id="sync_1",
        source_name="fixture",
        path="logs/app.log",
        document_external_id="logs/app.log",
        payload_json=json.dumps(
            {
                "external_id": "logs/app.log",
                "path": "logs/app.log",
                "source_type": "logs",
                "content": "[REDACTED_SECRET]",
                "content_hash": "abc",
                "metadata": {},
                "size_bytes": 10,
                "modified_at": None,
            }
        ),
        reason="retryable_upload_error",
        last_error="500",
    )
    store.close()
    _mock_core_ingest()

    result = runner.invoke(app, ["queue", "retry", "--config", str(config), "--format", "json"])

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["queue"]["total_count"] == 0


def test_validate_rag_pipeline_local_only_json(tmp_path: Path) -> None:
    runner = CliRunner()
    config = _config(tmp_path, _fixture_path())

    result = runner.invoke(
        app,
        [
            "validate-rag-pipeline",
            "--path",
            str(_fixture_path()),
            "--config",
            str(config),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["collector_ready"] is True
    assert payload["documents_prepared"] > 0
    assert "root_cause" not in result.stdout


@respx.mock
def test_validate_rag_pipeline_core_sync_and_investigate_are_explicit(tmp_path: Path) -> None:
    runner = CliRunner()
    config = _config(tmp_path, _fixture_path(), api=True, token=True)
    _mock_core_ingest()
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.post("http://core.test/v1/search").mock(return_value=Response(200, json={"results": []}))
    investigate_route = respx.post("http://core.test/v1/investigate").mock(
        return_value=Response(200, json={"answer": "Core answer", "citations": []})
    )

    result = runner.invoke(
        app,
        [
            "validate-rag-pipeline",
            "--path",
            str(_fixture_path()),
            "--config",
            str(config),
            "--api-url",
            "http://core.test",
            "--project-id",
            "proj_123",
            "--sync",
            "--search",
            "--investigate",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["documents_synced"] > 0
    assert payload["search_test_passed"] is True
    assert payload["investigation_test_passed"] is True
    assert investigate_route.called


def test_phase5_examples_and_dockerfile_are_parseable() -> None:
    for path in [
        Path("examples/local-daemon.yaml"),
        Path("examples/daemon.yaml"),
        Path("examples/production.yaml"),
        Path("examples/aws-daemon.yaml"),
        Path("examples/docker-compose.collector.yml"),
    ]:
        assert yaml.safe_load(path.read_text(encoding="utf-8"))
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert 'ARG INSTALL_TARGET="."' in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "USER opsincident" in dockerfile


def _mock_core_ingest() -> None:
    respx.get("http://core.test/v1/capabilities").mock(
        return_value=Response(
            200,
            json={
                "version": "0.2.0",
                "features": {
                    "source_registry": True,
                    "sync_lifecycle": True,
                    "document_batch_upload": True,
                    "search": True,
                    "investigate": True,
                },
                "endpoints": {
                    "register_collector": "/v1/projects/{project_id}/collectors/register",
                    "batch_upload": "/v1/sources/{source_id}/documents/batch",
                },
            },
        )
    )
    respx.post("http://core.test/v1/projects/proj_123/collectors/register").mock(
        return_value=Response(200, json={"collector_id": "collector_123"})
    )
    respx.post("http://core.test/v1/projects/proj_123/sources").mock(
        return_value=Response(200, json={"source_id": "src_123"})
    )
    respx.post("http://core.test/v1/sources/src_123/syncs/start").mock(
        return_value=Response(200, json={"sync_id": "sync_core"})
    )
    respx.post("http://core.test/v1/sources/src_123/documents/batch").mock(
        return_value=Response(200, json={"ok": True})
    )
    respx.post("http://core.test/v1/sources/src_123/syncs/sync_core/finish").mock(
        return_value=Response(200, json={"status": "success"})
    )
