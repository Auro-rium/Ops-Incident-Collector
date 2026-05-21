# OpsIncident Collector

**OpsIncident Collector** is the production-grade edge runtime for IncidentOps RAG pipelines.

It runs near private engineering data, safely discovers files, enforces path policy, redacts secrets, normalizes evidence into `NormalizedDocument`, and exports or syncs that evidence into IncidentOps Core. It also exposes MCP tools and LangGraph workflows for controlled agentic source onboarding, sync approval, readiness checks, and Core investigation bridging.

> Collector prepares safe evidence. Core performs canonical RAG and incident investigation.

No local root-cause diagnosis. No embeddings. No vector database. No LLM calls inside the ingestion pipeline. Apparently restraint is still legal.

---

## Why this exists

Most RAG systems start at the wrong layer: upload files, embed chunks, then panic about secrets, stale docs, missing logs, and garbage citations.

OpsIncident Collector solves the layer before RAG:

```text
private engineering data
  -> path policy
  -> file safety filters
  -> secret redaction
  -> metadata extraction
  -> NormalizedDocument
  -> local export / Core sync
  -> IncidentOps Core indexing + investigation
```

It is built for backend/SRE incident workflows over logs, code, runbooks, incident reports, deploy history, API docs, patches, diffs, and config files.

---

## Architecture boundary

The Collector deliberately does **not** become a second backend.

| Layer | Owns |
|---|---|
| OpsIncident Collector | discovery, filtering, redaction, metadata, `NormalizedDocument`, local export, Core sync, MCP tools, LangGraph orchestration |
| IncidentOps Core | canonical chunking, embeddings, indexing, retrieval, reranking, investigation, answers, citations, workflow runs, eval scoring |

`NormalizedDocument` is the canonical Collector output. Citation hints, chunking hints, and readiness reports are advisory metadata for Core, not a replacement for Core logic.

---

## Main capabilities

### Deterministic collector pipeline

- explicit allowlist roots
- denylist before file reads
- binary/oversized/empty file skipping
- secret redaction before export or sync
- stable `NormalizedDocument` contract
- JSONL, SQLite, console, and Core API exporters
- SQLite checkpoints for incremental sync
- failed upload queue with retry/backoff

### Core-compatible RAG contract

- `collector_version`, `schema_version`, and `core_api_version`
- checksum mapped to Core-compatible `content_hash`
- enriched metadata for service, environment, endpoints, deploy hashes, timestamps, trace/request IDs, headings, language, incident fields, API paths, and config summaries
- citation hints and chunking hints as metadata only
- `coverage`, `rag-report`, `eval-seed`, and `validate-core-contract` commands

### MCP production layer

The MCP server exposes real capabilities backed by the deterministic pipeline and Core adapter: inspect folders, validate configs, preview redaction safely, sync sources with permission checks, check source coverage/readiness, call Core search/investigate/run endpoints, and load XML prompt assets from disk.

### LangGraph orchestration runtime

Collector includes durable CLI-first workflows for source onboarding, RAG readiness, sync quality, and investigation bridging to Core. LangGraph coordinates inspection, readiness checks, sync planning, approval gates, and Core calls. It does not diagnose incidents locally.

### Real-server daemon mode

- periodic sync loop
- graceful shutdown
- health endpoint
- metrics endpoint
- structured operational events
- retry queue visibility
- Docker, Docker Compose, and systemd examples
- unattended upload only when explicitly enabled

---

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[mcp,agent]'
```

With `uv`:

```bash
uv pip install --python .venv/bin/python -e '.[mcp,agent]'
```

Check the CLI:

```bash
opsincident-collector --help
```

---

## Quick start: local-only RAG evidence export

```bash
opsincident-collector inspect --path tests/fixtures/basic_project

opsincident-collector rag-report \
  --path tests/fixtures/basic_project \
  --format json

opsincident-collector sync \
  --path tests/fixtures/basic_project \
  --export jsonl \
  --output /tmp/opsincident-docs.jsonl \
  --dry-run

opsincident-collector eval-seed \
  --path tests/fixtures/basic_project \
  --output /tmp/opsincident-eval-seed.jsonl \
  --format json
