from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from opsincident_collector.config.settings import AppSettings
from opsincident_collector.processors.path_policy import is_allowed_path


class PermissionLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL_SENSITIVE_READ = "LOCAL_SENSITIVE_READ"
    DATA_EXPORT = "DATA_EXPORT"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"


TOOL_PERMISSIONS = {
    "inspect_folder": PermissionLevel.READ_ONLY,
    "validate_source_config": PermissionLevel.READ_ONLY,
    "get_source_coverage": PermissionLevel.READ_ONLY,
    "get_rag_readiness": PermissionLevel.READ_ONLY,
    "search_evidence": PermissionLevel.READ_ONLY,
    "investigate_incident": PermissionLevel.READ_ONLY,
    "get_run_status": PermissionLevel.READ_ONLY,
    "get_run_events": PermissionLevel.READ_ONLY,
    "validate_core_contract": PermissionLevel.READ_ONLY,
    "preview_redaction": PermissionLevel.LOCAL_SENSITIVE_READ,
    "sync_source": PermissionLevel.DATA_EXPORT,
    "create_workflow_run": PermissionLevel.DATA_EXPORT,
    "generate_eval_seed": PermissionLevel.READ_ONLY,
    "export_report": PermissionLevel.READ_ONLY,
}


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str


def permission_level_for_tool(tool_name: str) -> PermissionLevel:
    return TOOL_PERMISSIONS.get(tool_name, PermissionLevel.READ_ONLY)


def check_tool_permission(
    settings: AppSettings,
    tool_name: str,
    path: Path | None = None,
    approved: bool = False,
    dry_run: bool = False,
) -> PermissionDecision:
    if tool_name in settings.mcp.deny_tools:
        return PermissionDecision(False, "tool denied by policy")
    level = TOOL_PERMISSIONS.get(tool_name, PermissionLevel.READ_ONLY)
    if settings.mcp.allow_tools and tool_name not in settings.mcp.allow_tools and level == PermissionLevel.READ_ONLY:
        return PermissionDecision(False, "tool not in allowlist")
    if level == PermissionLevel.LOCAL_SENSITIVE_READ:
        if path is None or not is_allowed_path(path, settings.security.allow_paths):
            return PermissionDecision(False, "path not allowlisted")
    if level == PermissionLevel.DATA_EXPORT:
        requires_approval = tool_name in settings.mcp.require_approval or settings.mcp.require_approval_for_sync
        if requires_approval and not (approved or dry_run):
            return PermissionDecision(False, "approval required")
    if level == PermissionLevel.EXTERNAL_WRITE:
        return PermissionDecision(False, "external write disabled")
    return PermissionDecision(True, "allowed")
