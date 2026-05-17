from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from opsincident_collector.config.loader import load_settings_optional
from opsincident_collector.langgraph_agent.checkpoints.sqlite_checkpointer import GraphRunStore
from opsincident_collector.langgraph_agent.graphs import (
    investigation_bridge_graph,
    rag_readiness_graph,
    source_onboarding_graph,
    sync_quality_graph,
)


class LangGraphUnavailableError(RuntimeError):
    pass


GRAPH_BUILDERS: dict[str, Callable[[], Any]] = {
    "source_onboarding": source_onboarding_graph.build_graph,
    "rag_readiness": rag_readiness_graph.build_graph,
    "sync_quality": sync_quality_graph.build_graph,
    "investigation_bridge": investigation_bridge_graph.build_graph,
}


TERMINAL_STATUSES = {
    "completed",
    "failed",
    "pending_approval",
    "rejected",
    "core_unavailable",
    "core_investigation_complete",
}


def new_run_id(prefix: str = "graph") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def run_graph(
    graph_name: str,
    input_state: dict[str, Any],
    *,
    config_path: Path | None = None,
    state_db_path: Path | None = None,
    resume_run_id: str | None = None,
) -> dict[str, Any]:
    _ensure_langgraph_available()
    if graph_name not in GRAPH_BUILDERS:
        raise ValueError(f"unknown graph: {graph_name}")

    settings = load_settings_optional(config_path)
    store = GraphRunStore(state_db_path or settings.state.sqlite_path)
    try:
        if resume_run_id:
            run = store.get_run(resume_run_id)
            if not run:
                raise KeyError(f"graph run not found: {resume_run_id}")
            state = dict(run["state"])
            state.update(input_state)
            state["run_id"] = resume_run_id
            run_id = resume_run_id
        else:
            run_id = input_state.get("run_id") or new_run_id(graph_name)
            state = _initial_state(input_state | {"run_id": run_id})
            store.create_run(graph_name, run_id, state)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message=r".*allowed_objects.*")
            warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
            compiled = GRAPH_BUILDERS[graph_name]()
        store.update_run_state(run_id, graph_name, state, status="running")
        for update in compiled.stream(state):
            for node_name, delta in update.items():
                if not isinstance(delta, dict):
                    continue
                state.update(delta)
                _persist_approval_if_needed(store, graph_name, node_name, state)
                store.record_event(run_id, graph_name, node_name, "node_update", delta)
                store.update_run_state(run_id, graph_name, state, status=state.get("status"))
        status = str(state.get("status") or "completed")
        completed = status not in {"pending_approval", "running"}
        if status == "running":
            status = "completed"
            state["status"] = status
        store.update_run_state(run_id, graph_name, state, status=status, completed=completed)
        return state
    except Exception as exc:
        failed_state = {
            **input_state,
            "run_id": input_state.get("run_id") or resume_run_id or new_run_id(graph_name),
            "status": "failed",
            "errors": [str(exc)],
        }
        run_id = failed_state["run_id"]
        existing = store.get_run(run_id)
        if not existing:
            store.create_run(graph_name, run_id, failed_state)
        store.update_run_state(
            run_id,
            graph_name,
            failed_state,
            status="failed",
            error=str(exc),
            completed=True,
        )
        raise
    finally:
        store.close()


def approve_action(
    approval_id: str,
    *,
    config_path: Path | None = None,
    state_db_path: Path | None = None,
    approved: bool = True,
) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    store = GraphRunStore(state_db_path or settings.state.sqlite_path)
    try:
        approval = store.decide_approval(
            approval_id,
            approved=approved,
            response={"approved": approved},
        )
        run = store.get_run(approval["run_id"])
        if not run:
            raise KeyError(f"graph run not found: {approval['run_id']}")
        state = dict(run["state"])
        if approved:
            state["approved"] = True
            state["sync_approved"] = True
            state["status"] = "running"
        else:
            state["status"] = "rejected"
            state["errors"] = [*state.get("errors", []), "approval rejected"]
        store.update_run_state(
            approval["run_id"],
            approval["graph_name"],
            state,
            status=state["status"],
            completed=not approved,
        )
        return {"approval": approval, "state": state}
    finally:
        store.close()


def get_graph_run_status(
    run_id: str,
    *,
    config_path: Path | None = None,
    state_db_path: Path | None = None,
) -> dict[str, Any]:
    settings = load_settings_optional(config_path)
    store = GraphRunStore(state_db_path or settings.state.sqlite_path)
    try:
        run = store.get_run(run_id)
        if not run:
            raise KeyError(f"graph run not found: {run_id}")
        return {
            "run": run,
            "events": store.list_events(run_id),
            "pending_approvals": store.list_pending_approvals(run_id),
        }
    finally:
        store.close()


def _initial_state(state: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("errors", [])
    state.setdefault("warnings", [])
    state.setdefault("status", "running")
    state.setdefault("config_loaded", False)
    state.setdefault("require_approval", True)
    state.setdefault("dry_run", False)
    state.setdefault("approved", False)
    return state


def _persist_approval_if_needed(
    store: GraphRunStore,
    graph_name: str,
    node_name: str,
    state: dict[str, Any],
) -> None:
    request = state.get("approval_request")
    if state.get("status") != "pending_approval" or not isinstance(request, dict):
        return
    if request.get("approval_id"):
        return
    approval_id = store.ensure_approval(
        run_id=state["run_id"],
        graph_name=graph_name,
        node_name=node_name,
        approval_type=str(request.get("action", "DATA_EXPORT")),
        request={
            "approval_id": None,
            "run_id": state["run_id"],
            "graph_name": graph_name,
            "node_name": node_name,
            **request,
        },
    )
    request["approval_id"] = approval_id
    request["run_id"] = state["run_id"]
    request["graph_name"] = graph_name


def _ensure_langgraph_available() -> None:
    warnings.filterwarnings(
        "ignore",
        message=r".*allowed_objects.*",
        category=Warning,
    )
    try:
        import langgraph  # noqa: F401
    except ModuleNotFoundError as exc:
        raise LangGraphUnavailableError(
            "LangGraph dependency not installed. "
            "Install with `pip install 'opsincident-collector[agent]'`."
        ) from exc
