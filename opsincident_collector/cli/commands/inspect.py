from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.pipeline import inspect_source


def inspect(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    output_format: str = typer.Option("table", "--format", help="table or json"),
    max_depth: int = typer.Option(8, "--max-depth", min=0),
    max_file_size_mb: int | None = typer.Option(None, "--max-file-size-mb", min=1),
    include: list[str] | None = typer.Option(None, "--include"),
    exclude: list[str] | None = typer.Option(None, "--exclude"),
    strict: bool = typer.Option(False, "--strict", help="Fail on warnings."),
) -> None:
    settings = load_settings_optional(config)
    inspection = inspect_source(
        path=path,
        settings=settings,
        max_depth=max_depth,
        max_file_size_mb=max_file_size_mb,
        include=include or [],
        exclude=exclude or [],
    )
    if output_format == "json":
        typer.echo(json.dumps(inspection.model_dump(mode="json"), indent=2))
    else:
        typer.echo(f"path: {inspection.path}")
        typer.echo(f"total_files: {inspection.total_files}")
        typer.echo(f"supported_files: {inspection.supported_files}")
        typer.echo(f"unsupported_files: {inspection.unsupported_files}")
        typer.echo(f"oversized_files: {inspection.oversized_files}")
        typer.echo(f"denied_files: {inspection.denied_files}")
        typer.echo(f"empty_files: {inspection.empty_files}")
        typer.echo(f"possible_secrets_detected: {inspection.possible_secrets_detected}")
        typer.echo(f"likely_source_types: {json.dumps(inspection.likely_source_types, sort_keys=True)}")
        if inspection.warnings:
            typer.echo("warnings:")
            for warning in inspection.warnings:
                typer.echo(f"- {warning}")
        if inspection.skipped_files:
            typer.echo("skipped_files:")
            for skipped in inspection.skipped_files[:20]:
                typer.echo(f"- {skipped.path}: {skipped.reason}")
    if strict and inspection.warnings:
        raise typer.Exit(code=1)
