# Terraform outputs for Algo Trading System infrastructure

# =============================================================================
# VPC Outputs
# =============================================================================
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of public subnets"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.vpc.private_subnet_ids
}

# =============================================================================
# ECS Outputs
# =============================================================================
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.cluster_name
}

output "ecs_cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = module.ecs.cluster_arn
}

output "trading_service_name" {
  description = "Name of the trading ECS service"
  value       = module.ecs.trading_service_name
}

output "dashboard_url" {
  description = "URL of the dashboard load balancer"
  value       = module.ecs.dashboard_url
}

output "ecr_repository_urls" {
  description = "URLs of ECR repositories"
  value       = module.ecs.ecr_repository_urls
}

# =============================================================================
# RDS Outputs
# =============================================================================
output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "rds_port" {
  description = "RDS instance port"
  value       = module.rds.port
}

output "rds_database_name" {
  description = "Name of the database"
  value       = module.rds.database_name
}

# =============================================================================
# S3 Outputs
# =============================================================================
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

# =============================================================================
# Secrets Manager Outputs
# =============================================================================
output "secrets_arn" {
  description = "ARN of the secrets manager secret"
  value       = aws_secretsmanager_secret.api_credentials.arn
}

# =============================================================================
# Monitoring Outputs
# =============================================================================
output "cloudwatch_log_group" {
  description = "Name of the CloudWatch log group"
  value       = aws_cloudwatch_log_group.app_logs.name
}

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alerts"
  value       = aws_sns_topic.alerts.arn
}

# =============================================================================
# Deployment Information
# =============================================================================
output "deployment_info" {
  description = "Deployment information summary"
  value = {
    environment    = var.environment
    region         = var.aws_region
    project_name   = var.project_name
    dashboard_url  = module.ecs.dashboard_url
    cluster_name   = module.ecs.cluster_name
  }
}
