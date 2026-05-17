from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import typer

warnings.filterwarnings("ignore", message=r".*allowed_objects.*", category=Warning)

from opsincident_collector.langgraph_agent.reports.markdown import graph_report_to_markdown
from opsincident_collector.langgraph_agent.runner import (
    LangGraphUnavailableError,
    approve_action,
    run_graph,
)

agent_app = typer.Typer(
    help=(
        "LangGraph orchestration commands. The Collector orchestrates setup, readiness, "
        "sync, and Core bridge workflows only; it does not diagnose incidents locally."
    )
)


@agent_app.command("onboard-source")
def onboard_source(
    path: Path | None = typer.Option(
        None,
        "--path",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    project_id: str | None = typer.Option(None, "--project-id"),
    export_target: str = typer.Option("api", "--export-target"),
    output: Path | None = typer.Option(None, "--output"),
    config: Path | None = typer.Option(None, "--config"),
    run_id: str | None = typer.Option(None, "--run-id"),
    resume: bool = typer.Option(False, "--resume"),
    approve: str | None = typer.Option(None, "--approve"),
    reject: str | None = typer.Option(None, "--reject"),
    output_format: str = typer.Option("table", "--format"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    _require_new_run_value(path, "--path", resume=resume, approve=approve, reject=reject)
    state = {
        "path": str(path) if path else None,
        "project_id": project_id,
        "config_path": str(config) if config else None,
        "export_target": export_target,
        "output": str(output) if output else None,
        "dry_run": dry_run,
        "approved": yes,
        "require_approval": True,
    }
    result = _run_or_decide(
        graph_name="source_onboarding",
        state=state,
        config=config,
        run_id=run_id,
        resume=resume,
        approve=approve,
        reject=reject,
    )
    _emit(result, output_format)


@agent_app.command("rag-readiness")
def rag_readiness(
    path: Path | None = typer.Option(
        None,
        "--path",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    config: Path | None = typer.Option(None, "--config"),
    run_id: str | None = typer.Option(None, "--run-id"),
    resume: bool = typer.Option(False, "--resume"),
    output_format: str = typer.Option("table", "--format"),
) -> None:
    _require_new_run_value(path, "--path", resume=resume)
    result = _run_or_decide(
        graph_name="rag_readiness",
        state={"path": str(path) if path else None, "config_path": str(config) if config else None},
        config=config,
        run_id=run_id,
        resume=resume,
    )
    _emit(result, output_format)


@agent_app.command("sync-quality")
def sync_quality(
    path: Path | None = typer.Option(
        None,
        "--path",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    project_id: str | None = typer.Option(None, "--project-id"),
    config: Path | None = typer.Option(None, "--config"),
    run_id: str | None = typer.Option(None, "--run-id"),
    resume: bool = typer.Option(False, "--resume"),
    output_format: str = typer.Option("table", "--format"),
) -> None:
    _require_new_run_value(path, "--path", resume=resume)
    result = _run_or_decide(
        graph_name="sync_quality",
        state={
            "path": str(path) if path else None,
            "project_id": project_id,
            "config_path": str(config) if config else None,
        },
        config=config,
        run_id=run_id,
        resume=resume,
    )
    _emit(result, output_format)


@agent_app.command("investigate")
def investigate(
    project_id: str | None = typer.Option(None, "--project-id"),
    query: str | None = typer.Option(None, "--query"),
    path: Path | None = typer.Option(
        None,
        "--path",
        exists=True,
        file_okay=False,
        resolve_path=True,
    ),
    config: Path | None = typer.Option(None, "--config"),
    top_k: int | None = typer.Option(None, "--top-k"),
    debug: bool = typer.Option(False, "--debug"),
    run_id: str | None = typer.Option(None, "--run-id"),
    resume: bool = typer.Option(False, "--resume"),
    approve: str | None = typer.Option(None, "--approve"),
    reject: str | None = typer.Option(None, "--reject"),
    output_format: str = typer.Option("table", "--format"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    _require_new_run_value(
        project_id,
        "--project-id",
        resume=resume,
        approve=approve,
        reject=reject,
    )
    _require_new_run_value(query, "--query", resume=resume, approve=approve, reject=reject)
    result = _run_or_decide(
        graph_name="investigation_bridge",
        state={
            "path": str(path) if path else None,
            "project_id": project_id,
            "query": query,
            "config_path": str(config) if config else None,
            "top_k": top_k,
            "debug": debug,
            "export_target": "api",
            "dry_run": dry_run,
            "approved": yes,
            "sync_approved": yes,
            "require_approval": True,
        },
        config=config,
        run_id=run_id,
        resume=resume,
        approve=approve,
        reject=reject,
    )
    _emit(result, output_format)


def _run_or_decide(
    *,
    graph_name: str,
    state: dict[str, Any],
    config: Path | None,
    run_id: str | None,
    resume: bool,
    approve: str | None = None,
    reject: str | None = None,
) -> dict[str, Any]:
    try:
        if approve or reject:
            approval = approve_action(
                approve or reject or "",
                config_path=config,
                approved=bool(approve),
            )
            if reject:
                return approval["state"]
            return run_graph(
                approval["approval"]["graph_name"],
                {},
                config_path=config,
                resume_run_id=approval["approval"]["run_id"],
            )
        return run_graph(
            graph_name,
            state,
            config_path=config,
            resume_run_id=run_id if resume else None,
        )
    except LangGraphUnavailableError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _require_new_run_value(
    value: Any,
    option_name: str,
    *,
    resume: bool = False,
    approve: str | None = None,
    reject: str | None = None,
) -> None:
    if value is None and not (resume or approve or reject):
        typer.echo(f"{option_name} is required for a new graph run")
        raise typer.Exit(code=1)


def _emit(state: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        typer.echo(json.dumps(state, indent=2, default=str))
        return
    typer.echo(graph_report_to_markdown(state))
    approval = state.get("approval_request") or {}
    if state.get("status") == "pending_approval" and approval.get("approval_id"):
        typer.echo("")
        typer.echo(f"approval_id: {approval['approval_id']}")
        typer.echo(
            "resume: opsincident-collector agent onboard-source "
            f"--approve {approval['approval_id']}"
        )
