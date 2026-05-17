from pathlib import Path

from typer.testing import CliRunner

from opsincident_collector.cli.main import app


def test_cli_inspect_fixture_project_json() -> None:
    runner = CliRunner()
    project_path = Path(__file__).resolve().parents[1] / "fixtures" / "basic_project"

    result = runner.invoke(app, ["inspect", "--path", str(project_path), "--format", "json"])

    assert result.exit_code == 0, result.stdout
    assert '"supported_files"' in result.stdout
    assert '"denied_files"' in result.stdout
    assert '"possible_secrets_detected"' in result.stdout
    assert '".env"' in result.stdout
