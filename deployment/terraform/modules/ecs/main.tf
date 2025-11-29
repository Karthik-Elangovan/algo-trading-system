# ECS Module for Algo Trading System
# Creates ECS cluster, services, and tasks

# =============================================================================
# Variables
# =============================================================================
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs"
  type        = list(string)
}

variable "trading_image" {
  description = "Docker image for trading engine"
  type        = string
}

variable "dashboard_image" {
  description = "Docker image for dashboard"
  type        = string
}

variable "data_service_image" {
  description = "Docker image for data service"
  type        = string
}

variable "trading_cpu" {
  description = "CPU units for trading task"
  type        = number
}

variable "trading_memory" {
  description = "Memory for trading task"
  type        = number
}

variable "dashboard_cpu" {
  description = "CPU units for dashboard task"
  type        = number
}

variable "dashboard_memory" {
  description = "Memory for dashboard task"
  type        = number
}

variable "data_service_cpu" {
  description = "CPU units for data service task"
  type        = number
}

variable "data_service_memory" {
  description = "Memory for data service task"
  type        = number
}

variable "trading_desired_count" {
  description = "Desired number of trading tasks"
  type        = number
}

variable "trading_min_count" {
  description = "Minimum number of trading tasks"
  type        = number
}

variable "trading_max_count" {
  description = "Maximum number of trading tasks"
  type        = number
}

variable "secrets_arn" {
  description = "ARN of secrets manager secret"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of S3 bucket"
  type        = string
}

variable "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  type        = string
}

# =============================================================================
# Local Variables
# =============================================================================
locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# =============================================================================
# ECR Repositories
# =============================================================================
resource "aws_ecr_repository" "trading" {
  name                 = "${local.name_prefix}-trading"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.name_prefix}-trading-ecr"
  }
}

resource "aws_ecr_repository" "dashboard" {
  name                 = "${local.name_prefix}-dashboard"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.name_prefix}-dashboard-ecr"
  }
}

resource "aws_ecr_repository" "data_service" {
  name                 = "${local.name_prefix}-data-service"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${local.name_prefix}-data-service-ecr"
  }
}

# ECR Lifecycle Policy
resource "aws_ecr_lifecycle_policy" "trading" {
  repository = aws_ecr_repository.trading.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# =============================================================================
# ECS Cluster
# =============================================================================
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${local.name_prefix}-cluster"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
}

# =============================================================================
# IAM Roles
# =============================================================================
# ECS Task Execution Role
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task-execution"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "${local.name_prefix}-ecs-secrets-policy"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Effect   = "Allow"
        Resource = var.secrets_arn
      }
    ]
  })
}

# ECS Task Role
resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-ecs-task"
  }
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${local.name_prefix}-ecs-s3-policy"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}

# =============================================================================
# Security Groups
# =============================================================================
resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "Security group for ECS tasks"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-ecs-sg"
  }
}

resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-alb-sg"
  }
}

# Allow ALB to ECS
resource "aws_security_group_rule" "ecs_from_alb" {
  type                     = "ingress"
  from_port                = 8501
  to_port                  = 8501
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs.id
  source_security_group_id = aws_security_group.alb.id
}

# =============================================================================
# Application Load Balancer
# =============================================================================
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = var.environment == "prod" ? true : false

  tags = {
    Name = "${local.name_prefix}-alb"
  }
}

resource "aws_lb_target_group" "dashboard" {
  name        = "${local.name_prefix}-dashboard-tg"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/_stcore/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 3
  }

  tags = {
    Name = "${local.name_prefix}-dashboard-tg"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.dashboard.arn
  }
}

# =============================================================================
# ECS Task Definitions
# =============================================================================
# Trading Engine Task Definition
resource "aws_ecs_task_definition" "trading" {
  family                   = "${local.name_prefix}-trading"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.trading_cpu
  memory                   = var.trading_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "trading"
      image     = var.trading_image != "" ? var.trading_image : "${aws_ecr_repository.trading.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "LOG_LEVEL"
          value = var.environment == "prod" ? "INFO" : "DEBUG"
        }
      ]

      secrets = [
        {
          name      = "ANGEL_ONE_API_KEY"
          valueFrom = "${var.secrets_arn}:ANGEL_ONE_API_KEY::"
        },
        {
          name      = "ANGEL_ONE_CLIENT_ID"
          valueFrom = "${var.secrets_arn}:ANGEL_ONE_CLIENT_ID::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.cloudwatch_log_group
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "trading"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "python -c 'import sys; sys.exit(0)' || exit 1"]
        interval    = 60
        timeout     = 30
        retries     = 3
        startPeriod = 30
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-trading-task"
  }
}

# Dashboard Task Definition
resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${local.name_prefix}-dashboard"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.dashboard_cpu
  memory                   = var.dashboard_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "dashboard"
      image     = var.dashboard_image != "" ? var.dashboard_image : "${aws_ecr_repository.dashboard.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8501
          hostPort      = 8501
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "STREAMLIT_SERVER_PORT"
          value = "8501"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.cloudwatch_log_group
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "dashboard"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-dashboard-task"
  }
}

# Data Service Task Definition
resource "aws_ecs_task_definition" "data_service" {
  family                   = "${local.name_prefix}-data-service"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.data_service_cpu
  memory                   = var.data_service_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "data-service"
      image     = var.data_service_image != "" ? var.data_service_image : "${aws_ecr_repository.data_service.repository_url}:latest"
      essential = true

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "LOG_LEVEL"
          value = var.environment == "prod" ? "INFO" : "DEBUG"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.cloudwatch_log_group
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "data-service"
        }
      }
    }
  ])

  tags = {
    Name = "${local.name_prefix}-data-service-task"
  }
}

# =============================================================================
# ECS Services
# =============================================================================
resource "aws_ecs_service" "trading" {
  name            = "${local.name_prefix}-trading"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.trading.arn
  desired_count   = var.trading_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  tags = {
    Name = "${local.name_prefix}-trading-service"
  }
}

resource "aws_ecs_service" "dashboard" {
  name            = "${local.name_prefix}-dashboard"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dashboard.arn
    container_name   = "dashboard"
    container_port   = 8501
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  tags = {
    Name = "${local.name_prefix}-dashboard-service"
  }
}

resource "aws_ecs_service" "data_service" {
  name            = "${local.name_prefix}-data-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.data_service.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  tags = {
    Name = "${local.name_prefix}-data-service"
  }
}

# =============================================================================
# Auto Scaling
# =============================================================================
resource "aws_appautoscaling_target" "trading" {
  max_capacity       = var.trading_max_count
  min_capacity       = var.trading_min_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.trading.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "trading_cpu" {
  name               = "${local.name_prefix}-trading-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.trading.resource_id
  scalable_dimension = aws_appautoscaling_target.trading.scalable_dimension
  service_namespace  = aws_appautoscaling_target.trading.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# =============================================================================
# Data Sources
# =============================================================================
data "aws_region" "current" {}

# =============================================================================
# Outputs
# =============================================================================
output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.main.arn
}

output "trading_service_name" {
  description = "Name of the trading service"
  value       = aws_ecs_service.trading.name
}

output "dashboard_url" {
  description = "URL of the dashboard"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_repository_urls" {
  description = "URLs of ECR repositories"
  value = {
    trading      = aws_ecr_repository.trading.repository_url
    dashboard    = aws_ecr_repository.dashboard.repository_url
    data_service = aws_ecr_repository.data_service.repository_url
  }
}

output "ecs_security_group_id" {
  description = "ID of ECS security group"
  value       = aws_security_group.ecs.id
}
