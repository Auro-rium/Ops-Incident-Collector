from __future__ import annotations

from typing import Any

import httpx

from opsincident_collector.adapters.core_contracts import CoreCapabilities, SourceRegistrationResult
from opsincident_collector.adapters.fallback_modes import resolve_endpoint
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version


class MissingBatchEndpointError(RuntimeError):
    pass


def is_retryable_api_error(exc: Exception) -> bool:
    if isinstance(exc, MissingBatchEndpointError):
        return False
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code in {408, 409, 425, 429} or status_code >= 500
    return False


class CoreClient:
    def __init__(self, base_url: str, token: str | None = None, timeout_seconds: int = 30, verify_tls: bool = True):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            verify=verify_tls,
            headers=headers,
        )

    def close(self) -> None:
        self.client.close()

    def health(self) -> dict[str, Any]:
        response = self.client.get("/health")
        response.raise_for_status()
        return response.json()

    def capabilities(self) -> CoreCapabilities | None:
        response = self.client.get("/v1/capabilities")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return CoreCapabilities.model_validate(response.json())

    def register_collector(
        self,
        project_id: str,
        payload: dict[str, Any],
        capabilities: CoreCapabilities | None = None,
    ) -> dict[str, Any]:
        endpoint = resolve_endpoint(capabilities.endpoints if capabilities else None, "register_collector")
        collector_payload = {
            "name": payload["name"],
            "environment": payload.get("environment") or "local",
            "version": payload.get("version") or collector_version(),
        }
        response = self.client.post(endpoint.format(project_id=project_id), json=collector_payload)
        response.raise_for_status()
        return response.json()

    def register_source(self, project_id: str, payload: dict[str, Any], capabilities: CoreCapabilities | None = None) -> SourceRegistrationResult:
        endpoint = resolve_endpoint(capabilities.endpoints if capabilities else None, "register_source")
        source_payload = {
            "name": payload["name"],
            "source_type": payload.get("source_type") or payload.get("type") or "filesystem",
            "type": payload.get("type") or payload.get("source_type") or "filesystem",
            "sync_mode": payload.get("sync_mode", "manual"),
            "config": payload.get("config", {}),
        }
        response = self.client.post(endpoint.format(project_id=project_id), json=source_payload)
        response.raise_for_status()
        data = response.json()
        return SourceRegistrationResult(source_id=data.get("source_id") or data.get("id") or payload["name"], raw=data)

    def create_sync(self, source_id: str, payload: dict[str, Any], capabilities: CoreCapabilities | None = None) -> dict[str, Any]:
        endpoint = resolve_endpoint(capabilities.endpoints if capabilities else None, "create_sync")
        response = self.client.post(endpoint.format(source_id=source_id), json=payload)
        if response.status_code == 404:
            legacy_response = self.client.post(f"/v1/sources/{source_id}/syncs", json=payload)
            if legacy_response.status_code == 404:
                return {"sync_id": payload["sync_id"]}
            legacy_response.raise_for_status()
            return legacy_response.json()
        response.raise_for_status()
        return response.json()

    def update_sync(self, source_id: str, sync_id: str, payload: dict[str, Any], capabilities: CoreCapabilities | None = None) -> dict[str, Any]:
        endpoint = resolve_endpoint(capabilities.endpoints if capabilities else None, "update_sync")
        formatted = endpoint.format(source_id=source_id, sync_id=sync_id)
        if formatted.endswith("/finish"):
            response = self.client.post(formatted, json=payload)
        else:
            response = self.client.patch(formatted, json=payload)
        if response.status_code == 404:
            legacy_response = self.client.patch(f"/v1/sources/{source_id}/syncs/{sync_id}", json=payload)
            if legacy_response.status_code == 404:
                return {"sync_id": sync_id, "status": payload.get("status")}
            legacy_response.raise_for_status()
            return legacy_response.json()
        response.raise_for_status()
        return response.json()

    @staticmethod
    def versioned_batch_payload(
        documents: list[dict[str, Any]],
        sync_id: str | None = None,
        collector_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "collector_version": collector_version(),
            "schema_version": SCHEMA_VERSION,
            "core_api_version": CORE_API_VERSION,
            "documents": documents,
        }
        if sync_id:
            payload["sync_id"] = sync_id
        if collector_id:
            payload["collector_id"] = collector_id
        return payload

    def batch_upload_documents(
        self,
        project_id: str,
        source_id: str,
        documents: list[dict[str, Any]],
        sync_id: str | None = None,
        collector_id: str | None = None,
        capabilities: CoreCapabilities | None = None,
    ) -> dict[str, Any]:
        capability_endpoints = capabilities.endpoints if capabilities else None
        batch_endpoint = resolve_endpoint(capability_endpoints, "batch_upload")
        payload = self.versioned_batch_payload(
            documents,
            sync_id=sync_id,
            collector_id=collector_id,
        )
        response = self.client.post(
            batch_endpoint.format(project_id=project_id, source_id=source_id),
            json=payload,
        )
        if response.status_code == 404:
            legacy_response = self.client.post(
                f"/v1/projects/{project_id}/sources/{source_id}/documents:batch",
                json=payload,
            )
            if legacy_response.status_code != 404:
                legacy_response.raise_for_status()
                return legacy_response.json()
            fallback = resolve_endpoint(capability_endpoints, "fallback_ingest")
            fallback_payload = payload | {"source_id": source_id}
            fallback_response = self.client.post(
                fallback.format(project_id=project_id),
                json=fallback_payload,
            )
            if fallback_response.status_code == 404:
                raise MissingBatchEndpointError(
                    "IncidentOps Core does not expose a document batch ingestion endpoint. "
                    "Use --export jsonl or update Core."
                )
            fallback_response.raise_for_status()
            return fallback_response.json()
        response.raise_for_status()
        return response.json()

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post("/v1/search", json=payload)
        response.raise_for_status()
        return response.json()

    def get_latest_sync(self, source_id: str) -> dict[str, Any]:
        response = self.client.get(f"/v1/sources/{source_id}/syncs/latest")
        response.raise_for_status()
        return response.json()

    def list_sources(self, project_id: str) -> dict[str, Any]:
        response = self.client.get(f"/v1/projects/{project_id}/sources")
        response.raise_for_status()
        return response.json()

    def investigate(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post("/v1/investigate", json=payload)
        response.raise_for_status()
        return response.json()

    def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post("/v1/runs", json=payload)
        response.raise_for_status()
        return response.json()

    def get_run_status(self, run_id: str) -> dict[str, Any]:
        response = self.client.get(f"/v1/runs/{run_id}")
        response.raise_for_status()
        return response.json()

    def get_run_events(self, run_id: str) -> dict[str, Any]:
        response = self.client.get(f"/v1/runs/{run_id}/events")
        response.raise_for_status()
        return response.json()
