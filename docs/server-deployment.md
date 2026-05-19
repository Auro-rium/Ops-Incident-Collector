# Server Deployment

The Collector can run as a CLI, MCP server, LangGraph orchestrator, or daemon. For production edge deployments, use daemon mode with explicit source allowlists and read-only data mounts.

## Docker

```bash
docker build -t opsincident-collector:base .
docker build --build-arg INSTALL_TARGET=".[mcp,agent]" -t opsincident-collector:agent .
```

Run one daemon cycle:

```bash
docker run --rm \
  -e INCIDENTOPS_API_URL=http://host.docker.internal:8001 \
  -e INCIDENTOPS_TOKEN=$INCIDENTOPS_TOKEN \
  -e INCIDENTOPS_PROJECT_ID=proj_123 \
  -v "$PWD/examples/daemon.yaml:/etc/opsincident-collector/collector.yaml:ro" \
  -v "$PWD/tests/fixtures/basic_project:/data/basic_project:ro" \
  -v "$PWD/.opsincident-collector:/var/lib/opsincident-collector" \
  opsincident-collector:agent \
  daemon run --config /etc/opsincident-collector/collector.yaml --max-cycles 1
```

The image creates `/etc/opsincident-collector`, `/var/lib/opsincident-collector`, and `/var/log/opsincident-collector`, then runs as the `opsincident` user.

## Docker Compose

See `examples/docker-compose.collector.yml`. It mounts config and state, mounts source data read-only, exposes health and metrics ports, and points to an external Core URL.

## AWS ECS Fargate

AWS deployment assets are in:

- `infra/terraform`
- `examples/aws-daemon.yaml`
- `.github/workflows/deploy-collector.yml`
- `scripts/smoke_aws_collector.sh`

The Terraform module expects existing VPC, subnet, and ECS cluster values. It creates only Collector-specific resources: ECR, ECS service/task definition, CloudWatch logs, IAM roles, Secrets Manager references, security group wiring, and optional EFS state storage.

See [aws-deployment.md](aws-deployment.md) for the full ECS, Secrets Manager, token rotation, and CI/CD workflow.

## systemd

See:

- `examples/systemd/opsincident-collector.service`
- `examples/systemd/env.example`

Typical setup:

```bash
sudo useradd --system --home /var/lib/opsincident-collector --shell /usr/sbin/nologin opsincident
sudo mkdir -p /etc/opsincident-collector /var/lib/opsincident-collector /var/log/opsincident-collector
sudo chown -R opsincident:opsincident /var/lib/opsincident-collector /var/log/opsincident-collector
sudo cp examples/production.yaml /etc/opsincident-collector/collector.yaml
sudo cp examples/systemd/env.example /etc/opsincident-collector/env
sudo cp examples/systemd/opsincident-collector.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now opsincident-collector
journalctl -u opsincident-collector -f
```

Core remains the investigation brain. The server deployment only operationalizes source access, redaction, normalization, sync, health, metrics, and queue retry.
