# Collector/Core Contract

This document defines the boundary between OpsIncident Collector and IncidentOps Core.

The contract is intentionally simple:

```text
Collector emits NormalizedDocument.
Core chunks, embeds, indexes, retrieves, investigates, cites, and evaluates.
```

## Canonical object

`NormalizedDocument` is the canonical Collector output.

Collector may enrich metadata, but it does not send canonical chunks as the primary ingestion unit.

Expected document fields:

```json
{
  "external_id": "logs/app.log",
  "path": "logs/app.log",
  "source_type": "logs",
  "content": "redacted content",
  "content_hash": "sha256:...",
  "metadata": {},
  "size_bytes": 12345,
  "modified_at": "2026-05-17T10:00:00Z"
}
```

Collector may use `checksum` internally. At Core upload time, the API adapter maps checksum to Core-compatible `content_hash`.

## Protocol envelope

Batch upload payloads include version fields:

```json
{
  "collector_version": "0.1.0",
  "schema_version": "incidentops.normalized_document.v1",
  "core_api_version": "v1",
  "documents": []
}
```

These fields exist because Core and Collector will evolve. Silent contract drift is software's favorite way of wasting a weekend.

## Metadata hints

Collector adds advisory metadata for Core:

```json
{
  "service_name": "orders",
  "environment": "prod",
  "endpoint_candidates": ["/v1/orders"],
  "deploy_hashes": ["abc1234"],
  "commit_shas": ["abc1234..."],
  "timestamp_start": "2026-05-17T10:00:00Z",
  "timestamp_end": "2026-05-17T10:30:00Z",
  "trace_ids": ["trace-001"],
  "request_ids": ["req-001"],
  "log_levels": {"ERROR": 4, "WARN": 12},
  "citation_hints": [],
  "chunking_hints": []
}
```

Hints are not commands. Core may use them, refine them, or ignore them.

## Citation hints

Citation hints help Core build evidence references.

```json
{
  "path": "logs/orders.log",
  "relative_path": "logs/orders.log",
  "start_line": 120,
  "end_line": 180,
  "label": "error_window",
  "reason": "contains repeated timeout errors",
  "confidence": 0.8
}
```

## Chunking hints

Chunking hints help Core decide likely structure. They do not replace Core chunking.

```json
{
  "type": "log_window",
  "start_line": 120,
  "end_line": 180,
  "priority": "high",
  "reason": "dense error window",
  "metadata": {"level": "ERROR"}
}
```

## Current Core expectations

The current IncidentOps Core repository has:

- source registry
- collector registration
- sync lifecycle endpoints
- normalized document batch ingest
- central indexer at `incidentops/ingestion/indexer.py`
- document uniqueness on `(project_id, source_id, external_id)`
- unchanged document skip on same `external_id` + `content_hash`
- reindex on same `external_id` + changed `content_hash`
- per-document failure isolation inside batch ingestion

Collector must preserve this behavior by uploading normalized documents, not pre-chunked canonical records.

## Required Core endpoints

Collector can operate locally without Core. Core-sync mode currently expects these Core endpoints:

```text
GET    /health
GET    /v1/capabilities
POST   /v1/projects/{project_id}/sources
GET    /v1/projects/{project_id}/sources
POST   /v1/projects/{project_id}/collectors/register
POST   /v1/sources/{source_id}/syncs/start
POST   /v1/sources/{source_id}/documents/batch
POST   /v1/sources/{source_id}/syncs/{sync_id}/finish
GET    /v1/sources/{source_id}/syncs/latest
POST   /v1/search
POST   /v1/investigate
POST   /v1/runs
GET    /v1/runs/{run_id}
GET    /v1/runs/{run_id}/events
GET    /v1/projects/{project_id}/readiness
GET    /v1/runtime/status
```

If Core does not expose a compatible document ingestion endpoint, Collector must fail clearly and suggest local JSONL export.

## Auth

Collector uses bearer token auth:

```bash
export INCIDENTOPS_TOKEN='...'
```

Config should reference the environment variable:

```yaml
api:
  token_env: INCIDENTOPS_TOKEN
```

Raw tokens should not be committed to YAML. Revolutionary security insight, somehow still necessary.

## Validation

Use:

```bash
opsincident-collector validate-core-contract \
  --api-url http://127.0.0.1:8001 \
  --project-id <PROJECT_ID>
```

Use `--with-sample` only when intentionally uploading a tiny redacted contract sample.

## Current contract notes

- Core accepts optional batch protocol metadata:
  - `collector_version`
  - `schema_version`
  - `core_api_version`
- Core exposes its limit and endpoint templates through `/v1/capabilities`.
- Core now reports runtime mode through `/v1/runtime/status`, which is useful for detecting cloud-vs-local fallback before starting a real sync.

## Non-negotiable boundary

Collector does not own:

- canonical chunking
- embeddings
- retrieval
- reranking
- root-cause hypotheses
- answer generation
- citation selection
- eval scoring

Those belong to Core.
