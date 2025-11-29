# Terraform main configuration for Algo Trading System
# AWS Infrastructure for production deployment

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration for state management
  # Uncomment and configure for production use
  # backend "s3" {
  #   bucket         = "algo-trading-terraform-state"
  #   key            = "terraform.tfstate"
  #   region         = "ap-south-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
}

# AWS Provider Configuration
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "algo-trading-system"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Current AWS caller identity
data "aws_caller_identity" "current" {}

# Current AWS region
data "aws_region" "current" {}

# =============================================================================
# VPC Module
# =============================================================================
module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  project_name        = var.project_name
  vpc_cidr            = var.vpc_cidr
  availability_zones  = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
}

# =============================================================================
# ECS Module - Container Orchestration
# =============================================================================
module "ecs" {
  source = "./modules/ecs"

  environment               = var.environment
  project_name              = var.project_name
  vpc_id                    = module.vpc.vpc_id
  private_subnet_ids        = module.vpc.private_subnet_ids
  public_subnet_ids         = module.vpc.public_subnet_ids
  
  # Container configurations
  trading_image             = var.trading_image
  dashboard_image           = var.dashboard_image
  data_service_image        = var.data_service_image
  
  # Resource configurations
  trading_cpu               = var.trading_cpu
  trading_memory            = var.trading_memory
  dashboard_cpu             = var.dashboard_cpu
  dashboard_memory          = var.dashboard_memory
  data_service_cpu          = var.data_service_cpu
  data_service_memory       = var.data_service_memory
  
  # Auto-scaling
  trading_desired_count     = var.trading_desired_count
  trading_min_count         = var.trading_min_count
  trading_max_count         = var.trading_max_count
  
  # Secrets
  secrets_arn               = aws_secretsmanager_secret.api_credentials.arn
  
  # Dependencies
  s3_bucket_arn             = module.s3.bucket_arn
  cloudwatch_log_group      = aws_cloudwatch_log_group.app_logs.name
}

# =============================================================================
# RDS Module - Database
# =============================================================================
module "rds" {
  source = "./modules/rds"

  environment          = var.environment
  project_name         = var.project_name
  vpc_id               = module.vpc.vpc_id
  private_subnet_ids   = module.vpc.private_subnet_ids
  
  # Database configurations
  db_instance_class    = var.db_instance_class
  db_allocated_storage = var.db_allocated_storage
  db_name              = var.db_name
  db_username          = var.db_username
  
  # Security
  allowed_security_groups = [module.ecs.ecs_security_group_id]
}

# =============================================================================
# S3 Module - Object Storage
# =============================================================================
module "s3" {
  source = "./modules/s3"

  environment  = var.environment
  project_name = var.project_name
  
  # Bucket configurations
  enable_versioning        = var.s3_enable_versioning
  lifecycle_glacier_days   = var.s3_lifecycle_glacier_days
  lifecycle_expiration_days = var.s3_lifecycle_expiration_days
}

# =============================================================================
# Secrets Manager - API Credentials
# =============================================================================
resource "aws_secretsmanager_secret" "api_credentials" {
  name                    = "${var.project_name}-${var.environment}-api-credentials"
  description             = "API credentials for Angel One broker integration"
  recovery_window_in_days = var.environment == "prod" ? 30 : 0

  tags = {
    Name = "${var.project_name}-api-credentials"
  }
}

resource "aws_secretsmanager_secret_version" "api_credentials" {
  secret_id = aws_secretsmanager_secret.api_credentials.id
  secret_string = jsonencode({
    ANGEL_ONE_API_KEY    = var.angel_one_api_key
    ANGEL_ONE_CLIENT_ID  = var.angel_one_client_id
    # Placeholder - actual secrets should be managed separately
    # ANGEL_ONE_PASSWORD   = ""
    # ANGEL_ONE_TOTP_SECRET = ""
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# =============================================================================
# CloudWatch - Logging and Monitoring
# =============================================================================
resource "aws_cloudwatch_log_group" "app_logs" {
  name              = "/aws/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-logs"
  }
}

# =============================================================================
# SNS - Alerting
# =============================================================================
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-${var.environment}-alerts"

  tags = {
    Name = "${var.project_name}-alerts"
  }
}

resource "aws_sns_topic_subscription" "email_alerts" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# =============================================================================
# CloudWatch Alarms
# =============================================================================
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "High CPU utilization on ECS cluster"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = module.ecs.cluster_name
  }

  tags = {
    Name = "${var.project_name}-high-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "${var.project_name}-${var.environment}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "High memory utilization on ECS cluster"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = module.ecs.cluster_name
  }

  tags = {
    Name = "${var.project_name}-high-memory-alarm"
  }
}
