# Architecture Documentation

This document describes the architecture of the Algo Trading System deployment.

## Table of Contents

1. [System Overview](#system-overview)
2. [Components](#components)
3. [AWS Infrastructure](#aws-infrastructure)
4. [Data Flow](#data-flow)
5. [Security Architecture](#security-architecture)
6. [Scalability](#scalability)
7. [Disaster Recovery](#disaster-recovery)

---

## System Overview

The Algo Trading System is a containerized application deployed on AWS using ECS Fargate for compute, RDS for persistence, and S3 for object storage.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud (ap-south-1)                          │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                              VPC (10.0.0.0/16)                        │   │
│  │                                                                       │   │
│  │   ┌─────────────────────────┐   ┌─────────────────────────┐          │   │
│  │   │   Public Subnet (AZ-A)  │   │   Public Subnet (AZ-B)  │          │   │
│  │   │   ┌─────────────────┐   │   │                         │          │   │
│  │   │   │  NAT Gateway    │   │   │                         │          │   │
│  │   │   └─────────────────┘   │   │                         │          │   │
│  │   │   ┌─────────────────┐   │   │   ┌─────────────────┐   │          │   │
│  │   │   │      ALB        │───┼───┼───│      ALB        │   │          │   │
│  │   │   └─────────────────┘   │   │   └─────────────────┘   │          │   │
│  │   └─────────────────────────┘   └─────────────────────────┘          │   │
│  │                                                                       │   │
│  │   ┌─────────────────────────┐   ┌─────────────────────────┐          │   │
│  │   │  Private Subnet (AZ-A)  │   │  Private Subnet (AZ-B)  │          │   │
│  │   │                         │   │                         │          │   │
│  │   │  ┌─────────────────┐    │   │  ┌─────────────────┐    │          │   │
│  │   │  │ Trading Engine  │    │   │  │ Trading Engine  │    │          │   │
│  │   │  │   (ECS Task)    │    │   │  │   (ECS Task)    │    │          │   │
│  │   │  └─────────────────┘    │   │  └─────────────────┘    │          │   │
│  │   │                         │   │                         │          │   │
│  │   │  ┌─────────────────┐    │   │  ┌─────────────────┐    │          │   │
│  │   │  │    Dashboard    │    │   │  │  Data Service   │    │          │   │
│  │   │  │   (ECS Task)    │    │   │  │   (ECS Task)    │    │          │   │
│  │   │  └─────────────────┘    │   │  └─────────────────┘    │          │   │
│  │   │                         │   │                         │          │   │
│  │   │  ┌─────────────────┐    │   │  ┌─────────────────┐    │          │   │
│  │   │  │  RDS (Primary)  │────┼───┼──│  RDS (Standby)  │    │          │   │
│  │   │  │   PostgreSQL    │    │   │  │   PostgreSQL    │    │          │   │
│  │   │  └─────────────────┘    │   │  └─────────────────┘    │          │   │
│  │   └─────────────────────────┘   └─────────────────────────┘          │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Supporting Services                                                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │  │
│  │  │     ECR      │  │  CloudWatch  │  │   Secrets    │  │     S3     │  │  │
│  │  │  (Images)    │  │   (Logs)     │  │   Manager    │  │  (Data)    │  │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### Trading Engine

The core component responsible for executing trading strategies.

**Responsibilities:**
- Strategy execution (Premium Selling, etc.)
- Order management
- Position tracking
- Risk management

**Configuration:**
- CPU: 1024 units (1 vCPU)
- Memory: 2048 MB
- Desired count: 2 (production)

**Health Check:**
- Command: Python import check
- Interval: 60s
- Timeout: 30s

### Dashboard (Streamlit)

Web-based interface for monitoring and control.

**Responsibilities:**
- Real-time position monitoring
- Performance metrics visualization
- Trade history
- Emergency controls

**Configuration:**
- CPU: 512 units
- Memory: 1024 MB
- Port: 8501

**Health Check:**
- Endpoint: `/_stcore/health`
- Interval: 30s

### Data Service

Handles market data processing and storage.

**Responsibilities:**
- Market data fetching
- Data caching
- Historical data management
- S3 integration

**Configuration:**
- CPU: 512 units
- Memory: 1024 MB

---

## AWS Infrastructure

### VPC Architecture

| Component | CIDR | Purpose |
|-----------|------|---------|
| VPC | 10.x.0.0/16 | Main network |
| Public Subnet A | 10.x.1.0/24 | ALB, NAT Gateway |
| Public Subnet B | 10.x.2.0/24 | ALB (redundancy) |
| Private Subnet A | 10.x.10.0/24 | ECS Tasks, RDS |
| Private Subnet B | 10.x.11.0/24 | ECS Tasks, RDS Standby |

### ECS Cluster

**Capacity Provider:** Fargate (serverless)

**Services:**
| Service | Task Definition | Desired Count | Min | Max |
|---------|-----------------|---------------|-----|-----|
| Trading | trading:latest | 2 | 2 | 5 |
| Dashboard | dashboard:latest | 1 | 1 | 2 |
| Data Service | data-service:latest | 1 | 1 | 2 |

### RDS PostgreSQL

**Instance Class:** db.t3.medium (production)

**Configuration:**
- Engine: PostgreSQL 15
- Storage: 100 GB gp3
- Multi-AZ: Yes (production)
- Encryption: AES-256
- Backup Retention: 30 days

### S3 Bucket

**Structure:**
```
algo-trading-<env>-data-<account-id>/
├── backtest-results/
│   └── YYYY/MM/DD/
├── reports/
│   └── daily/
│   └── monthly/
├── market-data/
│   └── historical/
└── logs/
    └── YYYY/MM/DD/
```

**Lifecycle Rules:**
- Backtest results → Glacier after 90 days
- Logs → Delete after 30 days

### Security Groups

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   ALB SG        │      │   ECS SG        │      │   RDS SG        │
│                 │      │                 │      │                 │
│ Ingress:        │      │ Ingress:        │      │ Ingress:        │
│ - 80 (0.0.0.0)  │──────│ - 8501 (ALB SG) │──────│ - 5432 (ECS SG) │
│ - 443 (0.0.0.0) │      │                 │      │                 │
│                 │      │ Egress:         │      │ Egress:         │
│ Egress:         │      │ - All (0.0.0.0) │      │ - All (0.0.0.0) │
│ - All (0.0.0.0) │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

---

## Data Flow

### Trading Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Market Data │───▶│ Data Service │───▶│   Trading    │───▶│   Broker     │
│  (Angel One) │    │              │    │   Engine     │    │  (Angel One) │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                            │                   │
                            │                   │
                            ▼                   ▼
                    ┌──────────────┐    ┌──────────────┐
                    │     S3       │    │     RDS      │
                    │ (Historical) │    │  (Trades)    │
                    └──────────────┘    └──────────────┘
```

### Request Flow

```
User ──▶ Route 53 ──▶ CloudFront ──▶ ALB ──▶ ECS (Dashboard) ──▶ RDS
                                      │
                                      └──▶ ECS (Trading Engine)
```

---

## Security Architecture

### Defense in Depth

1. **Network Level**
   - VPC isolation
   - Private subnets for workloads
   - Security groups (least privilege)
   - VPC Flow Logs

2. **Application Level**
   - Non-root containers
   - Read-only file systems where possible
   - No hardcoded credentials

3. **Data Level**
   - Encryption at rest (RDS, S3)
   - Encryption in transit (TLS)
   - Secrets in AWS Secrets Manager

4. **Access Control**
   - IAM roles (no access keys)
   - ECS task roles
   - Principle of least privilege

### Secrets Management

```
┌──────────────────────────────────────────────────────────────┐
│                    Secrets Manager                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  algo-trading-<env>-api-credentials                     │ │
│  │  {                                                      │ │
│  │    "ANGEL_ONE_API_KEY": "***",                          │ │
│  │    "ANGEL_ONE_CLIENT_ID": "***",                        │ │
│  │    "ANGEL_ONE_PASSWORD": "***",                         │ │
│  │    "ANGEL_ONE_TOTP_SECRET": "***"                       │ │
│  │  }                                                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  algo-trading-<env>-db-password                         │ │
│  │  {                                                      │ │
│  │    "username": "admin",                                 │ │
│  │    "password": "***",                                   │ │
│  │    "host": "...",                                       │ │
│  │    "port": 5432                                         │ │
│  │  }                                                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Scalability

### Horizontal Scaling

**ECS Auto Scaling:**
- Target tracking on CPU utilization (70%)
- Scale out: +1 task when CPU > 70% for 60s
- Scale in: -1 task when CPU < 50% for 300s
- Cooldown: 60s (out), 300s (in)

### Vertical Scaling

Increase task resources via Terraform:
```hcl
# In environments/prod.tfvars
trading_cpu = 2048    # 2 vCPU
trading_memory = 4096 # 4 GB
```

### Database Scaling

- **Vertical:** Change instance class
- **Read Replicas:** Add for read-heavy workloads
- **Connection Pooling:** Use PgBouncer if needed

---

## Disaster Recovery

### Recovery Objectives

| Metric | Target |
|--------|--------|
| RTO (Recovery Time Objective) | < 1 hour |
| RPO (Recovery Point Objective) | < 5 minutes |

### Backup Strategy

| Component | Method | Frequency | Retention |
|-----------|--------|-----------|-----------|
| RDS | Automated snapshots | Daily | 30 days |
| RDS | Transaction logs | Continuous | 7 days |
| S3 | Versioning | Automatic | 90 days |
| ECS | Task definitions | Immutable | Indefinite |

### Multi-AZ Deployment

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│      Availability Zone A    │     │      Availability Zone B    │
│                             │     │                             │
│  ┌───────────────────────┐  │     │  ┌───────────────────────┐  │
│  │   ECS Tasks (Active)  │  │     │  │   ECS Tasks (Active)  │  │
│  └───────────────────────┘  │     │  └───────────────────────┘  │
│                             │     │                             │
│  ┌───────────────────────┐  │     │  ┌───────────────────────┐  │
│  │    RDS (Primary)      │──┼─────┼──│    RDS (Standby)      │  │
│  └───────────────────────┘  │     │  └───────────────────────┘  │
│                             │     │                             │
└─────────────────────────────┘     └─────────────────────────────┘
```

### Failover Procedures

**RDS Failover:**
- Automatic for Multi-AZ deployments
- Manual: `aws rds failover-db-cluster`
- DNS update: ~30-60 seconds

**ECS Failover:**
- Automatic with ALB health checks
- Failed tasks replaced automatically
- No manual intervention needed

---

## Monitoring Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           CloudWatch                                      │
│                                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐             │
│  │   Log Groups   │  │    Metrics     │  │    Alarms      │             │
│  │                │  │                │  │                │             │
│  │ /aws/ecs/...   │  │ CPU, Memory    │  │ High CPU       │──────┐      │
│  │ /aws/rds/...   │  │ Request Count  │  │ High Memory    │      │      │
│  │ /aws/vpc/...   │  │ Response Time  │  │ Errors > 5%    │      │      │
│  └────────────────┘  │ Error Rate     │  │ Service Down   │      │      │
│          │           │ Custom Metrics │  └────────────────┘      │      │
│          │           └────────────────┘           │               │      │
│          │                    │                   │               │      │
│          ▼                    ▼                   ▼               ▼      │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │                     CloudWatch Dashboard                       │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                           ┌────────────────┐
                           │      SNS       │
                           │   (Alerts)     │
                           └────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌────────────┐  ┌────────────┐  ┌────────────┐
            │   Email    │  │   Slack    │  │  PagerDuty │
            └────────────┘  └────────────┘  └────────────┘
```

---

## Cost Optimization

### Estimated Monthly Costs (Production)

| Service | Configuration | Estimated Cost |
|---------|---------------|----------------|
| ECS Fargate | 4 tasks @ 1vCPU/2GB | $120 |
| RDS | db.t3.medium Multi-AZ | $150 |
| ALB | Application LB | $25 |
| NAT Gateway | 2 x NAT | $65 |
| S3 | 100GB + requests | $10 |
| CloudWatch | Logs + Metrics | $30 |
| ECR | Image storage | $5 |
| **Total** | | **~$405/month** |

### Cost Optimization Tips

1. Use Fargate Spot for non-critical workloads
2. Right-size RDS instance
3. Implement S3 lifecycle policies
4. Use reserved instances for predictable workloads
5. Clean up unused resources regularly
