# Validate RAG Pipeline

`validate-rag-pipeline` is an operational proof command. It validates the Collector side of the data path and optionally checks Core endpoints. It does not generate embeddings, run retrieval locally, call an LLM, or diagnose incidents.

## Local Proof

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --format json
```

This checks path policy, inspection, redaction/normalization dry-run, source coverage, and RAG readiness.

## Core Compatibility

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --project-id proj_123 \
  --api-url http://127.0.0.1:8001 \
  --format json
```

This additionally checks Core `/health`, `/v1/capabilities` when available, and batch document ingestion compatibility.

## Explicit Core Smoke Tests

```bash
opsincident-collector validate-rag-pipeline \
  --path tests/fixtures/basic_project \
  --project-id proj_123 \
  --api-url http://127.0.0.1:8001 \
  --query "What evidence is available for investigation?" \
  --sync \
  --search \
  --investigate \
  --format json
```

Default behavior does not upload, search, or investigate. `--sync`, `--search`, and `--investigate` are explicit. If Core is unavailable or lacks a compatible ingestion endpoint, the command reports that honestly instead of pretending success.
