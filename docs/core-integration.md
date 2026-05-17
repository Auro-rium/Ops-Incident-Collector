# Core Integration

OpsIncident Collector keeps `NormalizedDocument` as its canonical internal output. API upload wraps batches with protocol metadata:

```json
{
  "collector_version": "0.1.0",
  "schema_version": "incidentops.normalized_document.v1",
  "core_api_version": "v1",
  "documents": []
}
```

At the API boundary, Collector maps internal `checksum` to Core `content_hash` and sends source-relative paths where available:

```json
{
  "external_id": "fixture:logs/app.log",
  "path": "logs/app.log",
  "source_type": "logs",
  "content": "...redacted text...",
  "content_hash": "sha256 hex digest",
  "metadata": {
    "citation_hints": [],
    "chunking_hints": []
  },
  "size_bytes": 123,
  "modified_at": "2026-05-05T10:00:00Z"
}
```

`citation_hints` and `chunking_hints` are advisory. Core owns canonical chunking, embeddings, retrieval, reranking, investigation, generated answers, citations, workflow runs, and eval scoring.

Auth uses `Authorization: Bearer <token>`. Prefer `api.token_env` with `INCIDENTOPS_TOKEN`; raw YAML tokens remain a compatibility fallback and should not be used for shared configs. Future token rotation should happen outside the collector process by rotating the referenced environment variable or runtime secret.

The exporter probes `GET /v1/capabilities`, then uses advertised endpoints or default v1 paths. If Core lacks a batch ingestion endpoint, sync fails clearly and recommends JSONL export instead.

Transient upload failures are queued in local SQLite after redaction. Later syncs retry due items with exponential backoff. Non-retryable 4xx validation failures are marked exhausted so they do not loop forever.

Use contract validation before wiring a new Core deployment:

```bash
opsincident-collector validate-core-contract --api-url http://127.0.0.1:8001 --project-id proj_123
```

The command calls health and capabilities without uploading data. Add `--with-sample` only when a tiny redacted validation document may be uploaded.
