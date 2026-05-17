from __future__ import annotations

import re
from pathlib import Path

from opsincident_collector.config.settings import DEFAULT_SUPPORTED_EXTENSIONS
from opsincident_collector.security.redaction_patterns import REDACTION_PATTERNS

SECRET_PATTERNS = [pattern for _, pattern in REDACTION_PATTERNS]


def is_supported_extension(extension: str) -> bool:
    return extension.lower() in DEFAULT_SUPPORTED_EXTENSIONS


def is_binary_file(path: Path, sample_size: int = 1024) -> bool:
    sample = path.read_bytes()[:sample_size]
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    text_bytes = sum(byte in b"\t\n\r\f\b" or 32 <= byte <= 126 for byte in sample)
    return text_bytes / len(sample) < 0.8


def detect_possible_secret_count(path: Path, max_chars: int = 200_000) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return 0
    return sum(len(pattern.findall(text)) for pattern in SECRET_PATTERNS)
