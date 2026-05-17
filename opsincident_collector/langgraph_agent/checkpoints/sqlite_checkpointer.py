from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from opsincident_collector.state.migrations import run_migrations


SENSITIVE_KEYS = {
    "content",
    "payload_json",
    "preview",
    "token",
    "authorization",
    "password",
    "secret",
}


class GraphRunStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        run_migrations(self.conn)

    def close(self) -> None:
        self.conn.close()

    def create_run(self, graph_name: str, run_id: str, input_state: dict[str, Any]) -> None:
        now = _now()
        state = sanitize_for_storage(input_state)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO graph_runs (
                run_id, graph_name, status, input_json, state_json,
                created_at, updated_at, completed_at, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                run_id,
                graph_name,
                input_state.get("status", "running"),
                json.dumps(state),
                json.dumps(state),
                now,
                now,
            ),
        )
        self.conn.commit()

    def update_run_state(
        self,
        run_id: str,
        graph_name: str,
        state: dict[str, Any],
        *,
        status: str | None = None,
        error: str | None = None,
        completed: bool = False,
    ) -> None:
        safe_state = sanitize_for_storage(state)
        self.conn.execute(
            """
            UPDATE graph_runs
            SET status = ?, state_json = ?, updated_at = ?, completed_at = ?, error = ?
            WHERE run_id = ?
            """,
            (
                status or str(state.get("status") or "running"),
                json.dumps(safe_state),
                _now(),
                _now() if completed else None,
                error,
                run_id,
            ),
        )
        self.conn.commit()

    def record_event(
        self,
        run_id: str,
        graph_name: str,
        node_name: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO graph_events (
                run_id, graph_name, node_name, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                graph_name,
                node_name,
                event_type,
                json.dumps(sanitize_for_storage(payload)),
                _now(),
            ),
        )
        self.conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM graph_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data.pop("input_json"))
        data["state"] = json.loads(data.pop("state_json"))
        return data

    def list_events(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM graph_events WHERE run_id = ? ORDER BY id ASC",
            (run_id,),
        ).fetchall()
        events = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json"))
            events.append(data)
        return events

    def ensure_approval(
        self,
        *,
        run_id: str,
        graph_name: str,
        node_name: str,
        approval_type: str,
        request: dict[str, Any],
    ) -> str:
        existing = self.conn.execute(
            """
            SELECT approval_id FROM graph_approvals
            WHERE run_id = ? AND node_name = ? AND status = 'pending'
            ORDER BY created_at DESC LIMIT 1
            """,
            (run_id, node_name),
        ).fetchone()
        if existing:
            return str(existing["approval_id"])
        approval_id = f"approval_{uuid4().hex[:12]}"
        self.conn.execute(
            """
            INSERT INTO graph_approvals (
                approval_id, run_id, graph_name, node_name, approval_type,
                status, request_json, response_json, created_at, decided_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, ?, NULL)
            """,
            (
                approval_id,
                run_id,
                graph_name,
                node_name,
                approval_type,
                json.dumps(sanitize_for_storage(request)),
                _now(),
            ),
        )
        self.conn.commit()
        return approval_id

    def decide_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = "approved" if approved else "rejected"
        self.conn.execute(
            """
            UPDATE graph_approvals
            SET status = ?, response_json = ?, decided_at = ?
            WHERE approval_id = ?
            """,
            (
                status,
                json.dumps(sanitize_for_storage(response or {"approved": approved})),
                _now(),
                approval_id,
            ),
        )
        self.conn.commit()
        approval = self.get_approval(approval_id)
        if not approval:
            raise KeyError(f"approval not found: {approval_id}")
        return approval

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM graph_approvals WHERE approval_id = ?",
            (approval_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["request"] = json.loads(data.pop("request_json"))
        response_json = data.pop("response_json")
        data["response"] = json.loads(response_json) if response_json else None
        return data

    def list_pending_approvals(self, run_id: str | None = None) -> list[dict[str, Any]]:
        if run_id:
            rows = self.conn.execute(
                """
                SELECT * FROM graph_approvals
                WHERE status = 'pending' AND run_id = ?
                ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT * FROM graph_approvals
                WHERE status = 'pending'
                ORDER BY created_at ASC
                """
            ).fetchall()
        approvals = []
        for row in rows:
            data = dict(row)
            data["request"] = json.loads(data.pop("request_json"))
            response_json = data.pop("response_json")
            data["response"] = json.loads(response_json) if response_json else None
            approvals.append(data)
        return approvals


def sanitize_for_storage(value: Any) -> Any:
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SENSITIVE_KEYS or lowered.endswith("_token"):
                continue
            safe[key] = sanitize_for_storage(item)
        return safe
    if isinstance(value, list):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_storage(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
