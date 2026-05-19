from __future__ import annotations

import hashlib
from typing import Any

from opsincident_collector.adapters.core_client import CoreClient, MissingBatchEndpointError
from opsincident_collector.core.protocol import CORE_API_VERSION, SCHEMA_VERSION, collector_version

MISSING_BATCH_MESSAGE = (
    "Core does not expose a compatible NormalizedDocument batch ingestion endpoint. "
    "Use JSONL export or update Core ingestion contract."
)


def validate_core_contract(
    *,
    api_url: str,
    project_id: str,
    token: str | None = None,
    with_sample: bool = False,
) -> dict[str, Any]:
    client = CoreClient(api_url, token=token)
    report: dict[str, Any] = {
        "api_url": api_url,
        "project_id": project_id,
        "collector_version": collector_version(),
        "schema_version": SCHEMA_VERSION,
        "core_api_version": CORE_API_VERSION,
        "health": None,
        "capabilities_available": False,
        "features": {},
        "endpoints": {},
        "sample_uploaded": False,
        "compatible": False,
        "errors": [],
        "warnings": [],
    }
    try:
        report["health"] = client.health()
    except Exception as exc:
        report["errors"].append(f"health check failed: {exc}")
        client.close()
        return report

    capabilities = None
    try:
        capabilities = client.capabilities()
    except Exception as exc:
        report["warnings"].append(f"capabilities unavailable: {exc}")

    if capabilities:
        report["capabilities_available"] = True
        report["features"] = dict(capabilities.features)
        report["endpoints"] = dict(capabilities.endpoints)
    else:
        report["warnings"].append("capabilities endpoint did not return a contract document")
        _merge_openapi_contract(report, client)

    features = report["features"]
    endpoints = report["endpoints"]
    document_batch_upload = bool(features.get("document_batch_upload") or endpoints.get("batch_upload"))
    supported = {
        "source_registry": bool(features.get("source_registry") or endpoints.get("register_source")),
        "collector_registration": bool(
            features.get("collector_registration")
            or endpoints.get("register_collector")
            or endpoints.get("collector_register")
        ),
        "sync_lifecycle": bool(features.get("sync_lifecycle") or features.get("sync_tracking") or endpoints.get("create_sync")),
        "document_batch_upload": document_batch_upload,
        "fallback_ingest": bool(features.get("fallback_ingest") or endpoints.get("fallback_ingest")),
        "search": bool(features.get("search") or endpoints.get("search")),
        "investigate": bool(features.get("investigate") or endpoints.get("investigate")),
    }
    report["supported_features"] = supported

    if not document_batch_upload and not with_sample:
        report["errors"].append(MISSING_BATCH_MESSAGE)
        client.close()
        return report

    if with_sample:
        try:
            collector = client.register_collector(
                project_id=project_id,
                payload={
                    "name": "collector-contract-validation",
                    "environment": "contract_validation",
                    "version": collector_version(),
                },
                capabilities=capabilities,
            )
            collector_id = collector.get("collector_id") or collector.get("id")
            source = client.register_source(
                project_id=project_id,
                payload={"name": "collector-contract-validation", "source_type": "unknown_text"},
                capabilities=capabilities,
            )
            sync = client.create_sync(
                source_id=source.source_id,
                payload={
                    "sync_id": "contract-validation",
                    "collector_id": collector_id,
                    "diagnostics": {"mode": "contract_validation"},
                },
                capabilities=capabilities,
            )
            sync_id = sync.get("sync_id", "contract-validation")
            content = "OpsIncident Collector contract validation sample. [REDACTED_SECRET]"
            client.batch_upload_documents(
                project_id=project_id,
                source_id=source.source_id,
                sync_id=sync_id,
                collector_id=collector_id,
                documents=[
                    {
                        "external_id": "contract-validation/sample.txt",
                        "path": "contract-validation/sample.txt",
                        "source_type": "unknown_text",
                        "content": content,
                        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        "metadata": {"contract_validation": True},
                        "size_bytes": len(content.encode("utf-8")),
                        "modified_at": None,
                    }
                ],
                capabilities=capabilities,
            )
            client.update_sync(
                source_id=source.source_id,
                sync_id=sync_id,
                payload={"status": "success", "diagnostics": {"contract_validation": True}},
                capabilities=capabilities,
            )
            report["sample_uploaded"] = True
            document_batch_upload = True
            supported["document_batch_upload"] = True
        except MissingBatchEndpointError:
            report["errors"].append(MISSING_BATCH_MESSAGE)
        except Exception as exc:
            report["errors"].append(f"sample upload failed: {exc}")

    report["compatible"] = document_batch_upload and not report["errors"]
    if not document_batch_upload and MISSING_BATCH_MESSAGE not in report["errors"]:
        report["errors"].append(MISSING_BATCH_MESSAGE)
    client.close()
    return report


def _merge_openapi_contract(report: dict[str, Any], client: CoreClient) -> None:
    try:
        response = client.client.get("/openapi.json")
        if response.status_code == 404:
            report["warnings"].append("openapi.json unavailable for endpoint discovery")
            return
        response.raise_for_status()
        paths = set((response.json().get("paths") or {}).keys())
    except Exception as exc:
        report["warnings"].append(f"openapi discovery failed: {exc}")
        return

    openapi_features = {
        "source_registry": "/v1/projects/{project_id}/sources" in paths,
        "collector_registration": "/v1/projects/{project_id}/collectors/register" in paths,
        "sync_lifecycle": (
            "/v1/sources/{source_id}/syncs/start" in paths
            and "/v1/sources/{source_id}/syncs/{sync_id}/finish" in paths
        ),
        "document_batch_upload": "/v1/sources/{source_id}/documents/batch" in paths,
        "search": "/v1/search" in paths,
        "investigate": "/v1/investigate" in paths,
    }
    report["features"] = {**report.get("features", {}), **openapi_features}
    discovered_endpoints = {}
    known_paths = {
        "register_source": "/v1/projects/{project_id}/sources",
        "register_collector": "/v1/projects/{project_id}/collectors/register",
        "create_sync": "/v1/sources/{source_id}/syncs/start",
        "batch_upload": "/v1/sources/{source_id}/documents/batch",
        "update_sync": "/v1/sources/{source_id}/syncs/{sync_id}/finish",
        "search": "/v1/search",
        "investigate": "/v1/investigate",
    }
    for name, path in known_paths.items():
        if path in paths:
            discovered_endpoints[name] = path
    report["endpoints"] = {**report.get("endpoints", {}), **discovered_endpoints}
