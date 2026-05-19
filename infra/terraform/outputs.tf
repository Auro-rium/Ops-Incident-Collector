output "ecr_repository_url" {
  description = "Collector ECR repository URL."
  value       = aws_ecr_repository.collector.repository_url
}

output "ecs_service_name" {
  description = "Collector ECS service name."
  value       = aws_ecs_service.collector.name
}

output "ecs_task_definition_arn" {
  description = "Collector ECS task definition ARN."
  value       = aws_ecs_task_definition.collector.arn
}

output "cloudwatch_log_group_name" {
  description = "Collector CloudWatch log group."
  value       = aws_cloudwatch_log_group.collector.name
}

output "collector_security_group_ids" {
  description = "Security groups attached to the Collector service."
  value       = local.collector_security_group_ids
}

output "efs_file_system_id" {
  description = "EFS file system used for Collector state, when enabled."
  value       = local.efs_id
}
