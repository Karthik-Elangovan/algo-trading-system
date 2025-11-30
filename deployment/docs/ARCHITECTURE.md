# Algo Trading System - Architecture Documentation

## Overview

The Algo Trading System is a cloud-native automated trading platform designed for the Indian stock market. It uses a microservices architecture deployed on AWS, leveraging containerization and infrastructure-as-code for reliability and scalability.

## System Architecture

### High-Level Architecture

```
                                    ┌──────────────────┐
                                    │   End Users      │
                                    │   (Traders)      │
                                    └────────┬─────────┘
                                             │
                                             │ HTTPS
                                             ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        Application Load Balancer                      │  │
│  │                    (algo-trading-{env}-alb)                          │  │
│  └────────────────────────────────┬─────────────────────────────────────┘  │
│                                   │                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                              VPC                                     │   │
│  │  ┌─────────────────────────────┐  ┌──────────────────────────────┐  │   │
│  │  │      Public Subnets         │  │      Private Subnets          │  │   │
│  │  │  ┌───────┐    ┌───────┐    │  │  ┌────────────────────────┐   │  │   │
│  │  │  │ NAT   │    │ NAT   │    │  │  │    ECS Cluster          │   │  │   │
│  │  │  │Gateway│    │Gateway│    │  │  │  ┌────────────────────┐ │   │  │   │
│  │  │  │ (AZ1) │    │ (AZ2) │    │  │  │  │  Trading Service   │ │   │  │   │
│  │  │  └───────┘    └───────┘    │  │  │  │  (Fargate)         │ │   │  │   │
│  │  │                            │  │  │  └────────────────────┘ │   │  │   │
│  │  │                            │  │  │  ┌────────────────────┐ │   │  │   │
│  │  │                            │  │  │  │  Dashboard Service │ │   │  │   │
│  │  │                            │  │  │  │  (Fargate)         │ │   │  │   │
│  │  │                            │  │  │  └────────────────────┘ │   │  │   │
│  │  │                            │  │  │  ┌────────────────────┐ │   │  │   │
│  │  │                            │  │  │  │  Data Service      │ │   │  │   │
│  │  │                            │  │  │  │  (Fargate)         │ │   │  │   │
│  │  │                            │  │  │  └────────────────────┘ │   │  │   │
│  │  │                            │  │  └────────────────────────┘   │  │   │
│  │  │                            │  │  ┌────────────────────────┐   │  │   │
│  │  │                            │  │  │    RDS PostgreSQL       │   │  │   │
│  │  │                            │  │  │    (Multi-AZ in Prod)   │   │  │   │
│  │  │                            │  │  └────────────────────────┘   │  │   │
│  │  └─────────────────────────────┘  └──────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐   │
│  │     ECR     │ │     S3      │ │  Secrets    │ │    CloudWatch       │   │
│  │ Repositories│ │   Bucket    │ │  Manager    │ │  Logs & Metrics     │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ API Calls
                                    ▼
                          ┌──────────────────┐
                          │   Angel One API  │
                          │   (External)     │
                          └──────────────────┘
```

### Component Details

#### 1. Trading Engine Service

**Purpose:** Core service that executes trading strategies and manages orders.

**Technology:**
- Python 3.12
- Angel One SmartAPI
- Custom strategy implementations

**Responsibilities:**
- Strategy execution
- Order management
- Position tracking
- Risk management
- Trade logging

**Scaling:**
- Horizontal scaling via ECS auto-scaling
- CPU-based scaling policy (target 70%)
- Min: 2, Max: 5 tasks in production

#### 2. Dashboard Service

**Purpose:** Web-based monitoring and control interface.

**Technology:**
- Python 3.12
- Streamlit
- Plotly for visualizations

**Responsibilities:**
- Real-time portfolio display
- Trade history visualization
- Strategy performance metrics
- System health monitoring
- Manual trade controls

**Scaling:**
- Fixed at 1-2 instances
- Load balanced via ALB

#### 3. Data Service

