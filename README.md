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
- daemon mode with health, metrics, structured logs, and retry queue visibility
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
opsincident-collector agent rag-readiness --path ./some-folder --format json
opsincident-collector agent onboard-source --path ./some-folder --export-target api --project-id proj_123
opsincident-collector agent sync-quality --path ./some-folder --project-id proj_123
opsincident-collector agent investigate --path ./some-folder --project-id proj_123 --query "Why did orders slow after deploy?"
opsincident-collector daemon run --config examples/local-daemon.yaml --max-cycles 1
opsincident-collector queue status --config collector.yaml
opsincident-collector validate-rag-pipeline --path ./some-folder --format json
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
- the LangGraph agent runtime orchestrates source onboarding, readiness, sync quality, and Core investigation bridge workflows
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

## LangGraph Agent Runtime

Phase 4 adds LangGraph orchestration for Collector operations only:

- `source_onboarding`: inspect, redaction summary, coverage, readiness, sync planning, approval, sync, post-sync quality.
- `rag_readiness`: offline readiness and eval seed preview.
- `sync_quality`: local sync history and failed upload queue review.
- `investigation_bridge`: readiness checks plus Core `/v1/investigate` call when Core is available.

The graph runtime persists runs, node events, and approval requests in local SQLite. API sync/data
upload pauses for approval unless `--yes` or `--dry-run` is used. Graph state stores safe summaries
only and does not persist raw secrets.

```bash
opsincident-collector agent rag-readiness --path tests/fixtures/basic_project --format json
opsincident-collector agent onboard-source --path tests/fixtures/basic_project --export-target console --dry-run --format json
opsincident-collector agent investigate --path tests/fixtures/basic_project --project-id proj_123 --query "Why did latency increase?" --format json
```

Install agent dependencies with:

```bash
pip install "opsincident-collector[agent]"
docker build --build-arg INSTALL_TARGET=".[mcp,agent]" -t opsincident-collector:agent .
```

LangGraph does not call an LLM here, generate embeddings, use a vector database, or diagnose root
cause locally. Core remains responsible for RAG and investigation.

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

## Daemon and Operations

Phase 5 adds a real-server daemon for edge deployments:

- periodic sync through the same deterministic pipeline used by `sync`
- `/health` JSON endpoint with version, sync, Core reachability, state DB, and retry queue status
- `/metrics` Prometheus text endpoint with sync counters, retry queue depth, uptime, and Core reachability
- JSON structured daemon events such as `daemon_start`, `sync_cycle_complete`, and `core_unavailable`
- queue commands for failed upload visibility and retry

```bash
opsincident-collector daemon run --config examples/local-daemon.yaml --max-cycles 1
opsincident-collector daemon health --host 127.0.0.1 --port 8686
opsincident-collector queue status --config examples/local-daemon.yaml --format json
opsincident-collector queue retry --config examples/production.yaml --format json
```

API upload in daemon mode is refused unless the config explicitly permits unattended upload with `daemon.allow_unattended_upload: true` or disables upload confirmation. Tokens still come from `INCIDENTOPS_TOKEN` or `api.token_env`; raw tokens do not belong in YAML.

`validate-rag-pipeline` proves the Collector-to-Core path without pretending Core success:

```bash
opsincident-collector validate-rag-pipeline --path tests/fixtures/basic_project --format json
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --project-id proj_123 \
  --api-url http://127.0.0.1:8001 \
  --query "What evidence is available for investigation?" \
  --search \
  --investigate \
  --format json
```

By default it does not upload, search, or investigate. Add `--sync`, `--search`, or `--investigate` explicitly for those Core operations.

## AWS Deployment

Collector can run as its own ECS Fargate service, separate from IncidentOps Core. The deployment artifacts in this repo provide:

- `infra/terraform`: ECR, ECS service/task definition, CloudWatch logs, IAM roles, Secrets Manager references, security group wiring, and optional EFS state storage.
- `examples/aws-daemon.yaml`: daemon config for AWS with redaction, allow paths, retry/backoff, health, metrics, and API sync enabled.
- `.github/workflows/deploy-collector.yml`: GitHub OIDC CI/CD for lint, tests, compileall, Docker build, ECR push, ECS deploy, and optional health/RAG smoke checks.
- `scripts/smoke_aws_collector.sh`: health/Core/RAG validation smoke script.

Secrets belong in AWS Secrets Manager, not YAML:

```bash
INCIDENTOPS_API_URL
INCIDENTOPS_TOKEN
PROJECT_ID
SOURCE_NAME
SOURCE_TYPE
COLLECTOR_ENVIRONMENT
COLLECTOR_CONFIG
```

For the flagship demo, the AWS config uses a safe fixture path bundled in the image. For customer deployments, run Collector near the customer's private data and mount only the specific allowed source paths read-only. Collector still does not diagnose, call LLMs, create embeddings, or run retrieval locally; Core remains the RAG and investigation brain.

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

Agent/daemon image:

```bash
docker build --build-arg INSTALL_TARGET=".[mcp,agent]" -t opsincident-collector:agent .
docker run --rm \
  -e INCIDENTOPS_API_URL=http://host.docker.internal:8001 \
  -e INCIDENTOPS_TOKEN=$INCIDENTOPS_TOKEN \
  -e INCIDENTOPS_PROJECT_ID=proj_123 \
  -v "$PWD/examples/daemon.yaml:/etc/opsincident-collector/collector.yaml:ro" \
  -v "$PWD/tests/fixtures/basic_project:/data/basic_project:ro" \
  -v "$PWD/.opsincident-collector:/var/lib/opsincident-collector" \
  opsincident-collector:agent \
  daemon run --config /etc/opsincident-collector/collector.yaml --max-cycles 1
```

See [docs/security-model.md](docs/security-model.md) and [docs/config-reference.md](docs/config-reference.md).
See [docs/langgraph-agent.md](docs/langgraph-agent.md) for Phase 4 graph details.
See [docs/daemon.md](docs/daemon.md), [docs/operations.md](docs/operations.md), and [docs/validate-rag-pipeline.md](docs/validate-rag-pipeline.md) for Phase 5 deployment details.
See [docs/aws-deployment.md](docs/aws-deployment.md) for ECS Fargate, ECR, Secrets Manager, and GitHub Actions deployment.
