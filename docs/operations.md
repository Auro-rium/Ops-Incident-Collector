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

## AWS Operations

For ECS Fargate deployments, use `examples/aws-daemon.yaml` and the Terraform module in `infra/terraform`.

Required Secrets Manager-backed environment variables:

- `INCIDENTOPS_API_URL`
- `INCIDENTOPS_TOKEN`
- `PROJECT_ID`
- `SOURCE_NAME`
- `SOURCE_TYPE`
- `COLLECTOR_ENVIRONMENT`
- `COLLECTOR_CONFIG` when overriding the default config path

Health and metrics should stay internal or behind a protected route:

```bash
curl http://collector.internal:8686/health
curl http://collector.internal:8687/metrics
```

Run the AWS smoke script from an environment that can reach Collector and Core:

```bash
COLLECTOR_HEALTH_URL=http://collector.internal:8686/health \
CORE_API_URL=https://core.internal \
PROJECT_ID=proj_123 \
scripts/smoke_aws_collector.sh
```

Rotate the Collector token by updating the `INCIDENTOPS_TOKEN` secret and forcing a new ECS deployment. The token is read at process start and is never logged.

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
