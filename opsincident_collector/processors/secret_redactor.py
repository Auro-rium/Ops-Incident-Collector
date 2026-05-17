from __future__ import annotations

from opsincident_collector.core.models import RedactionSummary
from opsincident_collector.security.redaction_patterns import REDACTION_PATTERNS

REDACTION_TOKEN = "[REDACTED_SECRET]"


def redact_text(text: str, enabled: bool = True) -> tuple[str, RedactionSummary]:
    if not enabled:
        return (
            text,
            RedactionSummary(
                enabled=False,
                redacted_count=0,
                patterns_matched=[],
                had_possible_secret=False,
            ),
        )

    redacted_text = text
    redacted_count = 0
    matched_names: list[str] = []
    for name, pattern in REDACTION_PATTERNS:
        matches = pattern.findall(redacted_text)
        if not matches:
            continue
        redacted_text, count = pattern.subn(REDACTION_TOKEN, redacted_text)
        redacted_count += count
        matched_names.append(name)

    summary = RedactionSummary(
        enabled=True,
        redacted_count=redacted_count,
        patterns_matched=matched_names,
        had_possible_secret=redacted_count > 0,
    )
    return redacted_text, summary
