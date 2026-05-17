from __future__ import annotations

from pathlib import Path

import respx
from httpx import Response
from typer.testing import CliRunner

from opsincident_collector.cli.main import app


def _config(tmp_path: Path, project_path: Path, api: bool = False) -> Path:
    api_block = (
        """
api:
  base_url: "http://core.test"
  token_env: "INCIDENTOPS_TOKEN"
project:
  id: "proj_123"
"""
        if api
        else ""
    )
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
{api_block}
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
    return config


def test_api_sync_missing_token_fails_clearly(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("INCIDENTOPS_TOKEN", raising=False)
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = _config(tmp_path, project_path, api=True)

    result = runner.invoke(
        app,
        ["sync", "--path", str(project_path), "--config", str(config), "--export", "api", "--yes"],
    )

    assert result.exit_code == 1
    assert "IncidentOps API sync requires a token" in result.stdout


def test_doctor_reports_token_present_without_printing_value(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "super-secret-token")
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = _config(tmp_path, project_path, api=False)

    result = runner.invoke(app, ["doctor", "--config", str(config), "--json"])

    assert result.exit_code == 0
    assert "api_token" in result.stdout
    assert "present" in result.stdout
    assert "super-secret-token" not in result.stdout


def test_watch_api_without_yes_fails_before_loop(tmp_path: Path) -> None:
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = _config(tmp_path, project_path, api=True)

    result = runner.invoke(
        app,
        [
            "watch",
            "--path",
            str(project_path),
            "--config",
            str(config),
            "--export",
            "api",
            "--max-cycles",
            "1",
        ],
    )

    assert result.exit_code == 1
    assert "Refusing API watch sync without confirmation" in result.stdout


def test_watch_api_dry_run_allowed_without_yes(tmp_path: Path) -> None:
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = _config(tmp_path, project_path, api=True)

    result = runner.invoke(
        app,
        [
            "watch",
            "--path",
            str(project_path),
            "--config",
            str(config),
            "--export",
            "api",
            "--dry-run",
            "--max-cycles",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert '"export_target": "api"' in result.stdout or '"export_target":"api"' in result.stdout


@respx.mock
def test_watch_api_with_yes_allowed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INCIDENTOPS_TOKEN", "test-token")
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    config = _config(tmp_path, project_path, api=True)
    respx.get("http://core.test/v1/capabilities").mock(return_value=Response(404))
    respx.post("http://core.test/v1/projects/proj_123/sources").mock(
        return_value=Response(200, json={"source_id": "src_123"})
    )
    respx.post("http://core.test/v1/sources/src_123/syncs").mock(
        return_value=Response(200, json={"sync_id": "sync_123"})
    )
    respx.post("http://core.test/v1/projects/proj_123/sources/src_123/documents:batch").mock(
        return_value=Response(200, json={"ok": True})
    )
    respx.patch("http://core.test/v1/sources/src_123/syncs/sync_123").mock(
        return_value=Response(200, json={"status": "completed"})
    )

    result = runner.invoke(
        app,
        [
            "watch",
            "--path",
            str(project_path),
            "--config",
            str(config),
            "--export",
            "api",
            "--yes",
            "--max-cycles",
            "1",
        ],
    )

    assert result.exit_code == 0, result.stdout
