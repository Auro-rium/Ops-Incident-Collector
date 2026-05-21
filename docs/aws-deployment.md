# AWS Deployment

OpsIncident Collector deploys as a separate ECS Fargate service that syncs `NormalizedDocument` payloads into IncidentOps Core. It does not diagnose incidents, call LLMs, generate embeddings, run retrieval, or replace Core.

## Target Architecture

- ECS Fargate service: `incidentops-collector`
- ECR repository for the Collector image
- CloudWatch Logs for daemon JSON logs
- Secrets Manager for Core URL, token, project/source values, and optional config path
- Optional EFS mount for SQLite state and failed-upload retry queue
- Internal health endpoint on `8686`
- Internal Prometheus metrics endpoint on `8687`

Collector should run near the private engineering data it is allowed to read. For a flagship AWS demo it can sync the safe fixture path included in the image. For a customer deployment, run it in the customer's account/VPC or as close as possible to customer-owned logs, code snapshots, deploy history, runbooks, incidents, and API docs.

## Runtime Config

Use `examples/aws-daemon.yaml` for the demo baseline. It is configured for daemon API sync, health, metrics, retry queue persistence, redaction, and narrow allow paths.

Runtime values should come from Secrets Manager-backed environment variables:

- `INCIDENTOPS_API_URL`: IncidentOps Core API URL.
- `INCIDENTOPS_TOKEN`: Collector API token.
- `PROJECT_ID`: Core project id. `INCIDENTOPS_PROJECT_ID` is also supported locally.
- `SOURCE_NAME`: source name override for daemon sync.
- `SOURCE_TYPE`: source type override, usually `filesystem` or `logs_folder`.
- `COLLECTOR_ENVIRONMENT`: environment label such as `aws-demo`, `staging`, or `prod`.
- `COLLECTOR_CONFIG`: optional config path, normally `/app/examples/aws-daemon.yaml`.

Do not put raw tokens in YAML or Docker images.

## Terraform

Terraform lives in `infra/terraform` and accepts existing Core/network values:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=collector.tfvars
terraform apply -var-file=collector.tfvars
```

Minimum variables:

```hcl
aws_region                   = "us-east-1"
vpc_id                       = "vpc-..."
subnet_ids                   = ["subnet-...", "subnet-..."]
ecs_cluster_name             = "incidentops"
core_api_url_secret_arn      = "arn:aws:secretsmanager:..."
incidentops_token_secret_arn = "arn:aws:secretsmanager:..."
project_id_secret_arn        = "arn:aws:secretsmanager:..."
```

The module creates Collector resources only. It does not create Core, RDS, Redis, pgvector, or frontend infrastructure.

## CI/CD

`.github/workflows/deploy-collector.yml` runs:

- Ruff
- pytest
- compileall
- Docker build
- ECR push
- ECS service deployment
- wait for stable
- optional health check
- optional local `validate-rag-pipeline` smoke

Use GitHub OIDC. Do not create long-lived AWS access keys.

Required GitHub configuration:

- Secret `AWS_ROLE_TO_ASSUME`
- Var `AWS_REGION`
- Var `ECR_REPOSITORY`
- Var `ECS_CLUSTER`
- Var `ECS_COLLECTOR_SERVICE`
- Var `ECS_COLLECTOR_TASK_DEFINITION`
- Optional var `COLLECTOR_HEALTH_URL`
- Optional var `CORE_API_URL`
- Optional var `SMOKE_PROJECT_ID`

The ECS service can use a task definition image tag of `latest`; the workflow pushes `latest` and forces a new deployment. If you prefer immutable SHA tags, register a new task definition revision in your deployment pipeline.

## Health and Metrics

Health:

```bash
curl http://collector.internal:8686/health
```

Expected safe fields include:

- `status`
- `core_reachable`
- `last_sync_status`
- `pending_failed_uploads`
- `queue_depth`
- version fields

Metrics:

```bash
curl http://collector.internal:8687/metrics
```

Prometheus metrics include sync counters, retry queue depth, sync timestamps, daemon uptime, and Core reachability.

## Token Rotation

Rotate the Collector token in Core, update the `INCIDENTOPS_TOKEN` Secrets Manager value, then force a new ECS deployment:

```bash
aws ecs update-service \
  --cluster "$ECS_CLUSTER" \
  --service incidentops-collector \
  --force-new-deployment
```

The Collector reads the token from environment at process start and never prints it.

## One-off Operations

Inspect a source in a one-off container or local shell:

```bash
opsincident-collector inspect --path /data/source --format json
```

Run a dry validation without upload:

```bash
opsincident-collector validate-rag-pipeline \
  --path /data/source \
  --api-url "$INCIDENTOPS_API_URL" \
  --project-id "$PROJECT_ID" \
  --format json
```

Run a confirmed one-off sync:

```bash
opsincident-collector sync \
  --path /data/source \
  --export api \
  --api-url "$INCIDENTOPS_API_URL" \
  --project-id "$PROJECT_ID" \
  --source-name "$SOURCE_NAME" \
  --source-type "${SOURCE_TYPE:-filesystem}" \
  --yes \
  --force
```

## Smoke Script

```bash
COLLECTOR_HEALTH_URL=http://collector.internal:8686/health \
CORE_API_URL=https://core.internal \
PROJECT_ID=proj_123 \
scripts/smoke_aws_collector.sh
```

Set `RUN_SYNC=1` only when you intentionally want the script to perform an API sync against the configured safe source.

## Logs and Retry Queue

View logs:

```bash
aws logs tail /ecs/incidentops-collector --follow
```

Inspect and retry the failed-upload queue:

```bash
opsincident-collector queue status --config /app/examples/aws-daemon.yaml --format json
opsincident-collector queue retry --config /app/examples/aws-daemon.yaml --format json
```

Queued payloads are already redacted and are not printed by queue status. Failed uploads remain in SQLite until retry succeeds, retry limits are exhausted, or an operator clears old entries.

## Safety Model

- Keep source mounts read-only.
- Keep allow paths narrow.
- Keep deny patterns active.
- Keep redaction enabled.
- Use Secrets Manager for tokens.
- Use a non-root container user.
- Persist `/var/lib/opsincident-collector` if daemon retry state matters.
- Do not expose health/metrics publicly without a protected route.

Core remains the RAG and investigation brain. Collector only discovers, filters, redacts, normalizes, exports, and syncs evidence.
