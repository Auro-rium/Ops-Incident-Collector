import inspect
import json
from pathlib import Path

import pytest
import respx
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.cli.main import app
from opsincident_collector.mcp_server import resources as resource_impl
from opsincident_collector.mcp_server.prompt_loader import load_all_prompts, load_prompt
from opsincident_collector.mcp_server.resources import (
    local_config_resource,
    local_failed_uploads_resource,
    project_core_capabilities_resource,
)
from opsincident_collector.mcp_server.server import create_fastmcp_server, describe_mcp_surface
from opsincident_collector.mcp_server.tools import (
    create_workflow_run,
    generate_eval_seed,
    get_rag_readiness,
    get_run_events,
    get_run_status,
    inspect_folder,
    investigate_incident,
    preview_redaction,
    search_evidence,
    sync_source,
    validate_core_contract,
    validate_source_config,
)
from opsincident_collector.state.sqlite_store import SQLiteStore


def test_create_fastmcp_server_accepts_templated_resources() -> None:
    pytest.importorskip("mcp.server.fastmcp")

    server = create_fastmcp_server(Path("examples/mcp.json"))

    assert server is not None


def test_dynamic_project_resource_functions_accept_project_id() -> None:
    for name in [
        "get_project_sources",
        "get_project_coverage",
        "get_project_core_capabilities",
    ]:
        signature = inspect.signature(getattr(resource_impl, name))
        assert "project_id" in signature.parameters


def test_mcp_dump_schema_lists_tools_resources_and_prompts() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["mcp", "serve", "--config", "examples/mcp.json", "--dump-schema"])

    assert result.exit_code == 0, result.stdout
    schema = json.loads(result.stdout)
    assert "inspect_folder" in schema["tools"]
    assert "incidentops://project/{project_id}/sources" in schema["resources"]
    assert "core_investigation_bridge" in schema["prompts"]


def test_mcp_tools_invoke_shared_functions(tmp_path: Path) -> None:
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
collector:
  mode: "local"
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "{project_path}"
sources:
  - name: "fixture"
    type: "filesystem"
    path: "{project_path}"
""",
        encoding="utf-8",
    )
    inspection = inspect_folder(str(project_path), config_path=str(config))
    preview = preview_redaction(str(project_path / "logs" / "app.log"), config_path=str(config))
    readiness = get_rag_readiness(str(project_path), config_path=str(config))
    validation = validate_source_config(str(config))
    eval_seed = generate_eval_seed(str(project_path), config_path=str(config))
    output = tmp_path / "out.jsonl"
    summary = sync_source(
        path=str(project_path),
        export_target="jsonl",
        dry_run=True,
        approved=False,
        config_path=str(config),
        output=str(output),
    )

    assert inspection["ok"] is True
    assert inspection["inspection"]["supported_files"] > 0
    assert inspection["coverage"]["has_logs"] is True
    assert "[REDACTED_SECRET]" in preview["preview"]
    assert readiness["rag_readiness"]["score"] > 0
    assert validation["valid"] is True
    assert eval_seed["case_count"] > 0
    assert summary["summary"]["documents_synced"] > 0


def test_preview_redaction_refuses_non_allowlisted_path(tmp_path: Path) -> None:
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
security:
  allow_paths:
    - "{tmp_path / 'safe'}"
""",
        encoding="utf-8",
    )
    unsafe = tmp_path / "unsafe.log"
    unsafe.write_text("password=secret", encoding="utf-8")

    with pytest.raises(PermissionError):
        preview_redaction(str(unsafe), config_path=str(config))


def test_preview_redaction_refuses_denied_file_even_when_allowlisted(tmp_path: Path) -> None:
    safe = tmp_path / "safe"
    safe.mkdir()
    env_file = safe / ".env"
    env_file.write_text("PASSWORD=raw-secret", encoding="utf-8")
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
security:
  allow_paths:
    - "{safe}"
""",
        encoding="utf-8",
    )

    with pytest.raises(PermissionError):
        preview_redaction(str(env_file), config_path=str(config))


def test_sync_source_requires_approval(tmp_path: Path) -> None:
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = tmp_path / "collector.yaml"
    output = tmp_path / "out.jsonl"
    config.write_text(
        f"""
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "{project_path}"
sources:
  - name: "fixture"
    type: "filesystem"
    path: "{project_path}"