**Purpose:** Market data acquisition and processing.

**Technology:**
- Python 3.12
- Redis (optional caching)
- boto3 for AWS integration

**Responsibilities:**
- Market data fetching
- Historical data management
- Data caching
- S3 data persistence

**Scaling:**
- Single instance typically sufficient
- Can scale for high-frequency data needs

### Network Architecture

#### VPC Design

```
VPC CIDR: 10.x.0.0/16

┌─────────────────────────────────────────────────────────────┐
│                        VPC                                   │
│                                                              │
│  ┌─────────────────────────┐  ┌─────────────────────────┐   │
│  │    AZ-1 (ap-south-1a)   │  │    AZ-2 (ap-south-1b)   │   │
│  │                         │  │                         │   │
│  │  ┌───────────────────┐  │  │  ┌───────────────────┐  │   │
│  │  │  Public Subnet    │  │  │  │  Public Subnet    │  │   │
│  │  │  10.x.1.0/24      │  │  │  │  10.x.2.0/24      │  │   │
│  │  │  - NAT Gateway    │  │  │  │  - NAT Gateway    │  │   │
│  │  │  - ALB            │  │  │  │  - ALB            │  │   │
│  │  └───────────────────┘  │  │  └───────────────────┘  │   │
│  │                         │  │                         │   │
│  │  ┌───────────────────┐  │  │  ┌───────────────────┐  │   │
│  │  │  Private Subnet   │  │  │  │  Private Subnet   │  │   │
│  │  │  10.x.10.0/24     │  │  │  │  10.x.11.0/24     │  │   │
│  │  │  - ECS Tasks      │  │  │  │  - ECS Tasks      │  │   │
│  │  │  - RDS Primary    │  │  │  │  - RDS Standby    │  │   │
│  │  └───────────────────┘  │  │  └───────────────────┘  │   │
│  │                         │  │                         │   │
│  └─────────────────────────┘  └─────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Security Groups

| Security Group | Inbound Rules | Outbound Rules |
|---------------|---------------|----------------|
| ALB-SG | 80, 443 from 0.0.0.0/0 | All to VPC |
| ECS-SG | 8501 from ALB-SG | All to 0.0.0.0/0 |
| RDS-SG | 5432 from ECS-SG | None |

### Data Flow

#### Trading Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Strategy   │────▶│   Order      │────▶│  Angel One   │
│   Engine     │     │   Manager    │     │     API      │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    │
       │                    │                    │
       ▼                    ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Risk       │     │   Trade      │     │   Order      │
│   Manager    │     │   Logger     │     │   Response   │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │     RDS      │
                     │  PostgreSQL  │
                     └──────────────┘
```

#### Data Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Market Data │────▶│    Data      │────▶│    Redis     │
│     API      │     │   Service    │     │    Cache     │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            │
                            ▼
                     ┌──────────────┐
                     │      S3      │
                     │    Bucket    │
                     └──────────────┘
```

### Storage Architecture

#### S3 Bucket Structure

```
algo-trading-{env}-data-{account-id}/
├── backtest-results/
│   ├── 2024/
│   │   ├── 01/
│   │   └── 02/
│   └── ...
├── reports/
│   ├── daily/
│   ├── weekly/
│   └── monthly/
├── market-data/
│   ├── historical/
│   └── live/
└── logs/
    └── archived/
```

#### Database Schema

```sql
-- Core tables
trades (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20),
  side VARCHAR(10),
  quantity INTEGER,
  price DECIMAL(10,2),
  executed_at TIMESTAMP,
  strategy VARCHAR(50),
  pnl DECIMAL(10,2)
)

positions (
  id SERIAL PRIMARY KEY,
  symbol VARCHAR(20),
  quantity INTEGER,
  avg_price DECIMAL(10,2),
  current_price DECIMAL(10,2),
  unrealized_pnl DECIMAL(10,2),
  updated_at TIMESTAMP
)

