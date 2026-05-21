# Production Usage Guide

This guide shows how to run OpsIncident Collector as a local CLI, Core sync client, MCP server, LangGraph workflow runner, and real-server daemon.

The Collector never owns incident diagnosis. It prepares evidence and calls IncidentOps Core when investigation is needed.

## Local inspection

Use local inspection before any sync:

```bash
opsincident-collector inspect --path /data/service
```

Use JSON output for automation:

```bash
opsincident-collector inspect --path /data/service --format json
```

Inspection is read-only and should not upload anything.

## Local RAG readiness

```bash
opsincident-collector coverage --path /data/service --format json
opsincident-collector rag-report --path /data/service --format json
```

A weak readiness report usually means missing source categories. Common examples:

- logs missing: runtime investigation will be weak
- deploy history missing: deploy-regression investigation will be weak
- incidents missing: previous-incident lookup unavailable
- runbooks missing: remediation suggestions may be generic

The correct response to weak input is not fake confidence. Tragic, but useful.

## Local export

Export redacted `NormalizedDocument` records:

```bash
opsincident-collector sync \
  --path /data/service \
  --export jsonl \
  --output normalized-documents.jsonl \
  --dry-run
```

SQLite export is useful for local inspection and repeatable tests:

```bash
opsincident-collector sync \
  --path /data/service \
  --export sqlite \
  --output local-documents.sqlite \
  --dry-run
```

## Core sync

Set a token:

```bash
export INCIDENTOPS_TOKEN='...'
```

Validate Core compatibility:

```bash
opsincident-collector validate-core-contract \
  --api-url http://127.0.0.1:8001 \
  --project-id <PROJECT_ID>
```

Sync:

```bash
opsincident-collector sync \
  --path /data/service \
  --api-url http://127.0.0.1:8001 \
  --project-id <PROJECT_ID> \
  --export api \
  --yes
```

If Core lacks compatible ingestion, use JSONL export and fix Core. Do not pretend a sync worked. Fake success is worse than failure because now the system is confidently wrong.

## MCP server

Run:

```bash
opsincident-collector mcp serve --config examples/mcp.json
```

Inspect schema:

```bash
opsincident-collector mcp serve --dump-schema
```

Typical tool sequence:

1. `inspect_folder`
2. `get_rag_readiness`
3. `preview_redaction`
4. `sync_source` with `dry_run=true`
5. `sync_source` with approval
6. `investigate_incident`

`investigate_incident` calls Core. It does not diagnose locally.

## LangGraph workflows

RAG readiness:

```bash
opsincident-collector agent rag-readiness \
  --path /data/service \
  --format json
```

Source onboarding:

```bash
opsincident-collector agent onboard-source \
  --path /data/service \
  --project-id <PROJECT_ID> \
  --export-target api \
  --dry-run \
  --format json
```

Investigation bridge:

```bash
opsincident-collector agent investigate \
  --path /data/service \
  --project-id <PROJECT_ID> \
  --query "Why did latency increase?" \
  --format json
```

If the graph requires approval, it persists an approval request and prints resume/approval information. Data export actions must be approved unless explicitly dry-run or configured for unattended daemon operation.

## Daemon mode

Run a daemon locally:

```bash
opsincident-collector daemon run \
  --config examples/local-daemon.yaml \
  --max-cycles 1
```

Health:

```bash
curl http://127.0.0.1:8686/health
```

Metrics:

```bash
curl http://127.0.0.1:8687/metrics
```

In production, mount source folders read-only and keep state under `/var/lib/opsincident-collector`.

## Queue operations

Check failed uploads:

```bash
opsincident-collector queue status --config examples/production.yaml --format json
```

Retry due uploads:

```bash
opsincident-collector queue retry --config examples/production.yaml --format json
```

Clear old failed records only when you understand what you are deleting:

```bash
opsincident-collector queue clear --config examples/production.yaml --failed-before 30 --yes
```

No queue command should print raw payload JSON by default.

## Validate the full RAG pipeline

Local validation:

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --format json
```

Core validation:

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --project-id <PROJECT_ID> \
  --api-url http://127.0.0.1:8001 \
  --query "What evidence is available for investigation?" \
  --search \
  --investigate \
  --format json
```

By default, validation does not upload, search, or investigate. Use `--sync`, `--search`, and `--investigate` explicitly.

## Production deployment checklist

- [ ] run as non-root user
- [ ] mount source folders read-only
- [ ] store state under `/var/lib/opsincident-collector`
- [ ] use `INCIDENTOPS_TOKEN` or configured token env var
- [ ] keep raw tokens out of YAML
- [ ] enable health and metrics endpoints
- [ ] monitor retry queue depth
- [ ] validate Core contract before enabling unattended upload
- [ ] confirm daemon config explicitly allows unattended upload if using API sync
- [ ] keep redaction enabled
- [ ] keep path allowlists narrow

## Verification commands

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall opsincident_collector

docker build -t opsincident-collector:base .
docker build --build-arg INSTALL_TARGET='.[mcp,agent]' -t opsincident-collector:agent .
```

The point of production usage is not to show off commands. It is to prove the Collector can run near real data without leaking, guessing, or silently lying.
