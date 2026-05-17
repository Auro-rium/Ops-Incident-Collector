# Operations

Phase 5 adds deployment and operational controls for running the Collector on real servers.

## Retry Queue

Failed API document uploads are stored in SQLite after redaction. Operators can inspect and retry the queue without exposing `payload_json` by default.

```bash
opsincident-collector queue status --config collector.yaml
opsincident-collector queue retry --config collector.yaml
opsincident-collector queue clear --config collector.yaml --failed-before 30 --yes
```

`queue retry` reuses the existing Core API exporter and retry/backoff rules. It requires a Core URL, project id, and token when auth is enabled.

## Structured Logs

Daemon logs are JSON lines. Expected events include:

- `daemon_start`
- `health_server_started`
- `metrics_server_started`
- `sync_cycle_start`
- `sync_cycle_complete`
- `sync_cycle_failed`
- `core_unavailable`
- `daemon_stop`

Logs must not include raw tokens, raw secrets, file content, or queued upload payloads.

## Security Notes

- Mount source folders read-only.
- Run as a non-root user where possible.
- Put API tokens in environment variables, not YAML.
- Keep path allowlists narrow.
- Keep deny patterns active.
- Redaction happens before local export and API upload.
- The Collector does not embed, retrieve, diagnose, or generate incident answers locally.
