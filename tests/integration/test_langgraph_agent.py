from __future__ import annotations

import json
from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.cli.main import app
from opsincident_collector.langgraph_agent.checkpoints.sqlite_checkpointer import GraphRunStore
from opsincident_collector.langgraph_agent.runner import approve_action, run_graph
from opsincident_collector.state.sqlite_store import SQLiteStore


def _fixture_path() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"


def _config(tmp_path: Path, project_path: Path, *, api: bool = False) -> Path:
    config = tmp_path / "collector.yaml"
    api_block = ""
    project_block = ""
    if api:
        api_block = """
api:
  base_url: "http://core.test"
  auth_required: false
"""
        project_block = """
project:
  id: "proj_123"
"""
    config.write_text(
        f"""
{api_block}
{project_block}
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "{project_path}"
    - "{tmp_path}"
sources:
  - name: "fixture"
    type: "filesystem"
    path: "{project_path}"
""",
        encoding="utf-8",
    )
    return config


def test_rag_readiness_graph_persists_json_state_and_events(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)

    state = run_graph(
        "rag_readiness",
        {"path": str(project_path), "config_path": str(config)},
        config_path=config,
    )

    assert state["status"] == "completed"
    assert state["rag_readiness"]["score"] > 0
    assert state["eval_seed_preview"]
    json.dumps(state)
    store = GraphRunStore(tmp_path / "state.sqlite")
    try:
        run = store.get_run(state["run_id"])
        events = store.list_events(state["run_id"])
    finally:
        store.close()
    assert run is not None
    assert run["status"] == "completed"
    assert {event["node_name"] for event in events} >= {"inspect_sources", "final_report"}


def test_source_onboarding_api_without_approval_stops_pending(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path, api=True)

    state = run_graph(
        "source_onboarding",
        {
            "path": str(project_path),
            "project_id": "proj_123",
            "config_path": str(config),
            "export_target": "api",
            "dry_run": False,
            "approved": False,
        },
        config_path=config,
    )

    assert state["status"] == "pending_approval"
    assert state["approval_request"]["approval_id"].startswith("approval_")
    assert state["sync_summary"] is None
    assert "unsafe-demo-secret" not in json.dumps(state)
    store = GraphRunStore(tmp_path / "state.sqlite")
    try:
        approvals = store.list_pending_approvals(state["run_id"])
    finally:
        store.close()
    assert approvals
    assert "payload_json" not in json.dumps(approvals)


@respx.mock
def test_approval_allows_source_onboarding_api_sync(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path, api=True)
    _mock_core_ingest()

    pending = run_graph(
        "source_onboarding",
        {
            "path": str(project_path),
            "project_id": "proj_123",
            "config_path": str(config),
            "export_target": "api",
            "dry_run": False,
            "approved": False,
        },
        config_path=config,
    )
    approval_id = pending["approval_request"]["approval_id"]
    approval = approve_action(approval_id, config_path=config, approved=True)
    resumed = run_graph(
        approval["approval"]["graph_name"],
        {},
        config_path=config,
        resume_run_id=approval["approval"]["run_id"],
    )

    assert resumed["status"] == "completed"
    assert resumed["sync_summary"]["documents_synced"] > 0


def test_reject_approval_stops_graph(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path, api=True)
    pending = run_graph(
        "source_onboarding",
        {
            "path": str(project_path),
            "project_id": "proj_123",
            "config_path": str(config),
            "export_target": "api",
            "dry_run": False,
            "approved": False,
        },
        config_path=config,
    )

    rejected = approve_action(
        pending["approval_request"]["approval_id"],
        config_path=config,
        approved=False,
    )

    assert rejected["state"]["status"] == "rejected"


def test_source_onboarding_path_not_allowlisted_fails_safely(tmp_path: Path) -> None:
    project_path = _fixture_path()
    safe = tmp_path / "safe"
    safe.mkdir()
    config = _config(tmp_path, safe)

    state = run_graph(
        "source_onboarding",
        {
            "path": str(project_path),
            "config_path": str(config),
            "export_target": "jsonl",
            "dry_run": True,
        },
        config_path=config,
    )

    assert state["status"] == "failed"
    assert "not allowlisted" in state["errors"][0]


def test_sync_quality_graph_reports_failed_upload_queue(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)
    store = SQLiteStore(tmp_path / "state.sqlite")
    store.record_failed_upload(
        sync_id="sync_1",
        source_name="fixture",
        path="logs/app.log",
        document_external_id="logs/app.log",
        payload_json='{"content":"[REDACTED_SECRET]"}',
        reason="transient_upload_error",
        last_error="500",
    )
    store.close()

    state = run_graph(
        "sync_quality",
        {"path": str(project_path), "config_path": str(config)},
        config_path=config,
    )

    assert state["status"] == "completed"
    assert state["failed_uploads"]["queue_depth"] == 1
    assert state["final_report"]["sync_quality"] in {"weak", "usable", "strong"}
    assert "payload_json" not in json.dumps(state["failed_uploads"])


def test_investigation_bridge_core_unavailable_returns_no_local_diagnosis(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)

    state = run_graph(
        "investigation_bridge",
        {
            "path": str(project_path),
            "project_id": "proj_123",
            "query": "Why did latency increase?",
            "config_path": str(config),
        },
        config_path=config,
    )

    assert state["status"] == "core_unavailable"
    assert state["final_report"]["core_reachable"] is False
    assert state["final_report"]["local_diagnosis"] is None
    assert "root_cause" not in state["final_report"]


@respx.mock
def test_investigation_bridge_calls_core_investigate(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path, api=True)
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
    investigate_route = respx.post("http://core.test/v1/investigate").mock(
        return_value=Response(200, json={"answer": "Core result", "citations": []})
    )

    state = run_graph(
        "investigation_bridge",
        {
            "path": None,
            "project_id": "proj_123",
            "query": "Why did latency increase?",
            "config_path": str(config),
        },
        config_path=config,
    )

    assert state["status"] == "core_investigation_complete"
    assert state["core_investigation_result"]["answer"] == "Core result"
    assert investigate_route.called
    assert state["final_report"]["local_diagnosis"] is None


def test_agent_cli_rag_readiness_json_parseable(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "agent",
            "rag-readiness",
            "--path",
            str(project_path),
            "--config",
            str(config),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["final_report"]["rag_readiness"]["score"] > 0


def test_agent_cli_onboard_source_dry_run_json_parseable(tmp_path: Path) -> None:
    project_path = _fixture_path()
    config = _config(tmp_path, project_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "agent",
            "onboard-source",
            "--path",
            str(project_path),
            "--config",
            str(config),
            "--export-target",
            "console",
            "--dry-run",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["sync_summary"]["documents_synced"] > 0


def _mock_core_ingest() -> None:
    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
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
