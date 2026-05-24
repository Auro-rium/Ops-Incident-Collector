from __future__ import annotations

from pathlib import Path

import yaml

from opsincident_collector.config.loader import find_config_path, load_settings_optional


def test_aws_env_aliases_are_supported(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "collector.yaml"
    config.write_text(
        f"""
state:
  sqlite_path: "{tmp_path / 'state.sqlite'}"
security:
  allow_paths:
    - "{tmp_path}"
daemon:
  source_name: "from-config"
  source_type: "filesystem"
sources:
  - name: "fixture"
    type: "filesystem"
    path: "{tmp_path}"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("COLLECTOR_CONFIG", str(config))
    monkeypatch.setenv("INCIDENTOPS_API_URL", "https://core.internal")
    monkeypatch.setenv("PROJECT_ID", "proj_aws")
    monkeypatch.setenv("SOURCE_NAME", "aws-source")
    monkeypatch.setenv("SOURCE_TYPE", "logs_folder")
    monkeypatch.setenv("COLLECTOR_ENVIRONMENT", "aws-prod")

    assert find_config_path() == config
    settings = load_settings_optional(None)

    assert settings.api.base_url == "https://core.internal"
    assert settings.project.id == "proj_aws"
    assert settings.daemon.source_name == "aws-source"
    assert settings.daemon.source_type == "logs_folder"
    assert settings.collector.environment == "aws-prod"


def test_azure_dispatch_workflow_exists_and_is_safe() -> None:
    workflow = Path(".github/workflows/deploy-collector.yml").read_text(encoding="utf-8")
    workflow_yaml = yaml.safe_load(workflow)

    assert workflow_yaml["name"] == "Validate and Deploy Azure Collector"
    assert workflow_yaml["permissions"] == {"contents": "read"}
    assert "CORE_DEPLOY_TOKEN" in workflow
    assert "deploy-azure.yml" in workflow
    assert "actions/workflows/${CORE_DEPLOY_WORKFLOW}/dispatches" in workflow

    assert "aws-actions/configure-aws-credentials" not in workflow
    assert "amazon-ecr-login" not in workflow
    assert "aws ecs" not in workflow
    assert "AWS_ACCESS_KEY_ID" not in workflow
    assert "AWS_SECRET_ACCESS_KEY" not in workflow


def test_dockerfile_exposes_daemon_ports_and_non_root_user() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "USER opsincident" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "EXPOSE 8686 8687" in dockerfile
