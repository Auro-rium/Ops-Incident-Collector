from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.adapters.core_contract_validator import validate_core_contract
from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.analysis import (
    build_rag_readiness_report,
    build_source_coverage_report,
    collect_normalized_documents,
)
from opsincident_collector.core.pipeline import inspect_source, run_sync
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version
from opsincident_collector.processors.path_policy import ensure_path_allowed


def validate_rag_pipeline(
    path: Path = typer.Option(..., "--path", exists=True, file_okay=False, resolve_path=True),
    project_id: str | None = typer.Option(None, "--project-id"),
    api_url: str | None = typer.Option(None, "--api-url"),
    query: str = typer.Option("What evidence is available?", "--query"),
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False, resolve_path=True),
    token_env: str = typer.Option("INCIDENTOPS_TOKEN", "--token-env"),
    token: str | None = typer.Option(None, "--token"),
    sync: bool = typer.Option(False, "--sync"),
    search: bool = typer.Option(False, "--search"),
    investigate: bool = typer.Option(False, "--investigate"),
    output_format: str = typer.Option("table", "--format", help="table or json"),
) -> None:
    settings = load_settings_optional(config)
    if api_url:
        settings.api.base_url = api_url
    if project_id:
        settings.project.id = project_id
    if token:
        settings.api.token = token
    elif token_env:
        settings.api.token_env = token_env

    report = _build_report(
        path=path,
        settings=settings,
        query=query,
        sync=sync,
        search=search,
        investigate=investigate,
    )
    if output_format == "json":
        typer.echo(json.dumps(report, indent=2))
    else:
        for key, value in report.items():
            if key in {"warnings", "errors"}:
                typer.echo(f"{key}:")
                for item in value:
                    typer.echo(f"- {item}")
            else:
                typer.echo(f"{key}: {value}")
    if report["errors"]:
        raise typer.Exit(code=1)


def _build_report(
    *,
    path: Path,
    settings,
    query: str,
    sync: bool,
    search: bool,
    investigate: bool,
) -> dict:
    warnings: list[str] = []
    errors: list[str] = []
    collector_ready = False
    core_ready = False
    documents_synced = 0
    search_test_passed = False
    investigation_test_passed = False

    try:
        ensure_path_allowed(path.resolve(), settings.security.allow_paths)
        inspection = inspect_source(path=path, settings=settings)
        coverage = build_source_coverage_report(path, settings)
        readiness = build_rag_readiness_report(path, settings)
        documents = collect_normalized_documents(path, settings)
        collector_ready = bool(documents) and readiness.ready_for_core_sync
    except Exception as exc:
        inspection = None
        coverage = None
        readiness = None
        documents = []
        errors.append(f"collector validation failed: {exc}")

    core_contract = None
    if settings.api.base_url and settings.project.id:
        resolved_token = settings.api.resolve_token() or os.getenv(settings.api.token_env)
        core_contract = validate_core_contract(
            api_url=settings.api.base_url,
            project_id=settings.project.id,
            token=resolved_token,
            with_sample=False,
        )
        core_ready = bool(core_contract.get("compatible"))
        warnings.extend(core_contract.get("warnings") or [])
        if core_contract.get("errors"):
            warnings.extend(core_contract["errors"])
    elif search or investigate or sync:
        errors.append("Core operations require --api-url and --project-id")

    if sync and not errors:
        try:
            summary = run_sync(
                path=path,
                settings=settings,
                export_target="api",
                project_id=settings.project.id,
                source_name=path.name,
                output=None,
                dry_run=False,
                force=True,
            )
            documents_synced = summary.documents_synced
            warnings.extend(summary.warnings)
            errors.extend(summary.errors)
        except Exception as exc:
            errors.append(f"sync failed: {exc}")

    if (search or investigate) and settings.api.base_url and settings.project.id and not errors:
        client = CoreClient(
            settings.api.base_url,
            token=settings.api.resolve_token(),
            timeout_seconds=settings.api.timeout_seconds,
            verify_tls=settings.api.verify_tls,
        )
        try:
            if search:
                client.search({"project_id": settings.project.id, "query": query, "top_k": 5})
                search_test_passed = True
            if investigate:
                client.investigate({"project_id": settings.project.id, "query": query, "top_k": 5})
                investigation_test_passed = True
        except Exception as exc:
            errors.append(f"Core smoke test failed: {exc}")
        finally:
            client.close()

    rag_score = readiness.score if readiness else 0.0
    return {
        "pipeline_ready": collector_ready and (core_ready or not settings.api.base_url) and not errors,
        "collector_ready": collector_ready,
        "core_ready": core_ready,
        "collector_version": collector_version(),
        "schema_version": SCHEMA_VERSION,
        "core_api_version": CORE_API_VERSION,
        "rag_readiness_score": rag_score,
        "rag_readiness_grade": readiness.grade if readiness else None,
        "documents_prepared": len(documents),
        "documents_synced": documents_synced,
        "search_test_passed": search_test_passed,
        "investigation_test_passed": investigation_test_passed,
        "coverage": coverage.model_dump(mode="json") if coverage else None,
        "inspection": inspection.model_dump(mode="json") if inspection else None,
        "core_contract": core_contract,
        "warnings": warnings,
        "errors": errors,
    }
