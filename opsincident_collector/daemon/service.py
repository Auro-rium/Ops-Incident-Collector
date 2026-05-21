from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from opsincident_collector.adapters.core_client import CoreClient
from opsincident_collector.config.settings import AppSettings, SourceConfig
from opsincident_collector.core.logging import configure_logging
from opsincident_collector.core.models import SyncSummary
from opsincident_collector.core.pipeline import API_TOKEN_REQUIRED_MESSAGE, run_sync
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version
from opsincident_collector.daemon.health import HealthServer
from opsincident_collector.daemon.metrics import MetricsServer
from opsincident_collector.daemon.scheduler import next_interval_seconds
from opsincident_collector.daemon.signals import install_signal_handlers
from opsincident_collector.processors.path_policy import ensure_path_allowed
from opsincident_collector.state.sqlite_store import SQLiteStore


class DaemonStartupError(RuntimeError):
    pass


@dataclass
class DaemonRuntimeState:
    daemon_started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    running: bool = False
    permanent_error: bool = False
    last_successful_sync: str | None = None
    last_failed_sync: str | None = None
    last_sync_status: str | None = None
    last_error: str | None = None
    last_summary: dict[str, Any] | None = None
    core_reachable: bool | None = None
    state_db_writable: bool = True
    cycles_completed: int = 0
    totals: dict[str, float] = field(
        default_factory=lambda: {
            "files_seen": 0,
            "files_synced": 0,
            "files_skipped": 0,
            "documents_synced": 0,
            "redactions": 0,
            "failed_uploads": 0,
            "sync_duration_seconds": 0.0,
            "rag_readiness_score": 0.0,
        }
    )


