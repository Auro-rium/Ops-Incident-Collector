from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.pipeline import run_sync


def sync(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    project_id: str | None = typer.Option(None, "--project-id"),
    source_name: str | None = typer.Option(None, "--source-name"),
    source_type: str = typer.Option("filesystem", "--source-type"),
    api_url: str | None = typer.Option(None, "--api-url"),
    token: str | None = typer.Option(None, "--token"),
    config: Path | None = typer.Option(None, "--config"),
    export: str = typer.Option("jsonl", "--export"),
    output: Path | None = typer.Option(None, "--output"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    yes: bool = typer.Option(False, "--yes"),
    force: bool = typer.Option(False, "--force"),
    batch_size: int | None = typer.Option(None, "--batch-size"),
    max_file_size_mb: int | None = typer.Option(None, "--max-file-size-mb"),
    no_redact: bool = typer.Option(False, "--no-redact"),
) -> None:
    settings = load_settings_optional(config)
    if api_url:
        settings.api.base_url = api_url
    if token:
        import os

        os.environ[settings.api.token_env] = token
    if project_id:
        settings.project.id = project_id
    if batch_size:
        settings.sync.batch_size = batch_size
    if max_file_size_mb:
        settings.sync.max_file_size_mb = max_file_size_mb
    if export == "api" and settings.security.require_confirmation_for_upload and not (yes or dry_run):
        typer.echo("Refusing API sync without confirmation. Re-run with --yes or --dry-run.")
        raise typer.Exit(code=1)

    try:
        summary = run_sync(
            path=path,
            settings=settings,
            export_target=export,
            project_id=settings.project.id,
            source_name=source_name or path.name,
            output=output,
            dry_run=dry_run,
            force=force,
            no_redact=no_redact,
            source_type=source_type,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(summary.model_dump(mode="json"), indent=2))
