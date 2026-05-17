from __future__ import annotations

import json
import os

import typer

from opsincident_collector.adapters.core_contract_validator import validate_core_contract as run_validation


def validate_core_contract(
    api_url: str = typer.Option(..., "--api-url"),
    project_id: str = typer.Option(..., "--project-id"),
    token_env: str = typer.Option("INCIDENTOPS_TOKEN", "--token-env"),
    token: str | None = typer.Option(None, "--token"),
    with_sample: bool = typer.Option(False, "--with-sample"),
    output_format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    resolved_token = token or os.getenv(token_env)
    report = run_validation(
        api_url=api_url,
        project_id=project_id,
        token=resolved_token,
        with_sample=with_sample,
    )
    if output_format == "json":
        typer.echo(json.dumps(report, indent=2))
    else:
        typer.echo(f"api_url: {report['api_url']}")
        typer.echo(f"compatible: {report['compatible']}")
        typer.echo(f"capabilities_available: {report['capabilities_available']}")
        typer.echo(f"sample_uploaded: {report['sample_uploaded']}")
        typer.echo(f"supported_features: {json.dumps(report.get('supported_features', {}), sort_keys=True)}")
        if report["warnings"]:
            typer.echo("warnings:")
            for warning in report["warnings"]:
                typer.echo(f"- {warning}")
        if report["errors"]:
            typer.echo("errors:")
            for error in report["errors"]:
                typer.echo(f"- {error}")
    if not report["compatible"]:
        raise typer.Exit(code=1)
