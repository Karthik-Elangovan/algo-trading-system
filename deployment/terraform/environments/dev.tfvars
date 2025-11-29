# Development environment configuration
# Usage: terraform plan -var-file=environments/dev.tfvars

environment = "dev"
project_name = "algo-trading"
aws_region = "ap-south-1"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"
public_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
private_subnet_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]

# ECS Configuration - Minimal resources for dev
trading_cpu = 256
trading_memory = 512
dashboard_cpu = 256
dashboard_memory = 512
data_service_cpu = 256
data_service_memory = 512

trading_desired_count = 1
trading_min_count = 1
trading_max_count = 2

# RDS Configuration - Minimal for dev
db_instance_class = "db.t3.micro"
db_allocated_storage = 20
db_name = "algotrading_dev"
db_username = "admin"

# S3 Configuration
s3_enable_versioning = false
s3_lifecycle_glacier_days = 30
s3_lifecycle_expiration_days = 90

# Monitoring
log_retention_days = 7
alert_email = ""
