from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _git_output(repo_root: Path, *args: str) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def detect_repo_root(path: Path) -> Path | None:
    candidate = path if path.is_dir() else path.parent
    for parent in [candidate, *candidate.parents]:
        if (parent / ".git").exists():
            return parent
    git_root = _git_output(candidate, "rev-parse", "--show-toplevel")
    return Path(git_root) if git_root else None


def extract_metadata(path: Path, _text: str = "") -> dict[str, object]:
    repo_root = detect_repo_root(path)
    if not repo_root:
        return {"source_kind": "code", "git_available": shutil.which("git") is not None}
    return {
        key: value
        for key, value in {
            "source_kind": "git_local",
            "git_repo_root": str(repo_root),
            "git_branch": _git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD"),
            "git_latest_commit_sha": _git_output(repo_root, "rev-parse", "HEAD"),
        }.items()
        if value not in (None, [], {}, "")
    }
