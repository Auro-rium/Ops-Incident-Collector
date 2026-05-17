from __future__ import annotations

from pathlib import Path


def _normalize_path(path: Path | str) -> str:
    return Path(path).as_posix()


def is_denied_path(relative_path: str, deny_patterns: list[str]) -> bool:
    path = _normalize_path(relative_path)
    return any(Path(path).match(pattern) for pattern in deny_patterns)


def is_allowed_path(path: Path, allow_paths: list[str]) -> bool:
    resolved = path.resolve()
    for allowed in allow_paths:
        allowed_path = Path(allowed).expanduser().resolve()
        if resolved == allowed_path or allowed_path in resolved.parents:
            return True
    return False


def ensure_path_allowed(path: Path, allow_paths: list[str]) -> None:
    if not is_allowed_path(path, allow_paths):
        raise PermissionError(f"path is not allowlisted: {path}")
