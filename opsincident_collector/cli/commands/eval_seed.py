from __future__ import annotations

import json
from pathlib import Path

import typer

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.analysis import generate_eval_seed_cases, write_eval_seed_jsonl


def eval_seed(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    output: Path = typer.Option(..., "--output", dir_okay=False),
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    output_format: str = typer.Option("table", "--format", help="table or json"),
    max_depth: int = typer.Option(8, "--max-depth", min=0),
) -> None:
    settings = load_settings_optional(config)
    cases = generate_eval_seed_cases(path, settings, max_depth=max_depth)
    write_eval_seed_jsonl(cases, output)
    payload = {
        "output": str(output),
        "case_count": len(cases),
        "case_ids": [case.id for case in cases],
    }
    if output_format == "json":
        typer.echo(json.dumps(payload, indent=2))
    else:
        typer.echo(f"output: {output}")
        typer.echo(f"case_count: {len(cases)}")
        for case in cases:
            typer.echo(f"- {case.id}: {case.question}")
