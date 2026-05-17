# OpsIncident-Collector is a self-hosted collector, MCP server, and local orchestration runtime that discovers, redacts, normalizes, and syncs backend engineering data into IncidentOps Core for incident investigation.

Bring your logs, code, runbooks, deploy history, incidents, and API docs. OpsIncident-Collector turns them into investigation-ready evidence.

## Status

The repository now includes a hardened deterministic v1 foundation:

- local inspect and validation
- secret redaction and normalization
- JSONL and SQLite export
- SQLite checkpoints for incremental sync
- IncidentOps Core API adapter with capability/fallback behavior
- explicit collector/schema/Core API protocol versioning at export boundaries
- token-env based Core auth without printing token values
- failed upload queue with retry/backoff metadata
- Core-compatible RAG metadata, citation hints, and chunking hints
- source coverage, RAG readiness, eval seed, and Core contract validation commands
- permissioned MCP tool layer and FastMCP server wiring
- deterministic local agent workflow
- polling watch mode

## CLI

```bash
opsincident-collector init
opsincident-collector doctor
opsincident-collector validate --config collector.yaml
opsincident-collector inspect --path ./some-folder
opsincident-collector sync --path ./some-folder --export jsonl --output out.jsonl
opsincident-collector sync --path ./some-folder --export api --project-id proj_123 --yes
opsincident-collector watch --path ./some-folder --export jsonl --output out.jsonl
opsincident-collector coverage --path ./some-folder --format json
opsincident-collector rag-report --path ./some-folder --format json
opsincident-collector eval-seed --path ./some-folder --output eval_seed.jsonl
opsincident-collector validate-core-contract --api-url http://127.0.0.1:8001 --project-id proj_123
opsincident-collector mcp serve --config collector.yaml
opsincident-collector agent investigate --project-id proj_123 --query "Why did orders slow after deploy?"
```

## Local-only mode

The current implementation is useful without IncidentOps Core:

- inspect allowlisted paths
- classify likely source types
- detect unsupported, oversized, denied, empty, and binary files
- detect likely secrets without printing secret values
- redact secrets before JSONL and SQLite export
- skip unchanged files through SQLite checkpoints

`NormalizedDocument` remains the canonical collector document. JSONL exports wrap it in a small protocol envelope:

- `collector_version`
- `schema_version: incidentops.normalized_document.v1`
- `core_api_version: v1`
- `document`

The collector enriches `document.metadata` with advisory fields for Core:

- `citation_hints`: source path and line-range hints for evidence citation.
- `chunking_hints`: optional section/window/function hints for Core's indexer.
- retrieval metadata such as service, environment, endpoints, commits, timestamps, headings, language, and incident fields.

These are hints only. Core still owns canonical chunking, embeddings, indexing, retrieval, reranking, investigation, answers, citations, workflow runs, and eval scoring.

## Core-sync mode

- probes `GET /v1/capabilities` when available
- registers sources and uploads normalized documents
- sends `collector_version`, `schema_version`, and `core_api_version` in batch upload payloads
- maps Collector `checksum` to Core `content_hash` at API upload time
- uses `Authorization: Bearer <token>` from `INCIDENTOPS_TOKEN` or `api.token_env`
- fails API sync clearly when auth is required but no token is present
- queues transient failed document uploads in SQLite and retries due items on later syncs
- falls back to default endpoint contracts when capabilities are absent
- fails clearly if Core does not expose a batch ingestion path

Set tokens with environment variables instead of YAML:

```bash
export INCIDENTOPS_TOKEN=...
opsincident-collector sync --path ./service --export api --project-id proj_123 --yes
```

## MCP and agent mode

- MCP tools call the real Collector pipeline or IncidentOps Core API adapter; they are not decorative wrappers
- XML prompt assets are loaded from `opsincident_collector/prompts/` and exposed to clients without local LLM calls
- permission policy blocks non-allowlisted sensitive reads, denylisted files, and unapproved data export
- the deterministic local agent inspects configured evidence, identifies missing coverage, optionally syncs, and calls Core investigate when reachable
- watch mode refuses unconfirmed API sync before entering the polling loop; use `--yes` or `--dry-run`

Phase 3 MCP tools:

- `inspect_folder`, `validate_source_config`, `preview_redaction`, `sync_source`
- `get_source_coverage`, `get_rag_readiness`, `generate_eval_seed`, `validate_core_contract`
- `search_evidence`, `investigate_incident`, `create_workflow_run`, `get_run_status`, `get_run_events`, `export_report`

MCP resources expose redacted local config, last sync/inspection, local RAG readiness, failed-upload queue summaries, project sources, project coverage, and Core capabilities. Failed upload resources do not expose stored payload JSON.

```bash
opsincident-collector mcp serve --config collector.yaml
opsincident-collector mcp serve --config collector.yaml --dump-schema
```

Typical MCP client flow:

1. `inspect_folder`
2. `get_rag_readiness`
3. `sync_source` with `dry_run=true`
4. `sync_source` with explicit approval
5. `investigate_incident`

Core remains the investigation brain; Collector MCP tools do not invent root cause.

## RAG readiness and eval seeds

```bash
opsincident-collector coverage --path ./service --format json
opsincident-collector rag-report --path ./service --format json
opsincident-collector eval-seed --path ./service --output eval_seed.jsonl
```

`coverage` reports missing recommended source categories. `rag-report` gives a diagnostic score based on logs, code, deploy history, incidents, runbooks, API docs, metadata, and hints. `eval-seed` writes deterministic JSONL cases from local evidence without using an LLM.

Validate Core compatibility without uploading data:

```bash
opsincident-collector validate-core-contract --api-url http://127.0.0.1:8001 --project-id proj_123
```

Use `--with-sample` only when you explicitly want to upload one tiny redacted contract-validation document.

## Security model

- path access is constrained by allowlist and deny patterns
- dangerous files are skipped by default
- inspect does not upload data
- logs never print raw secret values

## Docker

Base image:

```bash
docker build -t opsincident-collector:base .
```

MCP-capable image:

```bash
docker build --build-arg INSTALL_TARGET=".[mcp]" -t opsincident-collector:mcp .
```

See [docs/security-model.md](docs/security-model.md) and [docs/config-reference.md](docs/config-reference.md).
