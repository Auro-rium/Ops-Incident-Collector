# MCP Server

OpsIncident Collector exposes a real MCP integration layer over the deterministic Collector
pipeline and the IncidentOps Core API adapter. It is not a local diagnosis engine: Core remains
responsible for retrieval, reranking, investigation, answer generation, citations, workflow runs,
and eval scoring.

## Run

```bash
opsincident-collector mcp serve --config collector.yaml
```

Phase 3 supports stdio transport for local AI clients. The MCP optional dependency is packaged as
`opsincident-collector[mcp]`.

```bash
opsincident-collector mcp serve --config collector.yaml --dump-schema
```

## Tools

- `inspect_folder`: calls the real local inspection pipeline and returns inspection plus coverage.
- `validate_source_config`: loads and validates Collector config without exposing tokens.
- `preview_redaction`: allowlisted sensitive read with redacted preview only.
- `sync_source`: runs the deterministic sync pipeline; non-dry-run export requires approval.
- `get_source_coverage`: returns local coverage or Core source registry data when available.
- `get_rag_readiness`: returns the Phase 2 RAG readiness report.
- `search_evidence`: calls Core `/v1/search`.
- `investigate_incident`: calls Core `/v1/investigate`; no local diagnosis fallback.
- `create_workflow_run`: calls Core `/v1/runs`; requires DATA_EXPORT approval.
- `get_run_status`: calls Core run status.
- `get_run_events`: calls Core run events.
- `export_report`: exports Core run data or local readiness data; writing output requires approval.
- `generate_eval_seed`: deterministically generates eval seed cases; writing output requires approval.
- `validate_core_contract`: validates Core health/capabilities; sample upload requires approval.

## Resources

- `incidentops://local/config`
- `incidentops://local/last-inspection`
- `incidentops://local/last-sync`
- `incidentops://local/rag-readiness`
- `incidentops://local/failed-uploads`
- `incidentops://project/{project_id}/sources`
- `incidentops://project/{project_id}/coverage`
- `incidentops://project/{project_id}/core-capabilities`

Resources redact tokens and do not expose failed upload payload content.

## XML Prompts

Prompt XML files live under `opsincident_collector/prompts/` and are loaded from disk:

- `source_coverage_review`
- `sync_decision`
- `rag_readiness_report`
- `incident_setup_planner`
- `post_sync_quality_gate`
- `core_investigation_bridge`
- `missing_data_advisor`

These prompts are assets for MCP clients. The Collector does not call an LLM and does not infer root
cause locally.

## Permission Model

- `READ_ONLY` is allowed by default.
- `LOCAL_SENSITIVE_READ` requires an allowlisted path and cannot read denylisted files.
- `DATA_EXPORT` requires explicit approval unless the operation is dry-run.
- `EXTERNAL_WRITE` is disabled.

MCP tool calls write safe audit events for sensitive reads and export/write operations. Audit payloads
include tool name, permission decision, path/project/run identifiers where relevant, and never raw
secrets or raw document payloads.

## Example Flow

1. `inspect_folder` on the service/log folder.
2. `get_rag_readiness` to identify missing source categories.
3. `sync_source` with `dry_run=true`.
4. `sync_source` with approval if the dry-run is acceptable.
5. `investigate_incident` to call Core once evidence is synced.
