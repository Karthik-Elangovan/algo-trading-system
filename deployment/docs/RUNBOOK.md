# Operations Runbook

This runbook provides step-by-step procedures for operating the Algo Trading System in production.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Incident Response](#incident-response)
3. [Common Issues & Resolutions](#common-issues--resolutions)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Emergency Procedures](#emergency-procedures)
6. [Contacts](#contacts)

---

## Daily Operations

### Morning Checklist (Before Market Open - 8:45 AM IST)

- [ ] **Check system health**
  ```bash
  ./deployment/scripts/health_check.sh prod --verbose
  ```

- [ ] **Verify all services are running**
  ```bash
  aws ecs describe-services \
    --cluster algo-trading-prod-cluster \
    --services algo-trading-prod-trading algo-trading-prod-dashboard \
    --query 'services[].{Name:serviceName,Running:runningCount,Desired:desiredCount}'
  ```

- [ ] **Check CloudWatch for overnight alerts**
  - Navigate to CloudWatch console
  - Review any triggered alarms

- [ ] **Verify broker connectivity**
  - Check dashboard for broker connection status
  - Verify market data feed is active

- [ ] **Review previous day's trading activity**
  - Check P&L reports
  - Review executed trades

### Evening Checklist (After Market Close - 4:00 PM IST)

- [ ] **Review day's trading performance**
  - Total trades executed
  - Realized P&L
  - Active positions

- [ ] **Check for any errors or anomalies**
  ```bash
  aws logs filter-log-events \
    --log-group-name /aws/ecs/algo-trading-prod \
    --start-time $(date -d '8 hours ago' +%s000) \
    --filter-pattern "ERROR"
  ```

- [ ] **Backup daily reports**
  - Ensure trade logs are exported to S3
  - Verify backup completion

- [ ] **Update position tracking spreadsheet** (if applicable)

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 - Critical | System down, trading halted | 15 minutes | All services down, data loss |
| P2 - High | Major functionality impaired | 30 minutes | Trading service down, errors >5% |
| P3 - Medium | Minor functionality impaired | 2 hours | Dashboard slow, minor errors |
| P4 - Low | Cosmetic or minor issues | 24 hours | UI glitches, documentation |

### P1 - Critical Incident Response

1. **Acknowledge the alert** (within 5 minutes)
   - Update incident channel
   - Page on-call engineer if not already done

2. **Assess the situation**
   ```bash
   # Quick health check
   ./deployment/scripts/health_check.sh prod
   
   # Check recent logs
   aws logs tail /aws/ecs/algo-trading-prod --since 15m
   ```

3. **Halt trading if necessary**
   ```bash
   # Set trading_enabled to false
   aws ssm put-parameter \
     --name /algo-trading/prod/trading_enabled \
     --value "false" \
     --overwrite
   ```

4. **Attempt immediate resolution**
   - Check [Common Issues](#common-issues--resolutions) section
   - Restart affected services if appropriate

5. **Escalate if not resolved within 15 minutes**
   - Contact backup engineer
   - Notify stakeholders

6. **Document the incident**
   - Timeline of events
   - Actions taken
   - Root cause (if known)

### Service Restart Procedure

```bash
# Restart a specific ECS service
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --force-new-deployment

# Monitor deployment
aws ecs wait services-stable \
  --cluster algo-trading-prod-cluster \
  --services algo-trading-prod-trading
```

---

## Common Issues & Resolutions

### Issue: Trading Service Not Processing Orders

**Symptoms:**
- Orders not being placed
- No new trades in dashboard
- Error logs showing connection issues

**Resolution Steps:**

1. Check service status:
   ```bash
   aws ecs describe-services \
     --cluster algo-trading-prod-cluster \
     --services algo-trading-prod-trading
   ```

2. Check recent logs:
   ```bash
   aws logs tail /aws/ecs/algo-trading-prod/trading --since 10m
   ```

3. Verify broker connection:
   - Check if Angel One API is responding
   - Verify API credentials are valid

4. Restart if necessary:
   ```bash
   ./deployment/scripts/deploy.sh prod --skip-build --skip-infra
   ```

### Issue: High CPU/Memory Utilization

**Symptoms:**
- CloudWatch alarms triggered
- Service performance degradation

**Resolution Steps:**

1. Identify the bottleneck:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name CPUUtilization \
     --dimensions Name=ServiceName,Value=algo-trading-prod-trading \
     --start-time $(date -d '1 hour ago' --utc +%Y-%m-%dT%H:%M:%SZ) \
     --end-time $(date --utc +%Y-%m-%dT%H:%M:%SZ) \
     --period 300 \
     --statistics Average
   ```

2. Scale up if needed:
   ```bash
   aws ecs update-service \
     --cluster algo-trading-prod-cluster \
     --service algo-trading-prod-trading \
     --desired-count 3
   ```

3. Investigate root cause:
   - Check for memory leaks
   - Review recent code changes
   - Analyze query performance

### Issue: Database Connection Failures

**Symptoms:**
- "Connection refused" errors
- Timeout errors in logs

**Resolution Steps:**

1. Check RDS status:
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier algo-trading-prod-db
   ```

2. Verify security groups:
   ```bash
   aws ec2 describe-security-groups \
     --group-ids <rds-security-group-id>
   ```

3. Test connectivity:
   ```bash
   # From within the VPC
   psql -h <rds-endpoint> -U admin -d algotrading -c "SELECT 1;"
   ```

4. If RDS is in "modifying" state, wait for completion

### Issue: Dashboard Not Loading

**Symptoms:**
- 502/504 gateway errors
- Blank page or timeout

**Resolution Steps:**

1. Check ALB target health:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn <target-group-arn>
   ```

2. Check dashboard service:
   ```bash
   aws ecs describe-services \
     --cluster algo-trading-prod-cluster \
     --services algo-trading-prod-dashboard
   ```

3. Restart dashboard service:
   ```bash
   aws ecs update-service \
     --cluster algo-trading-prod-cluster \
     --service algo-trading-prod-dashboard \
     --force-new-deployment
   ```

---

## Maintenance Procedures

### Scheduled Maintenance Window

**Time:** Saturday 6:00 AM - 8:00 AM IST (market closed)

### Pre-Maintenance Checklist

- [ ] Notify stakeholders 24 hours in advance
- [ ] Backup database
- [ ] Document current state
- [ ] Prepare rollback plan

### Database Backup

```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier algo-trading-prod-db \
  --db-snapshot-identifier algo-trading-backup-$(date +%Y%m%d)
```

### Update Deployment

```bash
# Pull latest changes
git pull origin main

# Deploy with testing
./deployment/scripts/deploy.sh prod --dry-run

# If dry-run looks good, deploy
./deployment/scripts/deploy.sh prod
```

### Rollback Procedure

```bash
# Quick rollback to previous version
./deployment/scripts/rollback.sh prod

# Rollback to specific version
./deployment/scripts/rollback.sh prod --to-revision <revision-number>
```

### Database Maintenance

```bash
# Connect to RDS
psql -h <rds-endpoint> -U admin -d algotrading

# Vacuum analyze
VACUUM ANALYZE;

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename))
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
```

---

## Emergency Procedures

### Emergency Stop Trading

If trading needs to be stopped immediately:

```bash
# Method 1: Disable via parameter
aws ssm put-parameter \
  --name /algo-trading/prod/trading_enabled \
  --value "false" \
  --overwrite

# Method 2: Scale down trading service
aws ecs update-service \
  --cluster algo-trading-prod-cluster \
  --service algo-trading-prod-trading \
  --desired-count 0

# Method 3: Close all positions via dashboard
# Navigate to dashboard > Emergency Controls > Close All Positions
```

### System Recovery

After an outage:

1. **Assess damage**
   - Check data integrity
   - Review open positions
   - Calculate any losses

2. **Restore services**
   ```bash
   ./deployment/scripts/health_check.sh prod --verbose
   ```

3. **Verify broker reconciliation**
   - Compare local positions with broker
   - Reconcile any discrepancies

4. **Resume trading (if appropriate)**
   ```bash
   aws ssm put-parameter \
     --name /algo-trading/prod/trading_enabled \
     --value "true" \
     --overwrite
   ```

### Data Recovery

```bash
# Restore from RDS snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier algo-trading-prod-db-restored \
  --db-snapshot-identifier <snapshot-id>

# Restore from S3 backup
aws s3 cp s3://algo-trading-prod-data/backups/<date>/ ./restore/ --recursive
```

---

## Contacts

### On-Call Rotation

| Role | Primary | Backup |
|------|---------|--------|
| DevOps | [Name] | [Name] |
| Backend | [Name] | [Name] |
| Trading | [Name] | [Name] |

### External Contacts

| Service | Contact |
|---------|---------|
| Angel One Support | support@angelbroking.com |
| AWS Support | AWS Console > Support |

### Escalation Path

1. On-call engineer
2. Team lead
3. Engineering manager
4. CTO

---

## Appendix

### Useful Commands

```bash
# View running tasks
aws ecs list-tasks --cluster algo-trading-prod-cluster

# Get task details
aws ecs describe-tasks --cluster algo-trading-prod-cluster --tasks <task-arn>

# Stream logs
aws logs tail /aws/ecs/algo-trading-prod --follow

# Check ECS events
aws ecs describe-services \
  --cluster algo-trading-prod-cluster \
  --services algo-trading-prod-trading \
  --query 'services[0].events[:10]'
```

### Important URLs

- CloudWatch Dashboard: `https://console.aws.amazon.com/cloudwatch`
- ECS Console: `https://console.aws.amazon.com/ecs`
- RDS Console: `https://console.aws.amazon.com/rds`
- Production Dashboard: `http://<alb-dns>/`
