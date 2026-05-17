from __future__ import annotations

from pathlib import Path

import typer

from opsincident_collector.config.loader import DEFAULT_CONFIG_TEMPLATE


def init(
    config_path: Path = typer.Option(Path("collector.yaml"), "--config", help="Config file path."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    if config_path.exists() and not force:
        typer.echo(f"Config already exists: {config_path}")
        raise typer.Exit(code=1)

    state_dir = Path(".opsincident-collector")
    state_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = state_dir / "state.sqlite"
    sqlite_path.touch(exist_ok=True)
    config_path.write_text(DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    typer.echo(f"Initialized {config_path}")
    typer.echo(f"State directory ready at {state_dir}")
