# Real Repo Ingestion Benchmark

This benchmark proves that Collector can ingest a real backend repository into IncidentOps Core safely and repeatedly. It is a repo/code/docs ingestion benchmark, not an incident-investigation benchmark.

## Command

```bash
export INCIDENTOPS_API_URL=http://127.0.0.1:8001
export INCIDENTOPS_TOKEN=...
export INCIDENTOPS_PROJECT_ID=<project-id>

opsincident-collector benchmark \
  --repo-url https://github.com/nsidnev/fastapi-realworld-example-app.git \
  --source-name phase1-fastapi-realworld-example-app \
  --query "Where are article routes and authentication dependencies defined?" \
  --output benchmarks/reports/fastapi-realworld-example-app.json
```

The command:

1. Clones the public repo into a benchmark workspace.
2. Inspects supported, unsupported, denied, binary, empty, and oversized files.
3. Syncs all normalized documents to Core.
4. Syncs the same content again with `force=True` so Core must report unchanged documents instead of relying only on Collector checkpoints.
5. Modifies one copied benchmark file.
6. Syncs again to prove changed-file replacement.
7. Runs `/v1/search` for a sample query.
8. Writes a JSON report.

## Report Schema

The formal JSON Schema lives at `benchmarks/real_repo_benchmark.schema.json`.

Top-level fields:

- `schema_version`: currently `incidentops.real_repo_benchmark.v1`.
- `generated_at`: UTC timestamp.
- `benchmark_started_at` / `benchmark_finished_at`: UTC benchmark bounds.
- `repo_url`, `branch`, `commit_sha`: the public repo identity that was benchmarked.
- `files_seen`, `files_skipped`, `skip_reasons`, `unsupported_extensions`: scan and skip summary.
- `normalized_documents`, `documents_synced`, `source_type_counts`, `redaction_count`: Collector normalization summary.
- `chunks_created`, `latest_core_sync_status`, `parser_errors`: Core ingest summary from the first sync.
- `search_queries`: one entry per search query with `search_result_count` and `top_evidence_paths`.
- `repeat_sync_skipped_unchanged`, `changed_file_path`, `changed_file_update_detected`, `duplicate_chunks_after_update`: idempotency/update checks.
- `repo`: source URL or local input path plus copied benchmark path.
- `inspection`: Collector inspection summary, including files seen, skipped files, skip reasons, supported extensions, unsupported extensions, likely source types, and possible secret count.
- `syncs`: three sync records: `initial`, `same_content_resync`, and `changed_file_resync`.
- `changed_file`: copied repo-relative path changed before the third sync.
- `checks`: derived pass/fail counters for unchanged resync duplicate chunks and changed-file updates.
- `search`: first `/v1/search` timing and result payload or error, retained for backwards compatibility with earlier reports.

Each sync record contains:

- `collector`: `SyncSummary`, including files seen, files skipped, documents normalized/synced, redaction count, failed uploads, source type counts, unsupported extensions, and duration.
- `core`: latest Core sync status when Core exposes `/v1/sources/{source_id}/syncs/latest`, including documents received, chunks created, diagnostics, and coverage.

## Expected Signals

- Initial sync creates documents and chunks.
- Same-content resync has high `skipped_unchanged` in Core diagnostics and `last_batch_chunks_created` equal to `0`.
- Changed-file resync reports at least one updated document and creates replacement chunks for the changed file.
- Search returns cited evidence from the repo.
- Unsupported or denied files are skipped with explicit reasons.
- Redaction count is reported without exposing secret values.

## Recommended Repos

Phase 1 targets:

- `tiangolo/full-stack-fastapi-template`
- `encode/starlette`

Do not start with very large repos such as PostHog or Saleor. Use them later as scale stress tests after the basic ingestion loop is proven.
