from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from opsincident_collector.config.settings import DEFAULT_DENY_PATTERNS
from opsincident_collector.config.loader import load_settings
from opsincident_collector.processors.path_policy import is_allowed_path


def validate(
    config: Path = typer.Option(..., "--config", exists=True, dir_okay=False, resolve_path=True),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    settings = load_settings(config)
    source_errors: list[str] = []
    warnings: list[str] = []
    allowed_paths: list[dict[str, str]] = []
    config_dir = config.parent

    for allowed in settings.security.allow_paths:
        allowed_path = Path(allowed)
        if not allowed_path.is_absolute():
            allowed_path = (config_dir / allowed_path).resolve()
        status = "ok" if allowed_path.exists() else "missing"
        allowed_paths.append({"path": str(allowed_path), "status": status})
        if status == "missing":
            warnings.append(f"allow path does not exist: {allowed}")
        if allowed_path == Path("/"):
            warnings.append("unsafe allow path: /")
        if allowed_path == Path.home():
            warnings.append("unsafe allow path: home directory")

    resolved_allow_paths = [entry["path"] for entry in allowed_paths]
    for source in settings.sources:
        source_path = Path(source.path)
        if not source_path.is_absolute() and not source_path.exists():
            source_path = config.parent / source_path
        if not source_path.exists():
            source_errors.append(f"missing source path: {source.path}")
        elif not is_allowed_path(source_path.resolve(), resolved_allow_paths):
            source_errors.append(f"source path not allowlisted: {source.path}")
    if settings.api.base_url and settings.api.auth_required and not settings.api.token_env:
        source_errors.append("api.token_env is required when API auth is enabled")
    if settings.api.base_url and settings.api.auth_required and not settings.api.resolve_token():
        warnings.append(f"API token is not present in {settings.api.token_env}")
    if not settings.security.deny_patterns:
        source_errors.append("security.deny_patterns must not be empty")
    missing_default_denies = sorted(set(DEFAULT_DENY_PATTERNS) - set(settings.security.deny_patterns))
    if missing_default_denies:
        warnings.append("default deny patterns were not fully active before loader merge")
    if settings.sync.max_file_size_mb <= 0 or settings.sync.max_file_size_mb > 1024:
        source_errors.append("sync.max_file_size_mb must be between 1 and 1024")
    if settings.sync.retry_count < 0:
        source_errors.append("sync.retry_count must be >= 0")
    if settings.sync.retry_backoff_seconds < 0:
        source_errors.append("sync.retry_backoff_seconds must be >= 0")
    if settings.daemon.interval_seconds <= 0:
        source_errors.append("daemon.interval_seconds must be > 0")
    if settings.daemon.export_target not in {"api", "jsonl", "sqlite", "console"}:
        source_errors.append("daemon.export_target must be api, jsonl, sqlite, or console")
    if settings.daemon.export_target in {"jsonl", "sqlite"} and not settings.daemon.output_path:
        source_errors.append("daemon.output_path is required for daemon jsonl/sqlite export")
    if settings.daemon.export_target == "api" and not settings.daemon.allow_unattended_upload:
        warnings.append("daemon API export requires daemon.allow_unattended_upload=true at runtime")

    result = {
        "valid": not source_errors,
        "collector_mode": settings.collector.mode,
        "source_count": len(settings.sources),
        "sqlite_path": str(settings.state.sqlite_path),
        "allowed_paths": allowed_paths,
        "denied_patterns_active": len(settings.security.deny_patterns),
        "token_env": settings.api.token_env,
        "token_present": bool(os.getenv(settings.api.token_env)) if settings.api.token_env else False,
        "max_file_size_mb": settings.sync.max_file_size_mb,
        "daemon_export_target": settings.daemon.export_target,
        "daemon_health": f"{settings.daemon.health_host}:{settings.daemon.health_port}",
        "daemon_metrics": f"{settings.daemon.metrics_host}:{settings.daemon.metrics_port}",
        "warnings": warnings,
        "errors": source_errors,
    }
    if as_json:
        typer.echo(json.dumps(result, indent=2))
    else:
        for key, value in result.items():
            typer.echo(f"{key}: {value}")
    if source_errors:
        raise typer.Exit(code=1)
