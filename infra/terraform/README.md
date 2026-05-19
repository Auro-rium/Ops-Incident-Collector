# OpsIncident Collector Terraform

This module deploys the Collector as an independent ECS Fargate service. It intentionally accepts existing networking and ECS inputs so it does not duplicate IncidentOps Core infrastructure.

## Creates

- ECR repository for the Collector image.
- ECS task definition and service named `incidentops-collector`.
- CloudWatch log group.
- ECS execution and task IAM roles.
- Secrets Manager environment references for Core URL, token, project/source values, and collector config path.
- Optional EFS volume for SQLite state and failed-upload retry queue persistence.
- Optional Collector security group with outbound access.
- Optional Core security group ingress rule from Collector to `core_api_port`.

## Required Inputs

```hcl
aws_region                  = "us-east-1"
vpc_id                      = "vpc-..."
subnet_ids                  = ["subnet-...", "subnet-..."]
ecs_cluster_name            = "incidentops"
core_api_url_secret_arn     = "arn:aws:secretsmanager:..."
incidentops_token_secret_arn = "arn:aws:secretsmanager:..."
project_id_secret_arn       = "arn:aws:secretsmanager:..."
core_security_group_id      = "sg-..." # optional
core_api_port               = 443      # or 8001 for an internal Core API
```

`core_api_url_secret_arn` should resolve to the `INCIDENTOPS_API_URL` value, not a raw token bundle. Keep the Collector token separate so it can be rotated independently.

## Deploy

```bash
terraform init
terraform plan -var-file=collector.tfvars
terraform apply -var-file=collector.tfvars
```

Push the image to the output `ecr_repository_url`, then force a new deployment or use the GitHub Actions workflow in this repo.

The Collector does not diagnose incidents, call LLMs, create embeddings, or run retrieval locally. It only reads allowlisted sources, redacts, normalizes, and syncs `NormalizedDocument` payloads into Core.
