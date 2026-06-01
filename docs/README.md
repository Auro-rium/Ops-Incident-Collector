# OpsIncident Collector Documentation

This directory documents the current Collector/Edge runtime.

The active product boundary is simple:

```text
Collector -> deterministic scan/redaction/normalization -> Core batch API -> Core retrieval/investigation/MCP
```

The most important rule: **Collector prepares safe evidence; IncidentOps Core performs canonical RAG, indexing, investigation, citations, evals, and product MCP.**

## Current Documentation Map

| Document | Purpose |
|---|---|
| [collector-philosophy.md](collector-philosophy.md) | Design philosophy and non-negotiable Collector/Core boundaries |
| [architecture.md](architecture.md) | System model, deterministic pipeline, responsibility split, and security path |
| [core-contract.md](core-contract.md) | Stable Collector/Core `NormalizedDocument` contract and upload expectations |
| [production-usage.md](production-usage.md) | Operator-facing usage guide for inspection, sync, daemon, Docker, and validation modes |
| [config-reference.md](config-reference.md) | Configuration precedence, fields, and safe config examples |
| [security-model.md](security-model.md) | Collector threat model, path policy, redaction, and telemetry controls |
| [real-repo-benchmark.md](real-repo-benchmark.md) | Repeatable real repository ingestion benchmark and report schema |

## Current Production Baseline

- Active GitHub workflow: `.github/workflows/deploy-collector.yml`
- Active remote: `Auro-rium/OpsIncident-Collector`
- Latest visible workflow runs validate Ruff, pytest, compileall, Docker build, and Core Azure deploy dispatch.

Collector owns:

- explicit source discovery
- path policy and deny rules
- file safety filtering
- secret redaction
- metadata extraction
- `NormalizedDocument` creation
- local export for review/test workflows
- Core sync through the versioned batch API
- failed upload queue and bounded retry
- daemon health/metrics for private Collector runtime

Core owns:

- canonical chunking
- embeddings
- indexing
- retrieval/reranking
- investigation
- answer generation
- citations
- readiness reports
- workflow runs
- eval scoring
- product MCP surface

If a doc implies the Collector diagnoses incidents locally, bypasses Core, owns embeddings, or exposes product MCP directly, the doc is wrong.

## Documentation Cleanup Result

Kept:

- `collector-philosophy.md`
- `architecture.md`
- `core-contract.md`
- `production-usage.md`
- `config-reference.md`
- `security-model.md`
- `real-repo-benchmark.md`

Removed as stale, too thin, or redundant in the current branch:

- `core-integration.md`
- `local-only-mode.md`
- `langgraph-agent.md`
- `daemon.md`
- `operations.md`
- `server-deployment.md`
- `validate-rag-pipeline.md`
- `phase5-production-validation.md`

Recreate a deleted doc only when it has enough current detail to justify existing.
