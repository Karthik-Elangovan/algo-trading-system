#!/bin/bash
# Health check script for Algo Trading System
# Usage: ./health_check.sh <environment> [options]
#
# Options:
#   --verbose    Show detailed output
#   --timeout    Timeout in seconds (default: 30)

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
VERBOSE=false
TIMEOUT=30
ENVIRONMENT="${1:-}"
shift || true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate environment
if [[ -z "$ENVIRONMENT" ]]; then
    echo -e "${RED}Error: Environment is required${NC}"
    echo "Usage: $0 <environment> [options]"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment${NC}"
    exit 1
fi

# Log functions
log() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
log_success() { echo -e "${GREEN}✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
log_error() { echo -e "${RED}✗${NC} $1"; }
log_verbose() { [[ "$VERBOSE" == "true" ]] && echo -e "  ${BLUE}→${NC} $1"; }

# AWS configuration
AWS_REGION="${AWS_REGION:-ap-south-1}"
CLUSTER_NAME="algo-trading-${ENVIRONMENT}-cluster"

# Health check results
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNINGS=0

# Record check result
record_result() {
    local status="$1"
    local name="$2"
    local message="$3"
    
    case "$status" in
        "pass")
            CHECKS_PASSED=$((CHECKS_PASSED + 1))
            log_success "$name: $message"
            ;;
        "fail")
            CHECKS_FAILED=$((CHECKS_FAILED + 1))
            log_error "$name: $message"
            ;;
        "warn")
            CHECKS_WARNINGS=$((CHECKS_WARNINGS + 1))
            log_warning "$name: $message"
            ;;
    esac
}

