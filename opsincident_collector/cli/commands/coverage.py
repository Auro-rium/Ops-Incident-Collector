from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.analysis import build_source_coverage_report


def coverage(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    output_format: str = typer.Option("table", "--format", help="table or json"),
    max_depth: int = typer.Option(8, "--max-depth", min=0),
) -> None:
    settings = load_settings_optional(config)
    report = build_source_coverage_report(path, settings, max_depth=max_depth)
    if output_format == "json":
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
        return

    typer.echo(f"document_count: {report.document_count}")
    typer.echo(f"source_type_counts: {json.dumps(report.source_type_counts, sort_keys=True)}")
    typer.echo(f"has_logs: {report.has_logs}")
    typer.echo(f"has_code: {report.has_code}")
    typer.echo(f"has_deploys: {report.has_deploys}")
    typer.echo(f"has_incidents: {report.has_incidents}")
    typer.echo(f"has_runbooks: {report.has_runbooks}")
    typer.echo(f"has_api_docs: {report.has_api_docs}")
    if report.missing_recommended_sources:
        typer.echo(f"missing_recommended_sources: {', '.join(report.missing_recommended_sources)}")
    if report.warnings:
        typer.echo("warnings:")
        for warning in report.warnings:
            typer.echo(f"- {warning}")
