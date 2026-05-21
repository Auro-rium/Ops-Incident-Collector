# Configuration Reference

This document defines the collector configuration model, precedence, and recommended patterns.

## Precedence

1. CLI flags
2. Environment variables
3. Config file values
4. Built-in defaults

## Core sections

### `project`
- `id`: stable project identifier used in exports/sync.
- `roots`: explicit filesystem roots allowed for discovery.
- `workspace_name`: optional logical grouping label.

### `discovery`
- `include_globs`: allow patterns for candidate paths.
- `exclude_globs`: deny patterns evaluated before reads.
- `follow_symlinks`: disabled by default for predictable traversal.
- `max_depth`: traversal depth guardrail.

### `filters`
- `max_file_size_bytes`: hard size cutoff.
- `allowed_extensions`: extension allowlist.
- `deny_extensions`: extension denylist.
- `binary_detection`: skip binary-like payloads.

### `redaction`
- `enabled`: must remain true in production profiles.
- `detectors`: token/key/pattern detector set.
- `replacement`: redaction placeholder template.
- `emit_redaction_summary`: include counts and categories only.

### `export`
- `local_output_path`: local artifact destination.
- `format`: jsonl/json bundle mode.
- `batch_size`: emission batching.

### `core_sync`
- `enabled`: allow outbound Core sync.
- `base_url`: Core API base endpoint.
- `auth_mode`: token/profile auth mode.
- `timeout_seconds`: request timeout.
- `retry`: bounded retry policy.

## Minimal example

```yaml
project:
  id: incident-prod-checkout
  roots: ["/workspace/repo"]

discovery:
  include_globs: ["**/*.md", "**/*.yml", "**/*.json", "**/*.py"]
  exclude_globs: ["**/.git/**", "**/node_modules/**", "**/.venv/**"]

filters:
  max_file_size_bytes: 2097152

redaction:
  enabled: true
  emit_redaction_summary: true

export:
  format: jsonl
  local_output_path: ./artifacts/normalized.jsonl
```

## Validation checklist

- Root paths are explicit and minimal.
- Excludes contain credential stores and generated folders.
- File size caps are set for predictable runtime.
- Redaction is enabled for all non-test profiles.
