# Config Reference

Use `examples/collector.yaml` as the reference format. Keep paths explicit and narrow; avoid pointing at your home directory or repository root unless you intend to inspect all supported files beneath it.

Important fields:

- `api.token_env`: environment variable used for Core auth, default `INCIDENTOPS_TOKEN`.
- `api.auth_required`: when true, API sync fails if no token is available.
- `sync.retry_count`: maximum retry attempts for queued upload failures.
- `sync.retry_backoff_seconds`: base exponential backoff for retry failures.
- `security.allow_paths`: the only paths the collector may read.
- `security.deny_patterns`: dangerous and binary files skipped before read/export.

Phase 2 commands use the same allowlist, denylist, redaction, and max-size settings:

- `coverage`
- `rag-report`
- `eval-seed`
- `validate-core-contract`

Environment overrides:

- `INCIDENTOPS_API_URL`
- `INCIDENTOPS_PROJECT_ID`
- `INCIDENTOPS_EDGE_STATE`
- `INCIDENTOPS_TOKEN` or the configured `api.token_env`
