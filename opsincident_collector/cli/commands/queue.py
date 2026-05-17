from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.queue import clear_queue, get_queue_status, retry_queue

queue_app = typer.Typer(help="Inspect and operate the failed-upload retry queue.")


@queue_app.command("status")
def status(
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False, resolve_path=True),
    output_format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    settings = load_settings_optional(config)
    payload = get_queue_status(settings)
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"pending_count: {payload['pending_count']}")
    typer.echo(f"exhausted_count: {payload['exhausted_count']}")
    typer.echo(f"total_count: {payload['total_count']}")
    typer.echo(f"next_retry_at: {payload['next_retry_at']}")
    typer.echo(f"oldest_failed_upload: {payload['oldest_failed_upload']}")
    typer.echo(f"by_source: {json.dumps(payload['by_source'], sort_keys=True)}")


@queue_app.command("retry")
def retry(
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False, resolve_path=True),
    project_id: str | None = typer.Option(None, "--project-id"),
    source_name: str | None = typer.Option(None, "--source-name"),
    output_format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    settings = load_settings_optional(config)
    try:
        payload = retry_queue(settings, project_id=project_id, source_name=source_name)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"retried_sources: {len(payload['summaries'])}")
    typer.echo(f"pending_count: {payload['queue']['pending_count']}")
    typer.echo(f"exhausted_count: {payload['queue']['exhausted_count']}")


@queue_app.command("clear")
def clear(
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False, resolve_path=True),
    failed_before_days: int = typer.Option(..., "--failed-before", min=0),
    yes: bool = typer.Option(False, "--yes"),
    output_format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    if not yes:
        typer.echo("Refusing to clear queue without --yes.")
        raise typer.Exit(code=1)
    settings = load_settings_optional(config)
    payload = clear_queue(settings, failed_before_days=failed_before_days)
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
        return
    typer.echo(f"cleared: {payload['cleared']}")
    typer.echo(f"remaining: {payload['queue']['total_count']}")

