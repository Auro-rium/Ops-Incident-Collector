from pathlib import Path

from opsincident_collector.config.settings import AppSettings
from opsincident_collector.security.permission_policy import check_tool_permission


def test_permission_policy_requires_approval_for_sync(tmp_path: Path) -> None:
    settings = AppSettings()
    settings.security.allow_paths = [str(tmp_path)]

    denied = check_tool_permission(settings, "sync_source", path=tmp_path, approved=False, dry_run=False)
    allowed = check_tool_permission(settings, "sync_source", path=tmp_path, approved=True, dry_run=False)

    assert denied.allowed is False
    assert allowed.allowed is True


def test_preview_redaction_requires_allowlisted_path(tmp_path: Path) -> None:
    settings = AppSettings()
    settings.security.allow_paths = [str(tmp_path / "safe")]
    decision = check_tool_permission(settings, "preview_redaction", path=Path(tmp_path / "unsafe"))
    assert decision.allowed is False
