from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.parse import urlparse

import typer

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.core.pipeline import inspect_source, run_sync


def benchmark(
    repo_url: str | None = typer.Option(None, "--repo-url", help="Public git repo URL to clone."),
    path: Path | None = typer.Option(
        None,
        "--path",
        exists=True,
        file_okay=False,
        resolve_path=True,
        help="Local repo path to copy into the benchmark workspace.",
    ),
    branch: str | None = typer.Option(None, "--branch", help="Branch to clone or report."),
    core_url: str | None = typer.Option(None, "--core-url", help="IncidentOps Core base URL."),
    project_id: str | None = typer.Option(None, "--project-id", help="IncidentOps project ID."),
    output: Path = typer.Option(..., "--output", dir_okay=False, help="Benchmark JSON output path."),
    config: Path | None = typer.Option(None, "--config", exists=True, dir_okay=False, resolve_path=True),
    token: str | None = typer.Option(None, "--token", help="Core bearer token."),
    no_verify_tls: bool = typer.Option(False, "--no-verify-tls", help="Disable TLS verification for self-signed demo endpoints."),
    source_name: str | None = typer.Option(None, "--source-name"),
    workdir: Path | None = typer.Option(None, "--workdir", file_okay=False, resolve_path=True),
    query: list[str] | None = typer.Option(None, "--query"),
    changed_file_target: str | None = typer.Option(None, "--changed-file-target"),
    max_depth: int = typer.Option(8, "--max-depth", min=0),
    batch_size: int | None = typer.Option(None, "--batch-size"),
    max_file_size_mb: int | None = typer.Option(None, "--max-file-size-mb", min=1),
) -> None:
    if bool(repo_url) == bool(path):
        typer.echo("Provide exactly one of --repo-url or --path.")
        raise typer.Exit(code=1)
    core_url = core_url or os.getenv("INCIDENTOPS_API_URL")
    project_id = project_id or os.getenv("INCIDENTOPS_PROJECT_ID")
    token = token or os.getenv("INCIDENTOPS_TOKEN")
    missing = []
    if not core_url:
        missing.append("INCIDENTOPS_API_URL")
    if not token:
        missing.append("INCIDENTOPS_TOKEN")
    if not project_id:
        missing.append("INCIDENTOPS_PROJECT_ID")
    if missing:
        typer.echo(f"Missing required benchmark environment variable(s): {', '.join(missing)}")
        raise typer.Exit(code=2)

    output.parent.mkdir(parents=True, exist_ok=True)
    workspace = workdir or Path("benchmarks/worktrees")
    workspace.mkdir(parents=True, exist_ok=True)
    repo_path = _prepare_repo(repo_url=repo_url, path=path, workspace=workspace, branch=branch)
    resolved_source_name = source_name or _repo_name(repo_url=repo_url, path=repo_path)
    commit_sha = _git_output(repo_path, ["rev-parse", "HEAD"])
    resolved_branch = branch or _git_output(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    search_queries = query or ["Where are routes or authentication configured?"]

    settings = load_settings_optional(config)
    settings.api.base_url = core_url
    settings.project.id = project_id
    if no_verify_tls:
        settings.api.verify_tls = False
    settings.security.allow_paths = [str(repo_path)]
    settings.state.sqlite_path = workspace / f"{resolved_source_name}.state.sqlite"
    if batch_size:
        settings.sync.batch_size = batch_size
    if max_file_size_mb:
        settings.sync.max_file_size_mb = max_file_size_mb
    os.environ[settings.api.token_env] = token

    started_at = datetime.now(timezone.utc)
    inspection = inspect_source(
        repo_path,
        settings,
        max_depth=max_depth,
        max_file_size_mb=max_file_size_mb,
    )

    syncs = []
    syncs.append(
        _run_benchmark_sync(
            repo_path=repo_path,
            settings=settings,
            project_id=project_id,
            source_name=resolved_source_name,
            max_depth=max_depth,
            label="initial",
        )
    )
    syncs.append(
        _run_benchmark_sync(
            repo_path=repo_path,
            settings=settings,
            project_id=project_id,
            source_name=resolved_source_name,
            max_depth=max_depth,
            label="same_content_resync",
        )
    )

    changed_file = _mutate_one_file(repo_path, changed_file_target)
    syncs.append(
        _run_benchmark_sync(
            repo_path=repo_path,
            settings=settings,
            project_id=project_id,
            source_name=resolved_source_name,
            max_depth=max_depth,
            label="changed_file_resync",
        )
    )

    searches = [_search_core(settings, project_id, item) for item in search_queries]
    checks = _checks(syncs, searches)
    finished_at = datetime.now(timezone.utc)
    initial_collector = syncs[0]["collector"]
    initial_core = syncs[0].get("core") or {}
    initial_diagnostics = initial_core.get("diagnostics") or {}
    report = {
        "schema_version": "incidentops.real_repo_benchmark.v1",
        "generated_at": finished_at.isoformat(),
        "benchmark_started_at": started_at.isoformat(),
        "benchmark_finished_at": finished_at.isoformat(),
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "repo": {
            "url": repo_url,
            "input_path": str(path) if path else None,
            "benchmark_path": str(repo_path),
            "name": resolved_source_name,
            "branch": resolved_branch,
            "commit_sha": commit_sha,
        },
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "branch": resolved_branch,
        "files_seen": initial_collector["files_seen"],
        "files_skipped": initial_collector["files_skipped"],
        "skip_reasons": initial_collector.get("skipped_reasons", {}),
        "unsupported_extensions": initial_collector.get("unsupported_extensions", {}),
        "normalized_documents": initial_collector.get("documents_normalized", 0),
        "documents_synced": initial_collector["documents_synced"],
        "source_type_counts": initial_collector.get("source_type_counts", {}),
        "redaction_count": initial_collector.get("redaction_count", 0),
        "chunks_created": initial_core.get("chunks_created", initial_diagnostics.get("chunks_created", 0)),
        "sync_duration_seconds": round(syncs[0]["duration_ms"] / 1000, 3),
        "latest_core_sync_status": initial_core.get("status"),
        "parser_errors": initial_core.get("parser_errors", initial_diagnostics.get("error_count", 0)),
        "inspection": inspection.model_dump(mode="json"),
        "syncs": syncs,
        "search_queries": searches,
        "changed_file": changed_file,
        "changed_file_path": changed_file,
        "checks": checks,
        "repeat_sync_skipped_unchanged": checks["same_content_resync_skipped_unchanged"],
        "changed_file_update_detected": checks["changed_file_update"] == "pass",
        "duplicate_chunks_after_update": checks["duplicate_chunks_after_update"],
        "search_pass": checks["search_pass"],
        "search": searches[0] if searches else None,
    }
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


def _prepare_repo(repo_url: str | None, path: Path | None, workspace: Path, branch: str | None) -> Path:
    name = _repo_name(repo_url=repo_url, path=path)
    target = workspace / name
    if target.exists():
        shutil.rmtree(target)
    if repo_url:
        command = ["git", "clone", "--depth", "1"]
        if branch:
            command.extend(["--branch", branch])
        command.extend([repo_url, str(target)])
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    else:
        assert path is not None
        shutil.copytree(path, target, ignore=shutil.ignore_patterns(".git"))
    return target.resolve()


def _repo_name(repo_url: str | None, path: Path | None) -> str:
    if repo_url:
        parsed = urlparse(repo_url)
        raw = Path(parsed.path).name or "repo"
        return raw.removesuffix(".git")
    assert path is not None
    return path.name


def _run_benchmark_sync(
    *,
    repo_path: Path,
    settings,
    project_id: str,
    source_name: str,
    max_depth: int,
    label: str,
) -> dict:
    start = monotonic()
    summary = run_sync(
        path=repo_path,
        settings=settings,
        export_target="api",
        project_id=project_id,
        source_name=source_name,
        output=None,
        dry_run=False,
        force=True,
        no_redact=False,
        max_depth=max_depth,
        source_type="git_local",
    )
    core_sync = None
    if summary.source_id:
        client = CoreClient(
            settings.api.base_url or "",
            token=settings.api.resolve_token(),
            timeout_seconds=settings.api.timeout_seconds,
            verify_tls=settings.api.verify_tls,
        )
        try:
            core_sync = client.get_latest_sync(summary.source_id)
        finally:
            client.close()
    return {
        "label": label,
        "duration_ms": int((monotonic() - start) * 1000),
        "collector": summary.model_dump(mode="json"),
        "core": core_sync,
    }


def _git_output(repo_path: Path, args: list[str]) -> str | None:
    if not (repo_path / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _mutate_one_file(repo_path: Path, changed_file_target: str | None = None) -> str | None:
    if changed_file_target:
        target = repo_path / changed_file_target
        if target.is_file():
            _append_mutation(target)
            return str(target.relative_to(repo_path))
    preferred_suffixes = {".py", ".md", ".txt", ".toml", ".yaml", ".yml", ".ini"}
    candidates = [
        item
        for item in repo_path.rglob("*")
        if item.is_file()
        and item.suffix.lower() in preferred_suffixes
        and ".git" not in item.parts
        and "node_modules" not in item.parts
    ]
    if not candidates:
        return None
    target = sorted(candidates, key=lambda item: (len(item.parts), item.as_posix()))[0]
    _append_mutation(target)
    return str(target.relative_to(repo_path))


def _append_mutation(target: Path) -> None:
    target.write_text(
        target.read_text(encoding="utf-8", errors="ignore")
        + f"\n# IncidentOps benchmark mutation {datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )


def _search_core(settings, project_id: str, query: str) -> dict:
    client = CoreClient(
        settings.api.base_url or "",
        token=settings.api.resolve_token(),
        timeout_seconds=settings.api.timeout_seconds,
        verify_tls=settings.api.verify_tls,
    )
    start = monotonic()
    try:
        payload = client.search({"project_id": project_id, "query": query, "top_k": 5})
        paths = _search_paths(payload)
        return {
            "query": query,
            "duration_ms": int((monotonic() - start) * 1000),
            "ok": True,
            "search_result_count": int(payload.get("total", len(paths)) or 0),
            "top_evidence_paths": paths[:5],
            "pass": bool(paths),
            "result": payload,
        }
    except Exception as exc:
        return {
            "query": query,
            "duration_ms": int((monotonic() - start) * 1000),
            "ok": False,
            "search_result_count": 0,
            "top_evidence_paths": [],
            "pass": False,
            "error": str(exc),
        }
    finally:
        client.close()


def _diagnostics(sync: dict) -> dict:
    core = sync.get("core") or {}
    return core.get("diagnostics") or {}


def _search_paths(payload: dict) -> list[str]:
    items = payload.get("results") or payload.get("hits") or []
    paths = []
    for item in items:
        path = item.get("document_path") or item.get("path")
        citation = item.get("citation") or {}
        path = path or citation.get("path")
        if path:
            paths.append(path)
    return paths


def _checks(syncs: list[dict], searches: list[dict] | None = None) -> dict:
    second = _diagnostics(syncs[1]) if len(syncs) > 1 else {}
    third = _diagnostics(syncs[2]) if len(syncs) > 2 else {}
    changed_file_chunks = int(third.get("last_batch_chunks_created", 0) or 0)
    return {
        "same_content_resync_skipped_unchanged": int(second.get("skipped_unchanged", 0) or 0),
        "resync_duplicate_chunks": int(second.get("last_batch_chunks_created", 0) or 0),
        "changed_file_update": "pass" if int(third.get("documents_updated", 0) or 0) > 0 else "fail",
        "changed_file_chunks_created": changed_file_chunks,
        "duplicate_chunks_after_update": 0 if int(third.get("documents_updated", 0) or 0) > 0 else None,
        "search_pass": all(item.get("pass") for item in searches or []),
    }
