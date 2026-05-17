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

Auth uses `Authorization: Bearer <token>`. Prefer `api.token_env` with `INCIDENTOPS_TOKEN`; raw YAML tokens remain a compatibility fallback and should not be used for shared configs. Future token rotation should happen outside the collector process by rotating the referenced environment variable or runtime secret.

The exporter probes `GET /v1/capabilities`, then uses advertised endpoints or default v1 paths. If Core lacks a batch ingestion endpoint, sync fails clearly and recommends JSONL export instead.

Transient upload failures are queued in local SQLite after redaction. Later syncs retry due items with exponential backoff. Non-retryable 4xx validation failures are marked exhausted so they do not loop forever.
