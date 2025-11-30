#!/bin/bash
# Rollback script for Algo Trading System
# Usage: ./rollback.sh <environment> [options]
#
# Options:
#   --to-version <version>   Rollback to specific version/tag
#   --to-revision <num>      Rollback to specific ECS task revision
#   --dry-run                Show what would be done without doing it

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Default values
DRY_RUN=false
TARGET_VERSION=""
TARGET_REVISION=""

# Parse arguments
ENVIRONMENT="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
    case $1 in
        --to-version)
            TARGET_VERSION="$2"
            shift 2
            ;;
        --to-revision)
            TARGET_REVISION="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
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
    echo -e "${RED}Error: Invalid environment. Must be dev, staging, or prod${NC}"
    exit 1
fi

# Log functions
log() { echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"; }
log_success() { echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1"; }
log_warning() { echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"; }
log_error() { echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1"; }

# Get AWS info
AWS_REGION="${AWS_REGION:-ap-south-1}"
CLUSTER_NAME="algo-trading-${ENVIRONMENT}-cluster"

# Get available revisions
list_available_revisions() {
    local service="$1"
    local task_family="algo-trading-${ENVIRONMENT}-${service}"
    
    log "Available revisions for ${service}:"
    aws ecs list-task-definitions \
        --family-prefix "${task_family}" \
        --sort DESC \
        --max-items 10 \
        --region "${AWS_REGION}" \
        --query 'taskDefinitionArns[]' \
        --output text | tr '\t' '\n'
}

# Rollback a single service
rollback_service() {
    local service="$1"
    local service_name="algo-trading-${ENVIRONMENT}-${service}"
    local task_family="algo-trading-${ENVIRONMENT}-${service}"
    
    log "Rolling back service: ${service_name}"
    
    # Determine target task definition
    local target_task_def=""
    
    if [[ -n "$TARGET_REVISION" ]]; then
        target_task_def="${task_family}:${TARGET_REVISION}"
    else
        # Get previous task definition
        local current_task_def=$(aws ecs describe-services \
            --cluster "${CLUSTER_NAME}" \
            --services "${service_name}" \
            --region "${AWS_REGION}" \
            --query 'services[0].taskDefinition' \
            --output text)
        
        local current_revision=$(echo "${current_task_def}" | rev | cut -d':' -f1 | rev)
        local previous_revision=$((current_revision - 1))
        
        if [[ $previous_revision -lt 1 ]]; then
            log_error "No previous revision available for ${service_name}"
            return 1
        fi
        
        target_task_def="${task_family}:${previous_revision}"
    fi
    
    log "Target task definition: ${target_task_def}"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would update service to use: ${target_task_def}"
        return 0
    fi
    
    # Update service
    aws ecs update-service \
        --cluster "${CLUSTER_NAME}" \
        --service "${service_name}" \
        --task-definition "${target_task_def}" \
        --region "${AWS_REGION}" > /dev/null
    
    log_success "Service ${service_name} updated to ${target_task_def}"
}

# Wait for services to stabilize
wait_for_stability() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would wait for service stability"
        return 0
    fi
    
    log "Waiting for services to stabilize..."
    
    local services=("trading" "dashboard" "data-service")
    local service_names=()
    
    for service in "${services[@]}"; do
        service_names+=("algo-trading-${ENVIRONMENT}-${service}")
    done
    
    aws ecs wait services-stable \
        --cluster "${CLUSTER_NAME}" \
        --services "${service_names[@]}" \
        --region "${AWS_REGION}" || {
            log_error "Services failed to stabilize"
            return 1
        }
    
    log_success "All services are stable"
}

# Run health checks
run_health_checks() {
    log "Running post-rollback health checks..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would run health checks"
        return 0
    fi
    
    "${SCRIPT_DIR}/health_check.sh" "${ENVIRONMENT}" || {
        log_error "Health checks failed after rollback"
        return 1
    }
    
    log_success "Health checks passed"
}

# Main rollback flow
main() {
    echo ""
    echo "======================================"
    echo "  Algo Trading System Rollback"
    echo "======================================"
    echo "Environment: ${ENVIRONMENT}"
    echo "Dry Run: ${DRY_RUN}"
    echo "Target Version: ${TARGET_VERSION:-auto}"
    echo "Target Revision: ${TARGET_REVISION:-previous}"
    echo "======================================"
    echo ""
    
    # Production confirmation
    if [[ "$ENVIRONMENT" == "prod" && "$DRY_RUN" != "true" ]]; then
        echo -e "${YELLOW}⚠️  WARNING: You are about to rollback PRODUCTION!${NC}"
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log "Rollback cancelled"
            exit 0
        fi
    fi
    
    # Show available revisions
    if [[ -z "$TARGET_REVISION" ]]; then
        log "Fetching available revisions..."
        list_available_revisions "trading"
        echo ""
    fi
    
    # Rollback services
    local services=("trading" "dashboard" "data-service")
    
    for service in "${services[@]}"; do
        rollback_service "${service}" || {
            log_error "Failed to rollback ${service}"
            exit 1
        }
    done
    
    # Wait and verify
    wait_for_stability
    run_health_checks
    
    echo ""
    log_success "Rollback completed successfully! 🔄"
}

# Run main
main
