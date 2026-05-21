# Local-only Mode

Local-only mode runs collection and export without external Core sync.

## Use cases

- Offline incident triage preparation.
- Security-restricted environments with no egress.
- Deterministic artifact generation for review/approval.

## Behavior

```mermaid
flowchart LR
    A[Discovery + Policy] --> B[Normalize + Redact]
    B --> C[Local Export Only]
    C -. no network .-> D[(Core Sync Disabled)]
```

## Operational notes

- Keep redaction enabled even in offline mode.
- Use local checksums/run IDs for reproducibility.
- Promote artifacts to Core only after approval.
