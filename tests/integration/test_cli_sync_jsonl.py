import json
from pathlib import Path

from typer.testing import CliRunner

from opsincident_collector.cli.main import app


def test_cli_sync_jsonl_and_checkpoint_behavior(tmp_path: Path) -> None:
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"
    output = tmp_path / "out.jsonl"
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

    first = runner.invoke(
        app,
        ["sync", "--path", str(project_path), "--config", str(config), "--export", "jsonl", "--output", str(output)],
    )
    second = runner.invoke(
        app,
        ["sync", "--path", str(project_path), "--config", str(config), "--export", "jsonl", "--output", str(output)],
    )

    assert first.exit_code == 0, first.stdout
    first_data = json.loads(first.stdout)
    second_data = json.loads(second.stdout)
    assert first_data["documents_synced"] > 0
    assert second_data["documents_synced"] == 0
    assert "top-secret" not in output.read_text(encoding="utf-8")
    assert "unsafe-demo-secret" not in output.read_text(encoding="utf-8")
    assert "[REDACTED_SECRET]" in output.read_text(encoding="utf-8")
