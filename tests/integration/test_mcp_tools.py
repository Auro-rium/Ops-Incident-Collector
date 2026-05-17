from pathlib import Path

import pytest

from opsincident_collector.mcp_server.tools import inspect_folder, preview_redaction, sync_source


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
    output = tmp_path / "out.jsonl"
    summary = sync_source(
        path=str(project_path),
        export_target="jsonl",
        dry_run=True,
        approved=False,
        config_path=str(config),
        output=str(output),
    )

    assert inspection["supported_files"] > 0
    assert "[REDACTED_SECRET]" in preview["preview"]
    assert summary["documents_synced"] > 0


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
