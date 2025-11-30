# Algo Trading System - Deployment Guide

This document provides comprehensive instructions for deploying the Algo Trading System to AWS.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Environment Setup](#environment-setup)
4. [Deployment Process](#deployment-process)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **AWS CLI** v2.0+ configured with appropriate credentials
- **Terraform** v1.0+
- **Docker** v20.0+
- **Python** v3.12+ (for local development)

### AWS Permissions

The deployment user/role needs the following AWS permissions:

- ECS (Full Access)
- ECR (Full Access)
- RDS (Full Access)
- S3 (Full Access)
- VPC (Full Access)
- CloudWatch (Full Access)
- Secrets Manager (Full Access)
- IAM (Limited - for creating service roles)
- SNS (Full Access)
- ELB (Full Access)

### Environment Variables

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="ap-south-1"
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                           AWS Cloud                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                         VPC                              │    │
│  │  ┌────────────────┐         ┌────────────────────────┐  │    │
│  │  │ Public Subnet  │         │    Private Subnet       │  │    │
│  │  │  ┌──────────┐  │         │  ┌────────────────┐    │  │    │
│  │  │  │   ALB    │──┼─────────┼──│  ECS Cluster   │    │  │    │
│  │  │  └──────────┘  │         │  │  ┌──────────┐  │    │  │    │
│  │  │  ┌──────────┐  │         │  │  │ Trading  │  │    │  │    │
│  │  │  │   NAT    │  │         │  │  │ Service  │  │    │  │    │
│  │  │  │ Gateway  │  │         │  │  └──────────┘  │    │  │    │
│  │  │  └──────────┘  │         │  │  ┌──────────┐  │    │  │    │
│  │  └────────────────┘         │  │  │Dashboard │  │    │  │    │
│  │                             │  │  │ Service  │  │    │  │    │
│  │                             │  │  └──────────┘  │    │  │    │
│  │                             │  │  ┌──────────┐  │    │  │    │
│  │                             │  │  │  Data    │  │    │  │    │
│  │                             │  │  │ Service  │  │    │  │    │
│  │                             │  │  └──────────┘  │    │  │    │
│  │                             │  └────────────────┘    │  │    │
│  │                             │  ┌────────────────┐    │  │    │
│  │                             │  │      RDS       │    │  │    │
│  │                             │  │   PostgreSQL   │    │  │    │
│  │                             │  └────────────────┘    │  │    │
│  │                             └────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │    S3    │  │   ECR    │  │ Secrets  │  │  CloudWatch  │    │
│  │  Bucket  │  │          │  │ Manager  │  │              │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/algo-trading-system.git
cd algo-trading-system
```

### 2. Configure Terraform Backend (Optional)

For production deployments, configure remote state:

```hcl
# deployment/terraform/main.tf
backend "s3" {
  bucket         = "algo-trading-terraform-state"
  key            = "terraform.tfstate"
  region         = "ap-south-1"
  encrypt        = true
  dynamodb_table = "terraform-state-lock"
}
```

### 3. Set Up Secrets

Store API credentials in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name algo-trading-prod-api-credentials \
  --secret-string '{
    "ANGEL_ONE_API_KEY": "your-api-key",
    "ANGEL_ONE_CLIENT_ID": "your-client-id",
    "ANGEL_ONE_PASSWORD": "your-password",
    "ANGEL_ONE_TOTP_SECRET": "your-totp-secret"
  }'
```

## Deployment Process

### Quick Deploy

```bash
# Development
./deployment/scripts/deploy.sh dev

# Staging
./deployment/scripts/deploy.sh staging

# Production
./deployment/scripts/deploy.sh prod
```

### Step-by-Step Deployment

#### 1. Initialize Terraform

```bash
cd deployment/terraform
terraform init
```

#### 2. Plan Infrastructure

```bash
terraform plan -var-file=environments/dev.tfvars -out=tfplan
```

#### 3. Apply Infrastructure

```bash
terraform apply tfplan
```

#### 4. Build and Push Docker Images

```bash
# Login to ECR
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com

# Build images
docker build -f deployment/docker/Dockerfile.trading -t algo-trading-dev-trading .
docker build -f deployment/docker/Dockerfile.dashboard -t algo-trading-dev-dashboard .
docker build -f deployment/docker/Dockerfile.data -t algo-trading-dev-data-service .

# Tag and push
docker tag algo-trading-dev-trading <ecr-url>/algo-trading-dev-trading:latest
docker push <ecr-url>/algo-trading-dev-trading:latest
```

#### 5. Update ECS Services

```bash
aws ecs update-service \
  --cluster algo-trading-dev-cluster \
  --service algo-trading-dev-trading \
  --force-new-deployment
```

### Deployment Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without applying |
| `--skip-build` | Skip Docker image building |
| `--skip-infra` | Skip Terraform deployment |
| `--force` | Continue even if health checks fail |

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ENVIRONMENT` | dev/staging/prod | Yes |
| `ANGEL_ONE_API_KEY` | Angel One API key | Yes |
| `ANGEL_ONE_CLIENT_ID` | Angel One client ID | Yes |
| `PAPER_TRADING` | Enable paper trading | No |
| `MAX_DAILY_TRADES` | Maximum trades per day | No |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR | No |

### Resource Sizing

| Environment | Trading CPU | Trading Memory | Dashboard CPU | Dashboard Memory |
|-------------|-------------|----------------|---------------|------------------|
| dev | 256 | 512 MB | 256 | 512 MB |
| staging | 512 | 1024 MB | 256 | 512 MB |
| prod | 1024 | 2048 MB | 512 | 1024 MB |

## Monitoring

### CloudWatch Dashboards

Access the monitoring dashboard:

1. Go to AWS CloudWatch Console
2. Navigate to Dashboards
3. Select "AlgoTradingSystem"

### Key Metrics

- **ECS CPU/Memory Utilization**: Container resource usage
- **ALB Request Count**: HTTP traffic volume
- **ALB Response Time**: Application latency
- **RDS Connections**: Database connection pool
- **Error Count**: Application errors

### Alerts

Alerts are sent to the configured SNS topic. Configure email subscriptions:

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:ap-south-1:<account>:algo-trading-prod-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com
```

## Troubleshooting

### Common Issues

#### 1. ECS Service Not Starting

```bash
# Check service events
aws ecs describe-services \
  --cluster algo-trading-dev-cluster \
  --services algo-trading-dev-trading

# Check task logs
aws logs tail /aws/ecs/algo-trading-dev --follow
```

#### 2. Database Connection Issues

```bash
# Verify security group rules
aws ec2 describe-security-groups \
  --group-ids <rds-security-group-id>

# Test connectivity from ECS task
aws ecs execute-command \
  --cluster algo-trading-dev-cluster \
  --task <task-id> \
  --container trading \
  --interactive \
  --command "/bin/bash"
```

#### 3. Image Pull Failures

```bash
# Verify ECR repository exists
aws ecr describe-repositories

# Check image exists
aws ecr list-images --repository-name algo-trading-dev-trading
```

### Rollback Procedure

```bash
# Quick rollback to previous version
./deployment/scripts/rollback.sh dev

# Rollback to specific revision
./deployment/scripts/rollback.sh dev --to-revision 5
```

### Health Checks

```bash
# Run health checks
./deployment/scripts/health_check.sh dev --verbose
```

## Security Considerations

1. **Never commit secrets** to version control
2. **Use IAM roles** instead of access keys where possible
3. **Enable VPC flow logs** for network monitoring
4. **Encrypt data at rest** (S3, RDS, EBS)
5. **Use HTTPS** for all external traffic
6. **Regularly rotate** API credentials and passwords

## Cost Optimization

- Use **Fargate Spot** for non-critical workloads
- Enable **RDS auto-scaling** for storage
- Configure **S3 lifecycle policies** for data archival
- Use **CloudWatch log retention** policies
- Consider **Reserved Capacity** for production workloads
