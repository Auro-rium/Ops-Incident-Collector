# Local-only Mode

Local-only mode supports safe inspection and export without IncidentOps Core:

- path allowlist and denylist enforcement
- empty, oversized, unsupported, and binary file skipping
- secret redaction before export
- `NormalizedDocument` creation
- JSONL export with protocol envelope
- SQLite export and checkpoint state
- citation and chunking hints stored inside `metadata`
- source coverage and RAG readiness diagnostics
- deterministic eval seed JSONL generation

Use local-only mode when Core is unavailable or when validating what would be uploaded before running API sync.

```bash
opsincident-collector coverage --path ./service --format json
opsincident-collector rag-report --path ./service --format json
opsincident-collector eval-seed --path ./service --output eval_seed.jsonl
```
