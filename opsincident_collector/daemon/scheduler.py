from __future__ import annotations

import random


def next_interval_seconds(interval_seconds: int, jitter_seconds: int = 0) -> float:
    base = max(interval_seconds, 1)
    if jitter_seconds <= 0:
        return float(base)
    return float(base + random.randint(0, jitter_seconds))

