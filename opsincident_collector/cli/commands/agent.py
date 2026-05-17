from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.agent.planner import build_investigation_plan
from opsincident_collector.agent.workflows import run_investigation_workflow
from opsincident_collector.config.loader import load_settings_optional

agent_app = typer.Typer(help="Agent commands.")


@agent_app.command("investigate")
def investigate(
    project_id: str = typer.Option(..., "--project-id"),
    query: str = typer.Option(..., "--query"),
    config: Path | None = typer.Option(None, "--config"),
    sync_if_stale: bool = typer.Option(False, "--sync-if-stale"),
    yes: bool = typer.Option(False, "--yes"),
) -> None:
    settings = load_settings_optional(config)
    plan = build_investigation_plan(settings, query)
    result = run_investigation_workflow(
        settings=settings,
        project_id=project_id,
        query=query,
        sync_if_stale=sync_if_stale,
        approved=yes,
    )
    typer.echo(json.dumps({"plan": plan, "result": result}, indent=2))
