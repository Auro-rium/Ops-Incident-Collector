from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from opsincident_collector.config.source_config import SourceConfig

DEFAULT_SUPPORTED_EXTENSIONS = {
    ".md",
    ".txt",
    ".log",
    ".json",
    ".yaml",
    ".yml",
    ".py",
    ".go",
    ".proto",
    ".patch",
    ".diff",
    ".sql",
    ".toml",
    ".ini",
}

DEFAULT_DENY_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "*.p12",
    "*.pfx",
    "*.crt",
    "*.cer",
    ".git/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "dist/**",
    "build/**",
    "target/**",
    ".next/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    ".ruff_cache/**",
    "*.sqlite",
    "*.db",
    "*.parquet",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.7z",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.mp4",
    "*.mov",
    "*.pdf",
]


class ApiSettings(BaseModel):
    base_url: str | None = None
    token: str | None = Field(default=None, repr=False, exclude=True)
    token_env: str = "INCIDENTOPS_TOKEN"
    timeout_seconds: int = 30
    verify_tls: bool = True
    auth_required: bool = True

    def resolve_token(self) -> str | None:
        if self.token_env:
            env_token = os.getenv(self.token_env)
            if env_token:
                return env_token
        return self.token


class ProjectSettings(BaseModel):
    id: str | None = None


class CollectorSettings(BaseModel):
    id: str = "local-dev-collector"
    name: str = "local-dev-machine"
    mode: str = "local"
    environment: str = "local"


class StateSettings(BaseModel):
    sqlite_path: Path = Path(".opsincident-collector/state.sqlite")


class SyncSettings(BaseModel):
    batch_size: int = 50
    max_file_size_mb: int = 10
    incremental: bool = True
    dry_run: bool = False
    compression: bool = False
    retry_count: int = 3
    retry_backoff_seconds: int = 5
    retry_due_on_start: bool = True


class SecuritySettings(BaseModel):
    redact_secrets: bool = True
    require_confirmation_for_upload: bool = True
    allow_paths: list[str] = Field(default_factory=lambda: ["."])
    deny_patterns: list[str] = Field(default_factory=lambda: list(DEFAULT_DENY_PATTERNS))


class ExportSettings(BaseModel):
    api_batch_endpoint: str | None = None
    fallback_ingest_endpoint: str | None = None


class DaemonSettings(BaseModel):
    enabled: bool = False
    interval_seconds: int = 300
    jitter_seconds: int = 30
    run_once: bool = False
    health_enabled: bool = True
    health_host: str = "127.0.0.1"
    health_port: int = 8686
    metrics_enabled: bool = True
    metrics_host: str = "127.0.0.1"
    metrics_port: int = 8687
    max_cycles: int | None = None
    export_target: str = "console"
    output_path: Path | None = None
    allow_unattended_upload: bool = False
    source_name: str | None = None
    source_type: str = "filesystem"
    max_depth: int = 8


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INCIDENTOPS_",
        extra="ignore",
    )

    api: ApiSettings = Field(default_factory=ApiSettings)
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
    state: StateSettings = Field(default_factory=StateSettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    exporters: ExportSettings = Field(default_factory=ExportSettings)
    daemon: DaemonSettings = Field(default_factory=DaemonSettings)
    sources: list[SourceConfig] = Field(default_factory=list)
