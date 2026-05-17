from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterator

from opsincident_collector.core.models import SourceItem


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(Path(path).match(pattern) for pattern in patterns)


def discover_files(
    root: Path,
    max_depth: int = 8,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> Iterator[SourceItem]:
    include = include or []
    exclude = exclude or []
    root = root.resolve()
    for child in sorted(root.rglob("*")):
        if not child.is_file():
            continue
        relative_path = child.relative_to(root).as_posix()
        if max_depth >= 0 and len(Path(relative_path).parts) - 1 > max_depth:
            continue
        if include and not _matches_any(relative_path, include):
            continue
        if exclude and _matches_any(relative_path, exclude):
            continue
        stat = child.stat()
        yield SourceItem(
            path=child,
            relative_path=relative_path,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            extension=child.suffix.lower(),
            detected_type=None,
        )
