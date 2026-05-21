variable "aws_region" {
  description = "AWS region for Collector resources."
  type        = string
}

variable "name_prefix" {
  description = "Prefix for Collector AWS resources."
  type        = string
  default     = "incidentops-collector"
}

variable "vpc_id" {
  description = "Existing VPC ID. Core/network infrastructure is not created here."
  type        = string
}

variable "subnet_ids" {
  description = "Existing subnet IDs for the Collector ECS service."
  type        = list(string)
}

variable "ecs_cluster_name" {
  description = "Existing ECS cluster name or ARN."
  type        = string
}

variable "security_group_ids" {
  description = "Additional security groups to attach to the Collector service."
  type        = list(string)
  default     = []
}

variable "create_security_group" {
  description = "Whether to create a Collector security group with outbound Core access."
  type        = bool
  default     = true
}

variable "core_security_group_id" {
  description = "Optional Core API security group ID. When set, the Collector SG gets explicit HTTPS egress to it."
  type        = string
  default     = null
}

variable "core_api_port" {
  description = "Core API port allowed from Collector when core_security_group_id is set."
  type        = number
  default     = 443
}

variable "assign_public_ip" {
  description = "Assign a public IP to Fargate tasks. Prefer false in private subnets."
  type        = bool
  default     = false
}

variable "desired_count" {
  description = "Collector daemon task count. Keep one unless you intentionally coordinate shared source/state access."
  type        = number
  default     = 1
}

variable "cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "memory" {
  description = "Fargate task memory MiB."
  type        = number
  default     = 1024
}

variable "image_tag" {
  description = "Image tag used by the ECS task definition."
  type        = string
  default     = "latest"
}

variable "container_image" {
  description = "Optional full image URI. Defaults to this module's ECR repo URL plus image_tag."
  type        = string
  default     = ""
}

variable "collector_config_path" {
  description = "Collector config path inside the container."
  type        = string
  default     = "/app/examples/aws-daemon.yaml"
}

variable "health_port" {
  description = "Collector daemon health port."
  type        = number
  default     = 8686
}

variable "metrics_port" {
  description = "Collector daemon metrics port."
  type        = number
  default     = 8687
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "core_api_url_secret_arn" {
  description = "Secrets Manager ARN containing INCIDENTOPS_API_URL."
  type        = string
}

variable "incidentops_token_secret_arn" {
  description = "Secrets Manager ARN containing INCIDENTOPS_TOKEN."
  type        = string
}

variable "project_id_secret_arn" {
  description = "Secrets Manager ARN containing PROJECT_ID."
  type        = string
}

variable "source_name_secret_arn" {
  description = "Optional Secrets Manager ARN containing SOURCE_NAME."
  type        = string
  default     = null
}

variable "source_type_secret_arn" {
  description = "Optional Secrets Manager ARN containing SOURCE_TYPE."
  type        = string
  default     = null
}

variable "collector_environment_secret_arn" {
  description = "Optional Secrets Manager ARN containing COLLECTOR_ENVIRONMENT."
  type        = string
  default     = null
}

variable "collector_config_secret_arn" {
  description = "Optional Secrets Manager ARN containing COLLECTOR_CONFIG path."
  type        = string
  default     = null
}

variable "enable_efs_state" {
  description = "Create and mount EFS for persistent SQLite state/retry queue."
  type        = bool
  default     = true
}

variable "efs_file_system_id" {
  description = "Optional existing EFS file system ID for Collector state."
  type        = string
  default     = null
}