""",
        encoding="utf-8",
    )

    with pytest.raises(PermissionError):
        sync_source(
            path=str(project_path),
            export_target="jsonl",
            dry_run=False,
            approved=False,
            config_path=str(config),
            output=str(output),
        )


def test_mcp_data_export_tools_require_approval_for_writes(tmp_path: Path) -> None:
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
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

    with pytest.raises(PermissionError):
        generate_eval_seed(
            str(project_path),
            output=str(tmp_path / "eval.jsonl"),
            config_path=str(config),
        )

    result = generate_eval_seed(
        str(project_path),
        output=str(tmp_path / "eval.jsonl"),
        approved=True,
        config_path=str(config),
    )
    assert result["ok"] is True
    assert (tmp_path / "eval.jsonl").exists()


@respx.mock
def test_mcp_core_calling_tools_use_core_adapter(tmp_path: Path) -> None:
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
api:
  base_url: "http://core.test"
  auth_required: false
project:
  id: "proj_123"
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "."
""",
        encoding="utf-8",
    )
    respx.post("http://core.test/v1/search").mock(
        return_value=Response(200, json={"results": [{"id": "doc1"}]})
    )
    respx.post("http://core.test/v1/investigate").mock(
        return_value=Response(200, json={"answer": "Core answer"})
    )
    respx.post("http://core.test/v1/runs").mock(
        return_value=Response(200, json={"run_id": "run_123", "status": "queued"})
    )
    respx.get("http://core.test/v1/runs/run_123").mock(
        return_value=Response(200, json={"run_id": "run_123", "status": "complete"})
    )
    respx.get("http://core.test/v1/runs/run_123/events").mock(
        return_value=Response(200, json={"events": [{"type": "done"}]})
    )

    search = search_evidence("proj_123", "orders", config_path=str(config))
    investigation = investigate_incident("proj_123", "orders", config_path=str(config))
    assert search["response"]["results"][0]["id"] == "doc1"
    assert investigation["response"]["answer"] == "Core answer"
    with pytest.raises(PermissionError):
        create_workflow_run("proj_123", "orders", config_path=str(config))
    run = create_workflow_run("proj_123", "orders", approved=True, config_path=str(config))
    assert run["response"]["run_id"] == "run_123"
    assert get_run_status("run_123", config_path=str(config))["response"]["status"] == "complete"
    events = get_run_events("run_123", config_path=str(config))
    assert events["response"]["events"][0]["type"] == "done"


@respx.mock
def test_mcp_validate_core_contract_uses_mocked_core(tmp_path: Path) -> None:
    config = tmp_path / "collector.yaml"
    config.write_text(
        """
api:
  base_url: "http://core.test"
  auth_required: false
project:
  id: "proj_123"
""",
        encoding="utf-8",
    )
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(
        return_value=Response(
            200,
            json={
                "features": {"document_batch_upload": True, "search": True, "investigate": True},
                "endpoints": {"batch_upload": "/v1/sources/{source_id}/documents/batch"},
            },
        )
    )

    result = validate_core_contract(config_path=str(config))

    assert result["ok"] is True
    assert result["report"]["sample_uploaded"] is False
    assert all(call.request.method == "GET" for call in respx.calls)


def test_xml_prompt_loader_and_surface() -> None:
    prompts = load_all_prompts()

    assert set(prompts) >= {
        "source_coverage_review",
        "sync_decision",
        "rag_readiness_report",
        "incident_setup_planner",
        "post_sync_quality_gate",
        "core_investigation_bridge",
        "missing_data_advisor",
    }
    assert "Core remains the investigation brain" in prompts["core_investigation_bridge"].raw_xml
    with pytest.raises(FileNotFoundError):
        load_prompt("missing_prompt")
    surface = describe_mcp_surface()
    assert "inspect_folder" in surface["tools"]
    assert "core_investigation_bridge" in surface["prompts"]


def test_mcp_resources_are_safe(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "env-secret-token")
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
api:
  base_url: "http://core.test"
  token: "raw-yaml-token"
  token_env: "INCIDENTOPS_TOKEN"
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "{tmp_path}"
""",
        encoding="utf-8",
    )
    store = SQLiteStore(tmp_path / "state.sqlite")
    store.record_failed_upload(
        sync_id="sync_1",
        source_name="fixture",
        path="logs/app.log",
        document_external_id="logs/app.log",
        payload_json='{"content":"unsafe-demo-secret"}',
        reason="transient_upload_error",
        last_error="500",
    )
    store.close()

    config_resource = local_config_resource(config)
    failed_resource = local_failed_uploads_resource(config)

    assert "raw-yaml-token" not in str(config_resource)
    assert "env-secret-token" not in str(config_resource)
    assert config_resource["api"]["token_present"] is True
    assert failed_resource["queue_depth"] == 1
    assert "payload_json" not in failed_resource["failed_uploads"][0]
    assert "unsafe-demo-secret" not in str(failed_resource)


@respx.mock
def test_project_core_capabilities_resource_uses_core_contract_validator(tmp_path: Path) -> None:
    config = tmp_path / "collector.yaml"
    config.write_text(
        """
api:
  base_url: "http://core.test"
  auth_required: false
""",
        encoding="utf-8",
    )
    respx.get("http://core.test/health").mock(return_value=Response(200, json={"status": "ok"}))
    respx.get("http://core.test/v1/capabilities").mock(
        return_value=Response(
            200,
            json={
                "features": {"document_batch_upload": True},
                "endpoints": {"batch_upload": "/v1/sources/{source_id}/documents/batch"},
            },
        )
    )

    result = project_core_capabilities_resource("proj_123", config)

    assert result["ok"] is True
    assert result["report"]["compatible"] is True