# Check ECS cluster health
check_ecs_cluster() {
    log "Checking ECS cluster..."
    
    local cluster_status=$(aws ecs describe-clusters \
        --clusters "${CLUSTER_NAME}" \
        --region "${AWS_REGION}" \
        --query 'clusters[0].status' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$cluster_status" == "ACTIVE" ]]; then
        record_result "pass" "ECS Cluster" "Active and healthy"
    else
        record_result "fail" "ECS Cluster" "Status: ${cluster_status}"
    fi
}

# Check ECS services
check_ecs_services() {
    log "Checking ECS services..."
    
    local services=("trading" "dashboard" "data-service")
    
    for service in "${services[@]}"; do
        local service_name="algo-trading-${ENVIRONMENT}-${service}"
        
        local service_info=$(aws ecs describe-services \
            --cluster "${CLUSTER_NAME}" \
            --services "${service_name}" \
            --region "${AWS_REGION}" \
            --query 'services[0]' \
            --output json 2>/dev/null || echo "{}")
        
        local status=$(echo "$service_info" | jq -r '.status // "NOT_FOUND"')
        local running=$(echo "$service_info" | jq -r '.runningCount // 0')
        local desired=$(echo "$service_info" | jq -r '.desiredCount // 0')
        
        log_verbose "${service_name}: status=${status}, running=${running}/${desired}"
        
        if [[ "$status" == "ACTIVE" && "$running" -eq "$desired" && "$running" -gt 0 ]]; then
            record_result "pass" "Service ${service}" "Running ${running}/${desired} tasks"
        elif [[ "$status" == "ACTIVE" && "$running" -lt "$desired" ]]; then
            record_result "warn" "Service ${service}" "Running ${running}/${desired} tasks"
        else
            record_result "fail" "Service ${service}" "Status: ${status}, Running: ${running}/${desired}"
        fi
    done
}

# Check RDS health
check_rds() {
    log "Checking RDS..."
    
    local db_identifier="algo-trading-${ENVIRONMENT}-db"
    
    local db_status=$(aws rds describe-db-instances \
        --db-instance-identifier "${db_identifier}" \
        --region "${AWS_REGION}" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$db_status" == "available" ]]; then
        record_result "pass" "RDS" "Available and healthy"
    elif [[ "$db_status" == "NOT_FOUND" ]]; then
        record_result "warn" "RDS" "Instance not found (may not be deployed)"
    else
        record_result "fail" "RDS" "Status: ${db_status}"
    fi
}

# Check ALB health
check_alb() {
    log "Checking Application Load Balancer..."
    
    local alb_name="algo-trading-${ENVIRONMENT}-alb"
    
    local alb_state=$(aws elbv2 describe-load-balancers \
        --names "${alb_name}" \
        --region "${AWS_REGION}" \
        --query 'LoadBalancers[0].State.Code' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$alb_state" == "active" ]]; then
        record_result "pass" "ALB" "Active"
        
        # Check target group health
        local tg_arn=$(aws elbv2 describe-target-groups \
            --names "algo-trading-${ENVIRONMENT}-dashboard-tg" \
            --region "${AWS_REGION}" \
            --query 'TargetGroups[0].TargetGroupArn' \
            --output text 2>/dev/null || echo "")
        
        if [[ -n "$tg_arn" && "$tg_arn" != "None" ]]; then
            local healthy_targets=$(aws elbv2 describe-target-health \
                --target-group-arn "${tg_arn}" \
                --region "${AWS_REGION}" \
                --query 'TargetHealthDescriptions[?TargetHealth.State==`healthy`] | length(@)' \
                --output text 2>/dev/null || echo "0")
            
            if [[ "$healthy_targets" -gt 0 ]]; then
                record_result "pass" "ALB Target Group" "${healthy_targets} healthy targets"
            else
                record_result "warn" "ALB Target Group" "No healthy targets"
            fi
        fi
    elif [[ "$alb_state" == "NOT_FOUND" ]]; then
        record_result "warn" "ALB" "Not found (may not be deployed)"
    else
        record_result "fail" "ALB" "State: ${alb_state}"
    fi
}

# Check dashboard endpoint
check_dashboard_endpoint() {
    log "Checking dashboard endpoint..."
    
    local alb_dns=$(aws elbv2 describe-load-balancers \
        --names "algo-trading-${ENVIRONMENT}-alb" \
        --region "${AWS_REGION}" \
        --query 'LoadBalancers[0].DNSName' \
        --output text 2>/dev/null || echo "")
    
    if [[ -z "$alb_dns" || "$alb_dns" == "None" ]]; then
        record_result "warn" "Dashboard Endpoint" "ALB DNS not available"
        return
    fi
    
    # Note: Using HTTP for initial health checks. Configure HTTPS with SSL/TLS
    # certificates for production by updating ALB listener and using HTTPS here.
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --connect-timeout "$TIMEOUT" \
        "http://${alb_dns}/_stcore/health" 2>/dev/null || echo "000")
    
    log_verbose "Dashboard HTTP response: ${http_code}"
    
    if [[ "$http_code" == "200" ]]; then
        record_result "pass" "Dashboard Endpoint" "Responding (HTTP ${http_code})"
    elif [[ "$http_code" == "000" ]]; then
        record_result "warn" "Dashboard Endpoint" "Connection failed (timeout or unreachable)"
    else
        record_result "fail" "Dashboard Endpoint" "HTTP ${http_code}"
    fi
}

# Check CloudWatch logs
check_cloudwatch_logs() {
    log "Checking CloudWatch logs..."
    
    local log_group="/aws/ecs/algo-trading-${ENVIRONMENT}"
    
    local log_group_exists=$(aws logs describe-log-groups \
        --log-group-name-prefix "${log_group}" \
        --region "${AWS_REGION}" \
        --query 'logGroups[0].logGroupName' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$log_group_exists" != "NOT_FOUND" && "$log_group_exists" != "None" ]]; then
        record_result "pass" "CloudWatch Logs" "Log group exists"
        
        # Check for recent error logs
        local recent_errors=$(aws logs filter-log-events \
            --log-group-name "${log_group}" \
            --start-time $(($(date +%s) * 1000 - 300000)) \
            --filter-pattern "ERROR" \
            --limit 10 \
            --region "${AWS_REGION}" \
            --query 'events | length(@)' \
            --output text 2>/dev/null || echo "0")
        
        if [[ "$recent_errors" -gt 0 ]]; then
            record_result "warn" "Recent Errors" "${recent_errors} error logs in last 5 minutes"
        else
            log_verbose "No recent error logs found"
        fi
    else
        record_result "warn" "CloudWatch Logs" "Log group not found"
    fi
}

# Check secrets manager
check_secrets() {
    log "Checking Secrets Manager..."
    
    local secret_name="algo-trading-${ENVIRONMENT}-api-credentials"
    
    local secret_status=$(aws secretsmanager describe-secret \
        --secret-id "${secret_name}" \
        --region "${AWS_REGION}" \
        --query 'VersionIdsToStages' \
        --output text 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$secret_status" != "NOT_FOUND" ]]; then
        record_result "pass" "Secrets Manager" "API credentials secret exists"
    else
        record_result "warn" "Secrets Manager" "Secret not found (may not be deployed)"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "======================================"
    echo "  Health Check Summary"
    echo "======================================"
    echo "Environment: ${ENVIRONMENT}"
    echo ""
    echo -e "${GREEN}Passed:${NC}   ${CHECKS_PASSED}"
    echo -e "${RED}Failed:${NC}   ${CHECKS_FAILED}"
    echo -e "${YELLOW}Warnings:${NC} ${CHECKS_WARNINGS}"
    echo "======================================"
    
    if [[ $CHECKS_FAILED -gt 0 ]]; then
        echo ""
        echo -e "${RED}❌ Health check failed!${NC}"
        return 1
    elif [[ $CHECKS_WARNINGS -gt 0 ]]; then
        echo ""
        echo -e "${YELLOW}⚠️  Health check passed with warnings${NC}"
        return 0
    else
        echo ""
        echo -e "${GREEN}✅ All health checks passed!${NC}"
        return 0
    fi
}

# Main
main() {
    echo ""
    echo "======================================"
    echo "  Algo Trading System Health Check"
    echo "======================================"
    echo "Environment: ${ENVIRONMENT}"
    echo "Timeout: ${TIMEOUT}s"
    echo "======================================"
    echo ""
    
    check_ecs_cluster
    check_ecs_services
    check_rds
    check_alb
    check_dashboard_endpoint
    check_cloudwatch_logs
    check_secrets
    
    print_summary
}

# Run main
main
