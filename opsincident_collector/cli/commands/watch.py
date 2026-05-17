from __future__ import annotations

import json
import signal
import time
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.pipeline import run_sync


def watch(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    project_id: str | None = typer.Option(None, "--project-id"),
    config: Path | None = typer.Option(None, "--config"),
    interval_seconds: int = typer.Option(30, "--interval-seconds", min=1),
    dry_run: bool = typer.Option(False, "--dry-run"),
    export: str = typer.Option("jsonl", "--export"),
    output: Path | None = typer.Option(None, "--output"),
    yes: bool = typer.Option(False, "--yes"),
    max_cycles: int | None = typer.Option(None, "--max-cycles", hidden=True),
) -> None:
    settings = load_settings_optional(config)
    if project_id:
        settings.project.id = project_id
    if export == "api" and settings.security.require_confirmation_for_upload and not (yes or dry_run):
        typer.echo("Refusing API watch sync without confirmation. Re-run with --yes or --dry-run.")
        raise typer.Exit(code=1)

    running = True

    def _stop(*_args):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    cycles = 0
    while running:
        try:
            summary = run_sync(
                path=path,
                settings=settings,
                export_target=export,
                project_id=settings.project.id,
                source_name=path.name,
                output=output,
                dry_run=dry_run,
                force=False,
                no_redact=False,
            )
        except ValueError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        typer.echo(json.dumps(summary.model_dump(mode="json")))
        cycles += 1
        if max_cycles is not None and cycles >= max_cycles:
            break
        time.sleep(interval_seconds)
