# LangGraph Agent Runtime

Phase 4 adds a LangGraph orchestration runtime around existing Collector operations. It does not
turn the Collector into an incident diagnosis agent.

Core remains responsible for chunking, embeddings, indexing, retrieval, reranking, investigation,
answer generation, citations, workflow runs, and eval scoring. Collector LangGraph workflows only
coordinate safe local source access, readiness checks, approval gates, sync, and calls into Core.

## Graphs

- `source_onboarding`: validates a path, inspects files, summarizes redaction risk, computes coverage/readiness, plans sync, waits for approval if needed, runs sync through the deterministic pipeline, and reports post-sync quality.
- `rag_readiness`: read-only offline graph for inspection, coverage, RAG readiness, and deterministic eval seed preview.
- `sync_quality`: reviews local sync history, failed upload queue depth, coverage, and readiness.
- `investigation_bridge`: checks Core health/capabilities, optionally inspects local sources, optionally syncs with approval, then calls Core `/v1/investigate`.

## Approval Model

Approval is required for API sync/data upload. Pending approvals are persisted in local SQLite:

- `graph_runs`
- `graph_events`
- `graph_approvals`

Approval payloads contain only safe summaries: graph name, path, project ID, action, risk level,
and document counts. They do not include raw file content, raw secrets, tokens, or failed upload
payload JSON.

## CLI Examples

```bash
opsincident-collector agent rag-readiness \
  --path tests/fixtures/basic_project \
  --format json
```

```bash
opsincident-collector agent onboard-source \
  --path tests/fixtures/basic_project \
  --export-target jsonl \
  --dry-run \
  --format json
```

```bash
opsincident-collector agent investigate \
  --path tests/fixtures/basic_project \
  --project-id proj_123 \
  --query "Why did latency increase?" \
  --format json
```

If a graph stops at approval, approve or reject the persisted action:

```bash
opsincident-collector agent onboard-source --approve approval_abc123
opsincident-collector agent onboard-source --reject approval_abc123
```

## Dependency

Install the agent extra when building a LangGraph-capable runtime:

```bash
pip install "opsincident-collector[agent]"
docker build --build-arg INSTALL_TARGET=".[mcp,agent]" -t opsincident-collector:agent .
```

If the dependency is missing, the CLI fails clearly:

```text
LangGraph dependency not installed. Install with `pip install 'opsincident-collector[agent]'`.
```

## Boundaries

The Collector does not:

- call an LLM
- generate embeddings
- use a vector database
- diagnose root cause locally
- generate final incident answers locally
- bypass Core investigation
- bypass path policy or DATA_EXPORT approval
- return raw secrets

Core remains the RAG and investigation brain.
