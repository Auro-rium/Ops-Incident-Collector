from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.analysis import build_rag_readiness_report


def rag_report(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    output_format: str = typer.Option("table", "--format", help="table or json"),
    max_depth: int = typer.Option(8, "--max-depth", min=0),
) -> None:
    settings = load_settings_optional(config)
    report = build_rag_readiness_report(path, settings, max_depth=max_depth)
    if output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
        return

    typer.echo(f"score: {report.score}")
    typer.echo(f"grade: {report.grade}")
    typer.echo(f"ready_for_core_sync: {report.ready_for_core_sync}")
    typer.echo(f"ready_for_investigation: {report.ready_for_investigation}")
    typer.echo(f"estimated_document_count: {report.estimated_document_count}")
    typer.echo(f"estimated_metadata_quality: {report.estimated_metadata_quality}")
    if report.strengths:
        typer.echo("strengths:")
        for strength in report.strengths:
            typer.echo(f"- {strength}")
    if report.weaknesses:
        typer.echo("weaknesses:")
        for weakness in report.weaknesses:
            typer.echo(f"- {weakness}")
    if report.recommended_next_sources:
        typer.echo(f"recommended_next_sources: {', '.join(report.recommended_next_sources)}")
