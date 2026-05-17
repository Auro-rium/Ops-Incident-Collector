from __future__ import annotations


def should_recommend_sync(missing_data: list[str]) -> bool:
    return bool(missing_data)
