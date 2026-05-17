from __future__ import annotations

import json
from pathlib import Path

import httpx
import typer

from opsincident_collector.config.loader import load_settings
from opsincident_collector.daemon.service import DaemonService, DaemonStartupError

daemon_app = typer.Typer(
    help=(
        "Run the Collector as a long-lived edge service with periodic sync, "
        "health, metrics, and graceful shutdown."
    )
)


@daemon_app.command("run")
def run_daemon(
    config: Path = typer.Option(..., "--config", exists=True, dir_okay=False, resolve_path=True),
    max_cycles: int | None = typer.Option(None, "--max-cycles", min=1),
    run_once: bool = typer.Option(False, "--run-once"),
    output_format: str = typer.Option("json", "--format", help="json or table"),
) -> None:
    settings = load_settings(config)
    service = DaemonService(
        settings,
        config_path=config,
        max_cycles=max_cycles,
        run_once=run_once or bool(max_cycles == 1),
    )
    try:
        payload = service.run()
    except DaemonStartupError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            typer.echo(f"{key}: {value}")
    if payload.get("status") == "error":
        raise typer.Exit(code=1)


@daemon_app.command("health")
def health(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8686, "--port"),
    timeout_seconds: float = typer.Option(2.0, "--timeout-seconds"),
    output_format: str = typer.Option("json", "--format", help="json or table"),
) -> None:
    url = f"http://{host}:{port}/health"
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        typer.echo(f"daemon health check failed: {exc}")
        raise typer.Exit(code=1) from exc
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            typer.echo(f"{key}: {value}")
    if payload.get("status") == "error":
        raise typer.Exit(code=1)

