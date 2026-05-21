# Operations Runbook

## Daily checks

1. Verify collector service health/readiness.
2. Confirm recent run success rate and latency bands.
3. Review redaction summary trends.
4. Review sync failures and retry exhaustion.

## Incident triage flow

```mermaid
flowchart LR
    A[Alert: failed/degraded run] --> B[Check run summary]
    B --> C{Failure class}
    C -->|Policy| D[Fix config/patterns]
    C -->|Read/Parse| E[Inspect file class/limits]
    C -->|Sync| F[Check Core connectivity/auth]
    D --> G[Re-run deterministic profile]
    E --> G
    F --> G
```

## Key metrics

- Files scanned / included / denied.
- Redactions by detector/category.
- Run duration and per-stage timing.
- Export/sync success rate.
- Approval turnaround for gated actions.

## Change management

- Stage config changes in local-only mode.
- Compare run summaries before production rollout.
- Promote with explicit approval + rollback plan.
