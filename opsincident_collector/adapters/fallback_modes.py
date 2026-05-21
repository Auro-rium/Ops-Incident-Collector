from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EndpointMap:
    health: str = "/health"
    capabilities: str = "/v1/capabilities"
    register_collector: str = "/v1/projects/{project_id}/collectors/register"
    register_source: str = "/v1/projects/{project_id}/sources"
    batch_upload: str = "/v1/sources/{source_id}/documents/batch"
    create_sync: str = "/v1/sources/{source_id}/syncs/start"
    update_sync: str = "/v1/sources/{source_id}/syncs/{sync_id}/finish"
    fallback_ingest: str = "/v1/projects/{project_id}/ingest/documents"
    search: str = "/v1/search"
    investigate: str = "/v1/investigate"
    runs: str = "/v1/runs"
    run_status: str = "/v1/runs/{run_id}"
    run_events: str = "/v1/runs/{run_id}/events"


def resolve_endpoint(capability_endpoints: dict[str, str] | None, name: str) -> str:
    defaults = EndpointMap()
    if capability_endpoints and name in capability_endpoints:
        return capability_endpoints[name]
    return getattr(defaults, name)
