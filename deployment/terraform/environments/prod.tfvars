# Production environment configuration
# Usage: terraform plan -var-file=environments/prod.tfvars

environment = "prod"
project_name = "algo-trading"
aws_region = "ap-south-1"

# VPC Configuration
vpc_cidr = "10.2.0.0/16"
public_subnet_cidrs = ["10.2.1.0/24", "10.2.2.0/24"]
private_subnet_cidrs = ["10.2.10.0/24", "10.2.11.0/24"]

# ECS Configuration - Production resources
trading_cpu = 1024
trading_memory = 2048
dashboard_cpu = 512
dashboard_memory = 1024
data_service_cpu = 512
data_service_memory = 1024

trading_desired_count = 2
trading_min_count = 2
trading_max_count = 5

# RDS Configuration - Production grade
db_instance_class = "db.t3.medium"
db_allocated_storage = 100
db_name = "algotrading_prod"
db_username = "admin"

# S3 Configuration
s3_enable_versioning = true
s3_lifecycle_glacier_days = 90
s3_lifecycle_expiration_days = 365

# Monitoring
log_retention_days = 90
alert_email = ""  # Set this to your alert email
