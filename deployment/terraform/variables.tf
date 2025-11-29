# Terraform variables for Algo Trading System infrastructure

# =============================================================================
# General Configuration
# =============================================================================
variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "algo-trading"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "ap-south-1"
}

# =============================================================================
# VPC Configuration
# =============================================================================
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

# =============================================================================
# ECS Configuration
# =============================================================================
variable "trading_image" {
  description = "Docker image for trading engine"
  type        = string
  default     = ""
}

variable "dashboard_image" {
  description = "Docker image for dashboard"
  type        = string
  default     = ""
}

variable "data_service_image" {
  description = "Docker image for data service"
  type        = string
  default     = ""
}

variable "trading_cpu" {
  description = "CPU units for trading task (1 vCPU = 1024)"
  type        = number
  default     = 512
}

variable "trading_memory" {
  description = "Memory for trading task (in MB)"
  type        = number
  default     = 1024
}

variable "dashboard_cpu" {
  description = "CPU units for dashboard task"
  type        = number
  default     = 256
}

variable "dashboard_memory" {
  description = "Memory for dashboard task (in MB)"
  type        = number
  default     = 512
}

variable "data_service_cpu" {
  description = "CPU units for data service task"
  type        = number
  default     = 256
}

variable "data_service_memory" {
  description = "Memory for data service task (in MB)"
  type        = number
  default     = 512
}

variable "trading_desired_count" {
  description = "Desired number of trading tasks"
  type        = number
  default     = 1
}

variable "trading_min_count" {
  description = "Minimum number of trading tasks for auto-scaling"
  type        = number
  default     = 1
}

variable "trading_max_count" {
  description = "Maximum number of trading tasks for auto-scaling"
  type        = number
  default     = 3
}

# =============================================================================
# RDS Configuration
# =============================================================================
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS (in GB)"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "algotrading"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "admin"
}

# =============================================================================
# S3 Configuration
# =============================================================================
variable "s3_enable_versioning" {
  description = "Enable versioning on S3 bucket"
  type        = bool
  default     = true
}

variable "s3_lifecycle_glacier_days" {
  description = "Days before transitioning to Glacier"
  type        = number
  default     = 90
}

variable "s3_lifecycle_expiration_days" {
  description = "Days before object expiration"
  type        = number
  default     = 365
}

# =============================================================================
# Monitoring Configuration
# =============================================================================
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "alert_email" {
  description = "Email address for alerts"
  type        = string
  default     = ""
}

# =============================================================================
# Secrets - API Credentials
# =============================================================================
variable "angel_one_api_key" {
  description = "Angel One API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "angel_one_client_id" {
  description = "Angel One client ID"
  type        = string
  default     = ""
  sensitive   = true
}
