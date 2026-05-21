from __future__ import annotations

import os
from pathlib import Path

import yaml

from opsincident_collector.config.settings import AppSettings, DEFAULT_DENY_PATTERNS

DEFAULT_CONFIG_TEMPLATE = """api:
  base_url: "http://127.0.0.1:8001"
  token_env: "INCIDENTOPS_TOKEN"
  timeout_seconds: 30
  verify_tls: true

project:
  id: "proj_123"

collector:
  id: "local-dev-collector"
  name: "local-dev-machine"
  mode: "local"
  environment: "local"

state:
  sqlite_path: ".opsincident-collector/state.sqlite"

sync:
  batch_size: 50
  max_file_size_mb: 10
  incremental: true
  dry_run: false
  compression: false
  retry_count: 3
  retry_backoff_seconds: 5

security:
  redact_secrets: true
  require_confirmation_for_upload: true
  allow_paths:
    - "./sample-data"
    - "./logs"
    - "./docs"
  deny_patterns:
    - ".env"
    - ".env.*"
    - "*.pem"
    - "*.key"
    - "id_rsa"
    - "id_ed25519"
    - "*.p12"
    - "*.pfx"
    - ".git/**"
    - "node_modules/**"
    - ".venv/**"
    - "venv/**"
    - "__pycache__/**"
    - "dist/**"
    - "build/**"
    - "target/**"
    - ".next/**"
    - ".pytest_cache/**"
    - ".mypy_cache/**"
    - ".ruff_cache/**"
    - "*.sqlite"
    - "*.db"
    - "*.parquet"
    - "*.zip"
    - "*.tar"
    - "*.gz"
    - "*.7z"
    - "*.png"
    - "*.jpg"
    - "*.jpeg"
    - "*.mp4"
    - "*.mov"
    - "*.pdf"

mcp:
  enabled: true
  transport: "stdio"
  readonly_default: true
  require_approval_for_sync: true

sources:
  # Replace these sample paths with your actual service, log, runbook, deploy,
  # incident, or API documentation folders. Avoid using your home directory or
  # a repo root unless you intend to inspect everything under it.
  - name: "service-code"
    type: "filesystem"
    path: "./sample-data"
    include:
      - "**/*.md"
      - "**/*.txt"
      - "**/*.log"
      - "**/*.json"
      - "**/*.yaml"
      - "**/*.yml"
      - "**/*.py"
      - "**/*.patch"
      - "**/*.diff"
      - "**/*.sql"
      - "**/*.toml"
      - "**/*.ini"
    exclude:
      - "**/.git/**"
      - "**/node_modules/**"
      - "**/.venv/**"
"""


def find_config_path() -> Path | None:
    env_path = os.getenv("INCIDENTOPS_EDGE_CONFIG") or os.getenv("COLLECTOR_CONFIG")
    candidates = [Path(env_path)] if env_path else []
    candidates.append(Path("collector.yaml"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_settings(config_path: Path) -> AppSettings:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    settings = AppSettings.model_validate(data)
    _apply_env_overrides(settings)
    _merge_default_denies(settings)
    if not settings.sources:
        data = settings.model_dump(mode="json")
        data["sources"] = [
            {
                "name": "default",
                "type": "filesystem",
                "path": ".",
                "include": [],
                "exclude": [],
            }
        ]
        settings = AppSettings.model_validate(data)
        _apply_env_overrides(settings)
        _merge_default_denies(settings)
    return settings


def load_settings_optional(config_path: Path | None) -> AppSettings:
    path = config_path or find_config_path()
    if path and path.exists():
        return load_settings(path)
    settings = AppSettings()
    _apply_env_overrides(settings)
    _merge_default_denies(settings)
    return settings


def _apply_env_overrides(settings: AppSettings) -> None:
    if os.getenv("INCIDENTOPS_API_URL"):
        settings.api.base_url = os.getenv("INCIDENTOPS_API_URL")
    project_id = os.getenv("INCIDENTOPS_PROJECT_ID") or os.getenv("PROJECT_ID")
    if project_id:
        settings.project.id = project_id
    if os.getenv("INCIDENTOPS_EDGE_STATE"):
        settings.state.sqlite_path = Path(os.getenv("INCIDENTOPS_EDGE_STATE", ""))
    source_name = os.getenv("INCIDENTOPS_SOURCE_NAME") or os.getenv("SOURCE_NAME")
    if source_name:
        settings.daemon.source_name = source_name
    source_type = os.getenv("INCIDENTOPS_SOURCE_TYPE") or os.getenv("SOURCE_TYPE")
    if source_type:
        settings.daemon.source_type = source_type
    collector_environment = os.getenv("INCIDENTOPS_COLLECTOR_ENVIRONMENT") or os.getenv(
        "COLLECTOR_ENVIRONMENT"
    )
    if collector_environment:
        settings.collector.environment = collector_environment


def _merge_default_denies(settings: AppSettings) -> None:
    merged = list(dict.fromkeys([*settings.security.deny_patterns, *DEFAULT_DENY_PATTERNS]))
    settings.security.deny_patterns = merged
