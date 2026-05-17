# Agent Instructions

- Keep the collector pipeline deterministic. Do not call LLMs, generate embeddings, or add vector storage in this repo.
- `NormalizedDocument` remains the canonical collector output. Envelopes may add protocol metadata only at export/API boundaries.
- IncidentOps Core owns chunking, retrieval, reranking, investigation, answer generation, citations, workflow runs, and eval scoring.
- The collector owns discovery, path policy, filtering, secret redaction, metadata extraction, local export, Core sync, and the existing MCP surface.
- Never log raw file content, token values, or secret values. Redaction must happen before export or preview.
- Respect allowlists and deny patterns. Do not add free-roaming filesystem behavior.
- Run tests after changes, preferably `.venv/bin/python -m pytest -q`.
- Phase 1 excludes LangGraph, new MCP tools, XML prompt libraries, daemon mode, RAG chunk candidates, and local incident diagnosis.
