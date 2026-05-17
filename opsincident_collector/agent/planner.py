from __future__ import annotations

from opsincident_collector.config.settings import AppSettings


def build_investigation_plan(settings: AppSettings, query: str) -> dict:
    return {
        "query": query,
        "core_available": bool(settings.api.base_url),
        "local_sources": [source.name for source in settings.sources],
        "steps": [
            "inspect configured local sources",
            "identify missing evidence types",
            "recommend sync if stale or missing",
            "call IncidentOps Core investigate when available",
        ],
    }
