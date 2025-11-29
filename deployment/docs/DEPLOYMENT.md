# Deployment Guide

This document provides instructions for deploying the Algo Trading System to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Local Development](#local-development)
4. [AWS Deployment](#aws-deployment)
5. [Configuration](#configuration)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Tools

- **Docker**: v20.10+
- **Docker Compose**: v2.0+
- **Terraform**: v1.0+
- **AWS CLI**: v2.0+
- **Python**: v3.12+

### AWS Resources

Ensure you have an AWS account with appropriate permissions to create:
- VPC and networking resources
- ECS clusters and services
- RDS PostgreSQL instances
- S3 buckets
- Secrets Manager secrets
- CloudWatch resources
- IAM roles and policies

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/algo-trading-system.git
cd algo-trading-system
```

### 2. Set Up Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit with your values
vim .env
```

Required environment variables:
- `ANGEL_ONE_API_KEY`: Your Angel One API key
- `ANGEL_ONE_CLIENT_ID`: Your Angel One client ID
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key

### 3. Deploy

```bash
# For local development
docker-compose -f deployment/docker/docker-compose.yml up

# For AWS deployment
./deployment/scripts/deploy.sh <environment>
```

## Local Development

### Using Docker Compose

1. **Build and start services**:
   ```bash
   cd deployment/docker
   docker-compose up --build
   ```

2. **Access services**:
   - Dashboard: http://localhost:8501
   - Trading Engine: internal service
   - Data Service: internal service

3. **View logs**:
   ```bash
   docker-compose logs -f trading
   docker-compose logs -f dashboard
   ```

4. **Stop services**:
   ```bash
   docker-compose down
   ```

### Building Individual Images

```bash
# Trading Engine
docker build -f deployment/docker/Dockerfile.trading -t algo-trading .

# Dashboard
docker build -f deployment/docker/Dockerfile.dashboard -t algo-dashboard .

# Data Service
docker build -f deployment/docker/Dockerfile.data -t algo-data .
```

## AWS Deployment

### Infrastructure Setup

1. **Initialize Terraform**:
   ```bash
   cd deployment/terraform
   terraform init
   ```

2. **Plan deployment**:
   ```bash
   # Development
   terraform plan -var-file=environments/dev.tfvars
   
   # Production
   terraform plan -var-file=environments/prod.tfvars
   ```

3. **Apply infrastructure**:
   ```bash
   terraform apply -var-file=environments/<env>.tfvars
   ```

### Automated Deployment

Use the deployment script for a complete deployment:

```bash
# Development deployment
./deployment/scripts/deploy.sh dev

# Staging deployment
./deployment/scripts/deploy.sh staging

# Production deployment (requires confirmation)
./deployment/scripts/deploy.sh prod
```

### Deployment Options

```bash
./deployment/scripts/deploy.sh <env> [options]

Options:
  --dry-run      Preview changes without deploying
  --skip-build   Skip Docker image building
  --skip-infra   Skip Terraform infrastructure
  --force        Continue even if health checks fail
```

### Manual Steps

1. **Push Docker images to ECR**:
   ```bash
   aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-south-1.amazonaws.com
   
   docker tag algo-trading:latest <account>.dkr.ecr.ap-south-1.amazonaws.com/algo-trading-<env>-trading:latest
   docker push <account>.dkr.ecr.ap-south-1.amazonaws.com/algo-trading-<env>-trading:latest
   ```

2. **Update ECS service**:
   ```bash
   aws ecs update-service --cluster algo-trading-<env>-cluster --service algo-trading-<env>-trading --force-new-deployment
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment | `development` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TRADING_ENABLED` | Enable trading | `true` |
| `PAPER_TRADING` | Paper trading mode | `true` |
| `MAX_DAILY_TRADES` | Max trades per day | `50` |
| `ANGEL_ONE_API_KEY` | Broker API key | - |
| `ANGEL_ONE_CLIENT_ID` | Broker client ID | - |

### Secrets Management

Secrets are stored in AWS Secrets Manager:

```bash
# Update a secret
aws secretsmanager put-secret-value \
  --secret-id algo-trading-prod-api-credentials \
  --secret-string '{"ANGEL_ONE_API_KEY":"xxx","ANGEL_ONE_CLIENT_ID":"yyy"}'
```

### Terraform Variables

Key variables in `terraform.tfvars`:

```hcl
environment = "prod"
aws_region = "ap-south-1"

# ECS Configuration
trading_cpu = 1024
trading_memory = 2048
trading_desired_count = 2

# RDS Configuration
db_instance_class = "db.t3.medium"
db_allocated_storage = 100
```

## Monitoring

### CloudWatch Dashboard

Access the dashboard at:
```
https://console.aws.amazon.com/cloudwatch/home?region=ap-south-1#dashboards:name=algo-trading-<env>
```

### Key Metrics

- **CPU Utilization**: Target < 80%
- **Memory Utilization**: Target < 80%
- **Response Time**: Target < 2s
- **Error Rate**: Target < 1%

### Alerts

Alerts are configured for:
- High CPU/Memory utilization
- Service unhealthy
- Database connection issues
- Trading execution failures
- Daily loss limits exceeded

### Viewing Logs

```bash
# Using AWS CLI
aws logs tail /aws/ecs/algo-trading-<env> --follow

# Filter errors
aws logs filter-log-events \
  --log-group-name /aws/ecs/algo-trading-<env> \
  --filter-pattern "ERROR"
```

## Troubleshooting

### Common Issues

#### Service Not Starting

1. Check CloudWatch logs:
   ```bash
   aws logs tail /aws/ecs/algo-trading-<env>/trading --follow
   ```

2. Verify secrets are configured:
   ```bash
   aws secretsmanager get-secret-value --secret-id algo-trading-<env>-api-credentials
   ```

3. Check ECS task status:
   ```bash
   aws ecs describe-tasks --cluster algo-trading-<env>-cluster --tasks <task-id>
   ```

#### Database Connection Issues

1. Verify security groups allow connection
2. Check RDS endpoint is correct
3. Verify credentials in Secrets Manager

#### Deployment Failures

1. Run with `--dry-run` to preview changes
2. Check Terraform state:
   ```bash
   terraform state list
   ```
3. Review CloudWatch logs for errors

### Health Checks

Run health checks manually:

```bash
./deployment/scripts/health_check.sh <env> --verbose
```

### Rollback

To rollback to a previous version:

```bash
# Rollback to previous task revision
./deployment/scripts/rollback.sh <env>

# Rollback to specific revision
./deployment/scripts/rollback.sh <env> --to-revision 5
```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use IAM roles** instead of access keys where possible
3. **Enable encryption** for all data at rest
4. **Restrict network access** using security groups
5. **Enable logging** for audit trails
6. **Rotate credentials** regularly

## Support

For issues or questions:
- Create a GitHub issue
- Contact the DevOps team
- Refer to the [Runbook](RUNBOOK.md) for operational procedures
