# Staging environment configuration
# Usage: terraform plan -var-file=environments/staging.tfvars

environment = "staging"
project_name = "algo-trading"
aws_region = "ap-south-1"

# VPC Configuration
vpc_cidr = "10.1.0.0/16"
public_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24"]
private_subnet_cidrs = ["10.1.10.0/24", "10.1.11.0/24"]

# ECS Configuration - Moderate resources for staging
trading_cpu = 512
trading_memory = 1024
dashboard_cpu = 256
dashboard_memory = 512
data_service_cpu = 256
data_service_memory = 512

trading_desired_count = 1
trading_min_count = 1
trading_max_count = 2

# RDS Configuration
db_instance_class = "db.t3.small"
db_allocated_storage = 50
db_name = "algotrading_staging"
db_username = "admin"

# S3 Configuration
s3_enable_versioning = true
s3_lifecycle_glacier_days = 60
s3_lifecycle_expiration_days = 180

# Monitoring
log_retention_days = 14
alert_email = ""