orders (
  id SERIAL PRIMARY KEY,
  broker_order_id VARCHAR(50),
  symbol VARCHAR(20),
  side VARCHAR(10),
  order_type VARCHAR(20),
  quantity INTEGER,
  price DECIMAL(10,2),
  status VARCHAR(20),
  created_at TIMESTAMP
)
```

### Security Architecture

#### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  IAM Roles                                            │   │
│  │  - ECS Task Execution Role (ECR, Logs, Secrets)      │   │
│  │  - ECS Task Role (S3, CloudWatch)                    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Secrets Manager                                      │   │
│  │  - API credentials (encrypted at rest)               │   │
│  │  - Database passwords                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Network Security                                     │   │
│  │  - VPC isolation                                     │   │
│  │  - Security groups (least privilege)                 │   │
│  │  - Private subnets for compute/database              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Data Encryption                                      │   │
│  │  - S3: AES-256 server-side encryption               │   │
│  │  - RDS: Encrypted storage                           │   │
│  │  - In transit: TLS/HTTPS                            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Monitoring & Observability

#### Metrics Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Application │────▶│  CloudWatch  │────▶│  Dashboard   │
│    Metrics   │     │    Metrics   │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Alarms    │
                     │     SNS      │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Email     │
                     │    Alerts    │
                     └──────────────┘
```

#### Log Aggregation

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Container   │────▶│  CloudWatch  │────▶│  Log         │
│    Logs      │     │    Logs      │     │  Insights    │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │
       │                    │
       ▼                    ▼
┌──────────────┐     ┌──────────────┐
│  VPC Flow    │     │  S3 Archive  │
│    Logs      │     │  (Lifecycle) │
└──────────────┘     └──────────────┘
```

### Deployment Architecture

#### CI/CD Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   GitHub     │────▶│   GitHub     │────▶│    Build     │
│   Push       │     │   Actions    │     │   & Test     │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │    Docker    │
                                          │    Build     │
                                          └──────────────┘
                                                 │
                                                 ▼
                                          ┌──────────────┐
                                          │    ECR       │
                                          │    Push      │
                                          └──────────────┘
                                                 │
                            ┌────────────────────┼────────────────────┐
                            ▼                    ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
                     │     Dev      │     │   Staging    │     │    Prod      │
                     │   Deploy     │────▶│   Deploy     │────▶│   Deploy     │
                     └──────────────┘     └──────────────┘     └──────────────┘
```

### Environment Comparison

| Aspect | Development | Staging | Production |
|--------|-------------|---------|------------|
| ECS Tasks | 1 | 1 | 2-5 |
| RDS Instance | db.t3.micro | db.t3.small | db.t3.medium |
| RDS Multi-AZ | No | No | Yes |
| ALB Protection | No | No | Yes |
| Log Retention | 7 days | 14 days | 90 days |
| Backup Retention | 7 days | 7 days | 30 days |
| Auto-scaling | No | Yes | Yes |

### Cost Considerations

#### Monthly Cost Estimate (Production)

| Service | Specification | Estimated Cost |
|---------|--------------|----------------|
| ECS Fargate | 2 tasks × 1 vCPU × 2GB | $70 |
| ALB | 1 load balancer | $25 |
| RDS | db.t3.medium Multi-AZ | $80 |
| NAT Gateway | 2 gateways | $65 |
| S3 | 50 GB storage | $2 |
| CloudWatch | Logs & metrics | $15 |
| **Total** | | **~$260/month** |

### Technology Stack Summary

| Layer | Technology |
|-------|------------|
| Compute | AWS Fargate (ECS) |
| Container Registry | Amazon ECR |
| Database | Amazon RDS PostgreSQL |
| Object Storage | Amazon S3 |
| Load Balancing | Application Load Balancer |
| Secrets | AWS Secrets Manager |
| Monitoring | Amazon CloudWatch |
| Alerting | Amazon SNS |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Containers | Docker |
| Application | Python 3.12 |
| UI Framework | Streamlit |
| Broker API | Angel One SmartAPI |
