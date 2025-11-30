# Algo Trading System - Operations Runbook

This runbook provides procedures for operating and maintaining the Algo Trading System in production.

## Table of Contents

1. [System Overview](#system-overview)
2. [Daily Operations](#daily-operations)
3. [Incident Response](#incident-response)
4. [Common Procedures](#common-procedures)
5. [Disaster Recovery](#disaster-recovery)
6. [Contact Information](#contact-information)

## System Overview

### Components

| Component | Description | Critical Level |
|-----------|-------------|----------------|
| Trading Engine | Executes trading strategies | Critical |
| Dashboard | Streamlit UI for monitoring | High |
| Data Service | Market data processing | High |
| RDS PostgreSQL | Trade history storage | Critical |
| Redis | Data caching (optional) | Medium |

### Service Dependencies

```
Trading Engine
  ├── Angel One API (external)
  ├── RDS PostgreSQL
  ├── S3 (backtest results)
  └── Secrets Manager

Dashboard
  ├── Trading Engine (data)
  └── S3 (reports)

Data Service
  ├── Market Data APIs
  ├── Redis Cache
  └── S3 (market data)
```

## Daily Operations

### Market Hours Checklist

**Pre-Market (8:30 AM IST)**

- [ ] Verify all ECS services are running
- [ ] Check CloudWatch for overnight errors
- [ ] Verify database connectivity
- [ ] Confirm API credentials are valid
- [ ] Review system resource utilization

```bash
# Quick health check
./deployment/scripts/health_check.sh prod --verbose
```

**During Market Hours (9:15 AM - 3:30 PM IST)**

- [ ] Monitor trade executions
- [ ] Watch for error alerts
- [ ] Verify position tracking
- [ ] Monitor API rate limits

**Post-Market (3:30 PM IST)**

- [ ] Review daily trade summary
- [ ] Check for failed orders
- [ ] Export daily reports
- [ ] Verify data persistence

### Weekly Tasks

- [ ] Review CloudWatch metrics trends
- [ ] Analyze error patterns
- [ ] Update API credentials if needed
- [ ] Review and rotate secrets
- [ ] Check S3 storage usage
- [ ] Verify backups

### Monthly Tasks

- [ ] Review cost reports
- [ ] Audit IAM permissions
- [ ] Update dependencies
- [ ] Review security patches
- [ ] Test disaster recovery procedures

## Incident Response

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 | Critical - Complete outage | 15 minutes | Trading engine down during market hours |
| P2 | High - Major degradation | 30 minutes | Dashboard unavailable, high latency |
| P3 | Medium - Partial impact | 2 hours | Non-critical feature broken |
| P4 | Low - Minor issues | 24 hours | UI bugs, documentation issues |

### P1 - Trading Engine Down

**Symptoms:**
- No trades being executed
- ECS service showing 0 running tasks
- CloudWatch showing no metrics

**Immediate Actions:**

1. **Check ECS Service Status**
```bash
aws ecs describe-services \
  --cluster algo-trading-prod-cluster \
  --services algo-trading-prod-trading \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount,events:events[:3]}'
```

2. **Check Recent Logs**
```bash
aws logs tail /aws/ecs/algo-trading-prod \
  --filter-pattern "ERROR" \
  --since 30m
```

3. **Force New Deployment**
```bash
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --force-new-deployment
```

4. **If API Issues - Verify Credentials**
```bash
aws secretsmanager get-secret-value \
  --secret-id algo-trading-prod-api-credentials \
  --query 'SecretString'
```

5. **Rollback if Necessary**
```bash
./deployment/scripts/rollback.sh prod
```

### P1 - Database Unavailable

**Symptoms:**
- Connection errors in logs
- RDS status not "available"

**Immediate Actions:**

1. **Check RDS Status**
```bash
aws rds describe-db-instances \
  --db-instance-identifier algo-trading-prod-db \
  --query 'DBInstances[0].{status:DBInstanceStatus,endpoint:Endpoint}'
```

2. **Check Security Groups**
```bash
aws ec2 describe-security-groups \
  --group-ids <rds-sg-id> \
  --query 'SecurityGroups[0].IpPermissions'
```

3. **Failover (if Multi-AZ)**
```bash
aws rds reboot-db-instance \
  --db-instance-identifier algo-trading-prod-db \
  --force-failover
```

### P2 - High Latency

**Symptoms:**
- Slow dashboard response
- ALB latency metrics elevated
- Trade execution delays

**Diagnostic Steps:**

1. **Check Container Resources**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=algo-trading-prod-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average
```

2. **Check Database Performance**
```bash
aws rds describe-db-instances \
  --db-instance-identifier algo-trading-prod-db \
  --query 'DBInstances[0].PerformanceInsightsEnabled'
```

3. **Scale Services if Needed**
```bash
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --desired-count 3
```

### P2 - API Rate Limit

**Symptoms:**
- 429 errors in logs
- Trade rejections

**Immediate Actions:**

1. **Reduce Trade Frequency**
```bash
# Update environment variable
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --task-definition algo-trading-prod-trading-limited
```

2. **Contact Broker** if needed for rate limit increase

## Common Procedures

### Scaling ECS Services

**Scale Up:**
```bash
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --desired-count 3
```

**Scale Down:**
```bash
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --desired-count 1
```

### Updating API Credentials

```bash
# Update secret
aws secretsmanager update-secret \
  --secret-id algo-trading-prod-api-credentials \
  --secret-string '{
    "ANGEL_ONE_API_KEY": "new-api-key",
    "ANGEL_ONE_CLIENT_ID": "new-client-id"
  }'

# Force service restart to pick up new credentials
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --force-new-deployment
```

### Database Maintenance

**Create Manual Snapshot:**
```bash
aws rds create-db-snapshot \
  --db-instance-identifier algo-trading-prod-db \
  --db-snapshot-identifier algo-trading-prod-manual-$(date +%Y%m%d)
```

**Export Data:**
```bash
# Connect to database and export
pg_dump -h <rds-endpoint> -U admin -d algotrading_prod > backup.sql
```

### Log Analysis

**Search for Errors:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/ecs/algo-trading-prod \
  --filter-pattern "ERROR" \
  --start-time $(($(date +%s) * 1000 - 3600000))
```

**Export Logs:**
```bash
aws logs create-export-task \
  --log-group-name /aws/ecs/algo-trading-prod \
  --from $(date -d '1 day ago' +%s)000 \
  --to $(date +%s)000 \
  --destination algo-trading-prod-logs-export \
  --destination-prefix logs
```

## Disaster Recovery

### RTO/RPO Targets

| Component | RTO | RPO |
|-----------|-----|-----|
| Trading Engine | 15 minutes | 0 (stateless) |
| Database | 1 hour | 5 minutes (snapshots) |
| Dashboard | 30 minutes | 0 (stateless) |

### Full System Recovery

1. **Restore Database**
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier algo-trading-prod-db-restored \
  --db-snapshot-identifier <snapshot-id>
```

2. **Update Connection Strings**
```bash
# Update secrets with new endpoint
aws secretsmanager update-secret \
  --secret-id algo-trading-prod-db-password \
  --secret-string '{"host": "new-endpoint"}'
```

3. **Redeploy Services**
```bash
./deployment/scripts/deploy.sh prod --skip-build
```

### Backup Verification

**Monthly Test:**
1. Restore database to test environment
2. Verify data integrity
3. Run integration tests
4. Document results

## Contact Information

### Escalation Path

| Level | Contact | When to Escalate |
|-------|---------|------------------|
| L1 | On-call engineer | First response |
| L2 | Senior engineer | After 30 min unresolved |
| L3 | Tech lead | Critical decisions |
| External | AWS Support | Infrastructure issues |

### External Dependencies

| Service | Support Contact | SLA |
|---------|-----------------|-----|
| Angel One | support@angelone.in | Business hours |
| AWS | AWS Support Console | Per support plan |

## Appendix

### Useful Commands

```bash
# List all running tasks
aws ecs list-tasks --cluster algo-trading-prod-cluster

# Describe task
aws ecs describe-tasks --cluster algo-trading-prod-cluster --tasks <task-id>

# Execute command in container
aws ecs execute-command \
  --cluster algo-trading-prod-cluster \
  --task <task-id> \
  --container trading \
  --interactive \
  --command "/bin/bash"

# Get ALB DNS
aws elbv2 describe-load-balancers \
  --names algo-trading-prod-alb \
  --query 'LoadBalancers[0].DNSName'
```

### Key Metrics to Monitor

| Metric | Normal Range | Alert Threshold |
|--------|--------------|-----------------|
| ECS CPU | < 60% | > 80% |
| ECS Memory | < 70% | > 80% |
| ALB Latency | < 500ms | > 2s |
| RDS Connections | < 50 | > 80 |
| Error Rate | < 0.1% | > 1% |
