locals {
  image_uri = var.container_image != "" ? var.container_image : "${aws_ecr_repository.collector.repository_url}:${var.image_tag}"

  optional_secrets = [
    {
      name      = "SOURCE_NAME"
      valueFrom = var.source_name_secret_arn
    },
    {
      name      = "SOURCE_TYPE"
      valueFrom = var.source_type_secret_arn
    },
    {
      name      = "COLLECTOR_ENVIRONMENT"
      valueFrom = var.collector_environment_secret_arn
    },
    {
      name      = "COLLECTOR_CONFIG"
      valueFrom = var.collector_config_secret_arn
    },
  ]

  container_secrets = concat(
    [
      {
        name      = "INCIDENTOPS_API_URL"
        valueFrom = var.core_api_url_secret_arn
      },
      {
        name      = "INCIDENTOPS_TOKEN"
        valueFrom = var.incidentops_token_secret_arn
      },
      {
        name      = "PROJECT_ID"
        valueFrom = var.project_id_secret_arn
      },
    ],
    [for item in local.optional_secrets : item if item.valueFrom != null]
  )

  secret_arns = [
    for arn in [
      var.core_api_url_secret_arn,
      var.incidentops_token_secret_arn,
      var.project_id_secret_arn,
      var.source_name_secret_arn,
      var.source_type_secret_arn,
      var.collector_environment_secret_arn,
      var.collector_config_secret_arn,
    ] : arn if arn != null && arn != ""
  ]

  collector_security_group_ids = concat(
    var.security_group_ids,
    var.create_security_group ? [aws_security_group.collector[0].id] : []
  )

  efs_id = (
    var.enable_efs_state
    ? (var.efs_file_system_id != null ? var.efs_file_system_id : aws_efs_file_system.collector_state[0].id)
    : null
  )
}

resource "aws_ecr_repository" "collector" {
  name                 = var.name_prefix
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "collector" {
  repository = aws_ecr_repository.collector.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 30 Collector images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "collector" {
  name              = "/ecs/${var.name_prefix}"
  retention_in_days = var.log_retention_days
}

resource "aws_security_group" "collector" {
  count       = var.create_security_group ? 1 : 0
  name        = "${var.name_prefix}-sg"
  description = "OpsIncident Collector ECS task security group"
  vpc_id      = var.vpc_id

  egress {
    description = "Collector outbound access to Core API, Secrets Manager, ECR, logs, and EFS"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "core_from_collector" {
  count                        = var.create_security_group && var.core_security_group_id != null ? 1 : 0
  security_group_id            = var.core_security_group_id
  referenced_security_group_id = aws_security_group.collector[0].id
  ip_protocol                  = "tcp"
  from_port                    = var.core_api_port
  to_port                      = var.core_api_port
  description                  = "Allow OpsIncident Collector to call IncidentOps Core API"
}

resource "aws_security_group" "efs" {
  count       = var.enable_efs_state && var.efs_file_system_id == null ? 1 : 0
  name        = "${var.name_prefix}-efs-sg"
  description = "OpsIncident Collector EFS state security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "NFS from Collector tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = local.collector_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_efs_file_system" "collector_state" {
  count          = var.enable_efs_state && var.efs_file_system_id == null ? 1 : 0
  creation_token = "${var.name_prefix}-state"
  encrypted      = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }
}

resource "aws_efs_mount_target" "collector_state" {
  for_each = var.enable_efs_state && var.efs_file_system_id == null ? toset(var.subnet_ids) : toset([])

  file_system_id  = aws_efs_file_system.collector_state[0].id
  subnet_id        = each.value
  security_groups  = [aws_security_group.efs[0].id]
}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.name_prefix}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = local.secret_arns
  }
}

resource "aws_iam_role_policy" "execution_secrets" {
  name   = "${var.name_prefix}-secrets"
  role   = aws_iam_role.execution.id
  policy = data.aws_iam_policy_document.execution_secrets.json
}

resource "aws_iam_role" "task" {
  name               = "${var.name_prefix}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

resource "aws_ecs_task_definition" "collector" {
  family                   = var.name_prefix
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  dynamic "volume" {
    for_each = var.enable_efs_state ? [1] : []

    content {
      name = "collector-state"

      efs_volume_configuration {
        file_system_id     = local.efs_id
        transit_encryption = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([
    {
      name      = "collector"
      image     = local.image_uri
      essential = true
      command   = ["daemon", "run", "--config", var.collector_config_path]

      environment = [
        {
          name  = "INCIDENTOPS_EDGE_STATE"
          value = "/var/lib/opsincident-collector/state.sqlite"
        },
        {
          name  = "PYTHONUNBUFFERED"
          value = "1"
        }
      ]

      secrets = local.container_secrets

      portMappings = [
        {
          containerPort = var.health_port
          hostPort      = var.health_port
          protocol      = "tcp"
        },
        {
          containerPort = var.metrics_port
          hostPort      = var.metrics_port
          protocol      = "tcp"
        }
      ]

      mountPoints = var.enable_efs_state ? [
        {
          sourceVolume  = "collector-state"
          containerPath = "/var/lib/opsincident-collector"
          readOnly      = false
        }
      ] : []

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.collector.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "collector"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "opsincident-collector daemon health --host 127.0.0.1 --port ${var.health_port} || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }
    }
  ])
}

resource "aws_ecs_service" "collector" {
  name            = "incidentops-collector"
  cluster         = var.ecs_cluster_name
  task_definition = aws_ecs_task_definition.collector.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = local.collector_security_group_ids
    assign_public_ip = var.assign_public_ip
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  depends_on = [
    aws_cloudwatch_log_group.collector,
    aws_iam_role_policy_attachment.execution,
  ]
}
