# Local-only Mode

Local-only mode supports safe inspection and export without IncidentOps Core:

- path allowlist and denylist enforcement
- empty, oversized, unsupported, and binary file skipping
- secret redaction before export
- `NormalizedDocument` creation
- JSONL export with protocol envelope
- SQLite export and checkpoint state

Use local-only mode when Core is unavailable or when validating what would be uploaded before running API sync.
