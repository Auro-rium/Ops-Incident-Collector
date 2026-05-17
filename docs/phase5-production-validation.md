# Phase 5 Production Validation

Phase 5 validates the operational Collector path:

- deterministic local inspection
- secret redaction
- NormalizedDocument creation
- local export readiness
- Core capability detection
- optional Core sync
- optional Core search/investigation smoke tests
- daemon health and metrics
- failed-upload queue visibility

The canonical output remains `NormalizedDocument`. Citation and chunking hints remain advisory metadata. Core owns canonical chunking, embeddings, indexing, retrieval, reranking, investigation, citations, workflow runs, and eval scoring.

Recommended local verification:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall opsincident_collector
opsincident-collector daemon run --config examples/local-daemon.yaml --max-cycles 1
opsincident-collector validate-rag-pipeline --path tests/fixtures/basic_project --format json
```
