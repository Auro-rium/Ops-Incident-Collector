from __future__ import annotations

import re

REDACTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.=]+")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{10,}\b")),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key)\s*[:=]\s*['\"]?[^\s'\",]+")),
    ("generic_secret", re.compile(r"(?i)(secret)\s*[:=]\s*['\"]?[^\s'\",]+")),
    ("password", re.compile(r"(?i)(password)\s*[:=]\s*['\"]?[^\s'\",]+")),
    (
        "database_url",
        re.compile(r"\b[a-z]+:\/\/[^:\s\/]+:[^@\s\/]+@[^ \n]+", re.IGNORECASE),
    ),
    (
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
    ),
]