```

---

## Sync to IncidentOps Core

Set a token through the environment. Do not put raw tokens in YAML unless you enjoy future regret.

```bash
export INCIDENTOPS_TOKEN='...'
```

Validate Core compatibility:

```bash
opsincident-collector validate-core-contract \
  --api-url http://127.0.0.1:8001 \
  --project-id <PROJECT_ID>
```

Sync documents:

```bash
opsincident-collector sync \
  --path /data/service \
  --api-url http://127.0.0.1:8001 \
  --project-id <PROJECT_ID> \
  --export api \
  --yes
```

Core remains responsible for chunking, embeddings, retrieval, and investigation.

---

## MCP server

```bash
opsincident-collector mcp serve --config examples/mcp.json
opsincident-collector mcp serve --dump-schema
```

The MCP layer exposes tools/resources/prompts for AI clients, but every sensitive action is permissioned. `sync_source` and output-writing operations require data-export approval. `investigate_incident` calls Core; it does not produce a local root cause.

---

## LangGraph workflows

```bash
opsincident-collector agent rag-readiness \
  --path tests/fixtures/basic_project \
  --format json

opsincident-collector agent onboard-source \
  --path tests/fixtures/basic_project \
  --export-target jsonl \
  --dry-run \
  --format json

opsincident-collector agent investigate \
  --path tests/fixtures/basic_project \
  --project-id <PROJECT_ID> \
  --query "What evidence is available for investigation?" \
  --format json
```

The investigation bridge checks local readiness and calls Core `/v1/investigate` when Core is available. If Core is unavailable, it returns readiness and missing-data guidance only.

---

## Daemon mode

```bash
opsincident-collector daemon run \
  --config examples/local-daemon.yaml \
  --max-cycles 1

curl http://127.0.0.1:8686/health
curl http://127.0.0.1:8687/metrics
```

Validate the local RAG pipeline:

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --format json
```

---

## Docker

```bash
docker build -t opsincident-collector:base .

docker build \
  --build-arg INSTALL_TARGET='.[mcp,agent]' \
  -t opsincident-collector:agent .
```

Run local daemon example:

```bash
docker run --rm \
  -v "$PWD/examples/local-daemon.yaml:/etc/opsincident-collector/collector.yaml:ro" \
  -v "$PWD/tests/fixtures/basic_project:/data/basic_project:ro" \
  -v "$PWD/.opsincident-collector:/var/lib/opsincident-collector" \
  opsincident-collector:agent \
  daemon run --config /etc/opsincident-collector/collector.yaml --max-cycles 1
```

---

## Verification

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall opsincident_collector
```

Recent Phase 5 baseline:

```text
ruff: passed
pytest: 72 passed
compileall: passed
Docker base build: passed
Docker [mcp,agent] build: passed
```

---

## Documentation

Start here:

- [docs/README.md](docs/README.md) - documentation index
- [docs/collector-philosophy.md](docs/collector-philosophy.md) - design philosophy and boundaries
- [docs/core-contract.md](docs/core-contract.md) - Collector/Core data contract
- [docs/production-usage.md](docs/production-usage.md) - server and operator usage guide

Detailed docs:

- [docs/architecture.md](docs/architecture.md)
- [docs/config-reference.md](docs/config-reference.md)
- [docs/security-model.md](docs/security-model.md)
- [docs/core-integration.md](docs/core-integration.md)
- [docs/mcp-server.md](docs/mcp-server.md)
- [docs/langgraph-agent.md](docs/langgraph-agent.md)
- [docs/daemon.md](docs/daemon.md)
- [docs/operations.md](docs/operations.md)
- [docs/server-deployment.md](docs/server-deployment.md)
- [docs/validate-rag-pipeline.md](docs/validate-rag-pipeline.md)

---

## Design laws

1. Never trust raw data.
2. Never leak secrets.
3. Never diagnose locally.
4. Never bypass Core for investigation.
5. Never pretend weak evidence is strong.
6. Never let agents roam arbitrary paths.
7. Always normalize.
8. Always version.
9. Always audit.
10. Always fail honestly.
