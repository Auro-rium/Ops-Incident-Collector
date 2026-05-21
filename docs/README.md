# OpsIncident Collector Documentation

This directory documents the production Collector/Edge runtime.

The most important rule: **Collector prepares safe evidence; IncidentOps Core performs canonical RAG and investigation.**

## Start here

| Document | Purpose |
|---|---|
| [collector-philosophy.md](collector-philosophy.md) | Deep design philosophy and non-negotiable boundaries |
| [architecture.md](architecture.md) | System model, pipeline diagrams, and responsibility split |
| [core-contract.md](core-contract.md) | Stable Collector/Core data contract and upload expectations |
| [production-usage.md](production-usage.md) | Operator-facing usage guide for local, Core, MCP, agent, daemon, and Docker modes |
| [security-model.md](security-model.md) | Threat model, redaction, path policy, and permission tiers |
| [config-reference.md](config-reference.md) | Configuration fields and examples |
| [core-integration.md](core-integration.md) | Core sync behavior, capabilities, and fallback contract |
| [mcp-server.md](mcp-server.md) | MCP tools/resources/prompts and permission behavior |
| [langgraph-agent.md](langgraph-agent.md) | LangGraph orchestration workflows and approval model |
| [daemon.md](daemon.md) | Daemon lifecycle, health, metrics, and sync loop |
| [operations.md](operations.md) | Operational checks and queue handling |
| [server-deployment.md](server-deployment.md) | Docker, Docker Compose, and systemd deployment |
| [validate-rag-pipeline.md](validate-rag-pipeline.md) | End-to-end RAG pipeline validation command |

## Current production baseline

The Collector has five completed capability layers:

1. deterministic collector hardening
2. Core-compatible RAG data contract
3. MCP production interface
4. LangGraph orchestration runtime
5. real-server daemon operations

Verification baseline after Phase 5:

```text
ruff check: passed
pytest: 72 passed
compileall: passed
Docker base build: passed
Docker [mcp,agent] build: passed
daemon health: ok
metrics endpoint: ok
validate-rag-pipeline local fixture: passed
```

## Responsibility boundary

Collector owns:

- discovery
- path policy
- filtering
- secret redaction
- metadata extraction
- `NormalizedDocument`
- local export
- Core sync
- MCP surface
- LangGraph orchestration around readiness/sync/Core calls
- daemon operations

Core owns:

- canonical chunking
- embeddings
- indexing
- retrieval
- reranking
- investigation
- answers
- citations
- workflow runs
- eval scoring

If a doc implies the Collector diagnoses incidents locally, that doc is wrong. Fix the doc, not the architecture.
