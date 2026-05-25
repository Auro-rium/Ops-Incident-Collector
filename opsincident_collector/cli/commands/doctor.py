from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.loader import find_config_path, load_settings
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version
from opsincident_collector.state.sqlite_store import SQLiteStore


def _check_state_writable(path: Path) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8"):
            return True
    except OSError:
        return False


def doctor(
    config: Path | None = typer.Option(None, "--config", help="Config file path."),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    config_path = config or find_config_path()
    rows: list[dict[str, str]] = []
    rows.append(
        {
            "check": "python_version",
            "status": "ok" if sys.version_info >= (3, 11) else "fail",
            "detail": sys.version.split()[0],
        }
    )
    rows.append({"check": "collector_version", "status": "ok", "detail": collector_version()})
    rows.append({"check": "schema_version", "status": "ok", "detail": SCHEMA_VERSION})
    rows.append({"check": "core_api_version", "status": "ok", "detail": CORE_API_VERSION})
    rows.append(
        {
            "check": "config_found",
            "status": "ok" if config_path and config_path.exists() else "warn",
            "detail": str(config_path) if config_path else "not found",
        }
    )

    settings = None
    if config_path and config_path.exists():
        try:
            settings = load_settings(config_path)
            rows.append({"check": "config_parse", "status": "ok", "detail": "loaded"})
        except Exception as exc:  # pragma: no cover
            rows.append({"check": "config_parse", "status": "fail", "detail": str(exc)})

    if settings:
        rows.append(
            {
                "check": "state_writable",
                "status": "ok" if _check_state_writable(settings.state.sqlite_path) else "fail",
                "detail": str(settings.state.sqlite_path),
            }
        )
        api_url = settings.api.base_url or os.getenv("INCIDENTOPS_API_URL")
        rows.append(
            {
                "check": "core_url",
                "status": "ok" if api_url else "warn",
                "detail": api_url or "not configured",
            }
        )
        token = settings.api.resolve_token()
        rows.append(
            {
                "check": "api_token",
                "status": "ok" if token else "warn",
                "detail": "present" if token else f"{settings.api.token_env}=unset",
            }
        )
        if api_url:
            client = None
            try:
                client = CoreClient(api_url, token=token, timeout_seconds=settings.api.timeout_seconds, verify_tls=settings.api.verify_tls)
                health = client.health()
                rows.append({"check": "api_health", "status": "ok", "detail": json.dumps(health)})
            except Exception as exc:
                rows.append({"check": "api_health", "status": "warn", "detail": str(exc)})
            finally:
                if client:
                    client.close()
        allowlist_ok = all(Path(p).expanduser() for p in settings.security.allow_paths)
        rows.append(
            {
                "check": "path_allowlist",
                "status": "ok" if allowlist_ok else "fail",
                "detail": ", ".join(settings.security.allow_paths) or "empty",
            }
        )
        if settings.state.sqlite_path.exists():
            store = SQLiteStore(settings.state.sqlite_path)
            try:
                rows.append(
                    {
                        "check": "retry_queue_depth",
                        "status": "ok",
                        "detail": str(store.failed_upload_queue_depth()),
                    }
                )
            finally:
                store.close()
        else:
            rows.append({"check": "retry_queue_depth", "status": "ok", "detail": "0"})
    else:
        rows.append({"check": "state_writable", "status": "warn", "detail": "config required"})

    if as_json:
        typer.echo(json.dumps(rows, indent=2))
        return

    for row in rows:
        typer.echo(f"{row['check']:<18} {row['status']:<5} {row['detail']}")