class DaemonService:
    def __init__(
        self,
        settings: AppSettings,
        *,
        config_path: Path,
        max_cycles: int | None = None,
        run_once: bool | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.settings = settings
        self.config_path = config_path
        self.max_cycles = max_cycles if max_cycles is not None else settings.daemon.max_cycles
        self.run_once = settings.daemon.run_once if run_once is None else run_once
        self.stop_event = stop_event or threading.Event()
        self.state = DaemonRuntimeState()
        self.health_server: HealthServer | None = None
        self.metrics_server: MetricsServer | None = None
        self.log = structlog.get_logger("opsincident_collector.daemon")

    def run(self) -> dict[str, Any]:
        configure_logging()
        self.validate_startup()
        self._refresh_core_reachable()
        self._touch_state_db()
        self.state.running = True
        self.log.info(
            "daemon_start",
            config_path=str(self.config_path),
            export_target=self.settings.daemon.export_target,
            source_count=len(self.settings.sources),
        )
        install_signal_handlers(self.stop_event)
        try:
            self._start_http_servers()
            while not self.stop_event.is_set():
                self._run_cycle()
                if self.max_cycles is not None and self.state.cycles_completed >= self.max_cycles:
                    break
                if self.run_once:
                    break
                wait_seconds = next_interval_seconds(
                    self.settings.daemon.interval_seconds,
                    self.settings.daemon.jitter_seconds,
                )
                if self.stop_event.wait(wait_seconds):
                    break
        except Exception as exc:
            self.state.permanent_error = True
            self.state.last_error = _safe_error(exc)
            self.state.last_sync_status = "failed"
            self.log.error("sync_cycle_failed", error=self.state.last_error)
            raise
        finally:
            self.state.running = False
            self._stop_http_servers()
            self.log.info("daemon_stop", cycles_completed=self.state.cycles_completed)
        return self.health_payload()

    def validate_startup(self) -> None:
        if not self.settings.sources:
            raise DaemonStartupError("daemon requires at least one configured source")
        export_target = self.settings.daemon.export_target
        if export_target not in {"api", "jsonl", "sqlite", "console"}:
            raise DaemonStartupError(f"unsupported daemon export target: {export_target}")
        if export_target in {"jsonl", "sqlite"} and not self.settings.daemon.output_path:
            raise DaemonStartupError(f"daemon export target {export_target} requires daemon.output_path")
        for source in self.settings.sources:
            source_path = Path(source.path).expanduser()
            if not source_path.exists():
                raise DaemonStartupError(f"source path does not exist: {source.path}")
            try:
                ensure_path_allowed(source_path.resolve(), self.settings.security.allow_paths)
            except PermissionError as exc:
                raise DaemonStartupError(str(exc)) from exc
        if export_target == "api":
            if self.settings.security.require_confirmation_for_upload and not self.settings.daemon.allow_unattended_upload:
                raise DaemonStartupError(
                    "daemon API upload requires security.require_confirmation_for_upload=false "
                    "or daemon.allow_unattended_upload=true"
                )
            if not self.settings.api.base_url:
                raise DaemonStartupError("daemon API upload requires api.base_url")
            if not self.settings.project.id:
                raise DaemonStartupError("daemon API upload requires project.id")
            if self.settings.api.auth_required and not self.settings.api.resolve_token():
                raise DaemonStartupError(API_TOKEN_REQUIRED_MESSAGE)

    def health_payload(self) -> dict[str, Any]:
        pending_failed_uploads = self._failed_upload_depth()
        if self.state.permanent_error or not self.state.state_db_writable:
            status = "error"
        elif pending_failed_uploads or self.state.last_failed_sync or self.state.core_reachable is False:
            status = "degraded"
        else:
            status = "ok"
        return {
            "status": status,
            "collector_version": collector_version(),
            "schema_version": SCHEMA_VERSION,
            "core_api_version": CORE_API_VERSION,
            "daemon_started_at": self.state.daemon_started_at,
            "last_successful_sync": self.state.last_successful_sync,
            "last_failed_sync": self.state.last_failed_sync,
            "last_sync_status": self.state.last_sync_status,
            "last_error": self.state.last_error,
            "pending_failed_uploads": pending_failed_uploads,
            "queue_depth": pending_failed_uploads,
            "core_reachable": self.state.core_reachable,
            "state_db_writable": self.state.state_db_writable,
            "cycles_completed": self.state.cycles_completed,
        }

    def metrics_payload(self) -> str:
        pending_failed_uploads = self._failed_upload_depth()
        uptime = (
            datetime.now(timezone.utc) - datetime.fromisoformat(self.state.daemon_started_at)
        ).total_seconds()
        metrics = {
            "collector_files_seen_total": self.state.totals["files_seen"],
            "collector_files_synced_total": self.state.totals["files_synced"],
            "collector_files_skipped_total": self.state.totals["files_skipped"],
            "collector_documents_synced_total": self.state.totals["documents_synced"],
            "collector_redactions_total": self.state.totals["redactions"],
            "collector_failed_uploads_total": self.state.totals["failed_uploads"],
            "collector_retry_queue_depth": pending_failed_uploads,
            "collector_sync_duration_seconds": self.state.totals["sync_duration_seconds"],
            "collector_last_successful_sync_timestamp": _timestamp(self.state.last_successful_sync),
            "collector_last_failed_sync_timestamp": _timestamp(self.state.last_failed_sync),
            "collector_rag_readiness_score": self.state.totals["rag_readiness_score"],
            "collector_daemon_uptime_seconds": uptime,
            "collector_core_reachable": 1 if self.state.core_reachable else 0,
        }
        lines = []
        for name, value in metrics.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {float(value)}")
        return "\n".join(lines) + "\n"

    def _start_http_servers(self) -> None:
        if self.settings.daemon.health_enabled:
            self.health_server = HealthServer(
                self.settings.daemon.health_host,
                self.settings.daemon.health_port,
                self.health_payload,
            )
            self.health_server.start()
            self.log.info(
                "health_server_started",
                host=self.health_server.host,
                port=self.health_server.port,
            )
        if self.settings.daemon.metrics_enabled:
            self.metrics_server = MetricsServer(
                self.settings.daemon.metrics_host,
                self.settings.daemon.metrics_port,
                self.metrics_payload,
            )
            self.metrics_server.start()
            self.log.info(
                "metrics_server_started",
                host=self.metrics_server.host,
                port=self.metrics_server.port,
            )

    def _stop_http_servers(self) -> None:
        if self.health_server:
            self.health_server.stop()
        if self.metrics_server:
            self.metrics_server.stop()

    def _run_cycle(self) -> None:
        self._refresh_core_reachable()
        self.log.info("sync_cycle_start", cycle=self.state.cycles_completed + 1)
        started = datetime.now(timezone.utc)
        summaries: list[dict[str, Any]] = []
        try:
            for source in self.settings.sources:
                summary = self._sync_source(source)
                summaries.append(summary.model_dump(mode="json"))
                self._apply_summary(summary)
            self.state.last_successful_sync = datetime.now(timezone.utc).isoformat()
            self.state.last_summary = {"summaries": summaries}
            self.state.last_sync_status = "success"
            self.log.info(
                "sync_cycle_complete",
                cycle=self.state.cycles_completed + 1,
                source_count=len(summaries),
                failed_uploads=self._failed_upload_depth(),
            )
        except Exception as exc:
            self.state.last_failed_sync = datetime.now(timezone.utc).isoformat()
            self.state.last_error = _safe_error(exc)
            self.state.last_sync_status = "failed"
            self.log.error(
                "sync_cycle_failed",
                cycle=self.state.cycles_completed + 1,
                error=self.state.last_error,
            )
        finally:
            duration = (datetime.now(timezone.utc) - started).total_seconds()
            self.state.totals["sync_duration_seconds"] += duration
            self.state.cycles_completed += 1

    def _sync_source(self, source: SourceConfig) -> SyncSummary:
        source_path = Path(source.path).expanduser()
        return run_sync(
            path=source_path,
            settings=self.settings,
            export_target=self.settings.daemon.export_target,
            project_id=self.settings.project.id,
            source_name=self.settings.daemon.source_name or source.name,
            output=self.settings.daemon.output_path,
            dry_run=self.settings.sync.dry_run,
            force=False,
            no_redact=not self.settings.security.redact_secrets,
            max_depth=self.settings.daemon.max_depth,
            source_type=source.type or self.settings.daemon.source_type,
        )

    def _apply_summary(self, summary: SyncSummary) -> None:
        self.state.totals["files_seen"] += summary.files_seen
        self.state.totals["files_synced"] += summary.files_uploaded
        self.state.totals["files_skipped"] += summary.files_skipped
        self.state.totals["documents_synced"] += summary.documents_synced
        self.state.totals["failed_uploads"] += summary.failed_uploads

    def _refresh_core_reachable(self) -> None:
        if not self.settings.api.base_url:
            self.state.core_reachable = None
            return
        client = None
        try:
            client = CoreClient(
                self.settings.api.base_url,
                token=self.settings.api.resolve_token(),
                timeout_seconds=self.settings.api.timeout_seconds,
                verify_tls=self.settings.api.verify_tls,
            )
            client.health()
            self.state.core_reachable = True
        except Exception as exc:
            self.state.core_reachable = False
            self.log.warning("core_unavailable", error=_safe_error(exc))
        finally:
            if client:
                client.close()

    def _touch_state_db(self) -> None:
        try:
            store = SQLiteStore(self.settings.state.sqlite_path)
            store.close()
            self.state.state_db_writable = True
        except Exception as exc:
            self.state.state_db_writable = False
            self.state.last_error = _safe_error(exc)
            raise DaemonStartupError(f"state DB is not writable: {exc}") from exc

    def _failed_upload_depth(self) -> int:
        try:
            store = SQLiteStore(self.settings.state.sqlite_path)
            try:
                return store.failed_upload_queue_depth()
            finally:
                store.close()
        except Exception:
            self.state.state_db_writable = False
            return 0


def _timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    return datetime.fromisoformat(value).timestamp()


def _safe_error(exc: Exception) -> str:
    value = str(exc)
    try:
        json.dumps(value)
    except TypeError:
        value = repr(value)
    return value
