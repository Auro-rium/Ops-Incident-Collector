# Daemon Mode

`opsincident-collector daemon run` turns the Collector into a long-running edge service. It does not add local diagnosis, embeddings, retrieval, or a second Core backend. It only schedules the existing deterministic sync pipeline and exposes operational endpoints.

## Command

```bash
opsincident-collector daemon run --config /etc/opsincident-collector/collector.yaml
opsincident-collector daemon run --config examples/local-daemon.yaml --max-cycles 1
```

The daemon:

- loads and validates config before start
- checks allowlisted source paths
- refuses API export unless unattended upload is explicitly allowed
- runs periodic sync through `run_sync`
- exposes `/health` and `/metrics`
- updates SQLite sync history and failed-upload queue state
- handles `SIGINT` and `SIGTERM` gracefully
- emits JSON structured logs without tokens or raw content

## Health

```bash
opsincident-collector daemon health --host 127.0.0.1 --port 8686
```

`GET /health` returns version fields, daemon start time, last sync timestamps, last error, failed upload queue depth, Core reachability, and state DB writability.

Status values:

- `ok`: loop is running, state DB is writable, and no recent operational problem is known.
- `degraded`: failed uploads are pending, Core is unavailable, or the last sync failed while the daemon can keep running.
- `error`: state DB/config is unusable or the loop crashed permanently.

## Metrics

`GET /metrics` returns Prometheus text exposition for sync counters, retry queue depth, timestamps, readiness score placeholder, uptime, and Core reachability.

Core remains responsible for chunking, embeddings, retrieval, reranking, investigation, and answer generation.
