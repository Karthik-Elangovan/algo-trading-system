#!/bin/bash
# Deployment script for Algo Trading System
# Usage: ./deploy.sh <environment> [options]
#
# Options:
#   --dry-run       Show what would be deployed without deploying
#   --skip-build    Skip Docker image build
#   --skip-infra    Skip Terraform infrastructure deployment
#   --force         Force deployment even if health checks fail

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Default values
DRY_RUN=false
SKIP_BUILD=false
SKIP_INFRA=false
FORCE=false

# Parse arguments
ENVIRONMENT="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --skip-infra)
            SKIP_INFRA=true
            shift
            ;;
        --force)
            FORCE=true
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
    echo "Environments: dev, staging, prod"
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo -e "${RED}Error: Invalid environment. Must be dev, staging, or prod${NC}"
    exit 1
fi

# Log function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

# Check required tools
check_prerequisites() {
    log "Checking prerequisites..."
    
    local missing_tools=()
    
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
    fi
    
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if ! command -v terraform &> /dev/null; then
        missing_tools+=("terraform")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured or invalid"
        exit 1
    fi
    
    log_success "All prerequisites met"
}

# Get AWS account information
get_aws_info() {
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    AWS_REGION="${AWS_REGION:-ap-south-1}"
    ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    
    log "AWS Account: ${AWS_ACCOUNT_ID}"
    log "AWS Region: ${AWS_REGION}"
}

# Build and push Docker images
build_and_push_images() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        log_warning "Skipping Docker build"
        return
    fi
    
    log "Building and pushing Docker images..."
    
    # Login to ECR
    aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ECR_REGISTRY}"
    
    local images=("trading" "dashboard" "data")
    local docker_dir="${PROJECT_ROOT}/deployment/docker"
    
    for image in "${images[@]}"; do
        local image_name="algo-trading-${ENVIRONMENT}-${image}"
        local image_tag="${ECR_REGISTRY}/${image_name}:latest"
        local dockerfile="${docker_dir}/Dockerfile.${image}"
        
        log "Building ${image} image..."
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "[DRY-RUN] Would build: docker build -f ${dockerfile} -t ${image_tag} ${PROJECT_ROOT}"
            log "[DRY-RUN] Would push: docker push ${image_tag}"
        else
            # Build image
            docker build -f "${dockerfile}" -t "${image_tag}" "${PROJECT_ROOT}"
            
            # Push to ECR
            docker push "${image_tag}"
            
            log_success "Built and pushed ${image_tag}"
        fi
    done
}

# Deploy infrastructure with Terraform
deploy_infrastructure() {
    if [[ "$SKIP_INFRA" == "true" ]]; then
        log_warning "Skipping infrastructure deployment"
        return
    fi
    
    log "Deploying infrastructure with Terraform..."
    
    local terraform_dir="${PROJECT_ROOT}/deployment/terraform"
    local tfvars_file="${terraform_dir}/environments/${ENVIRONMENT}.tfvars"
    
    if [[ ! -f "$tfvars_file" ]]; then
        log_error "Terraform variables file not found: ${tfvars_file}"
        exit 1
    fi
    
    cd "${terraform_dir}"
    
    # Initialize Terraform
    log "Initializing Terraform..."
    terraform init
    
    # Plan deployment
    log "Planning Terraform deployment..."
    terraform plan -var-file="${tfvars_file}" -out=tfplan
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would apply: terraform apply tfplan"
        return
    fi
    
    # Apply deployment
    log "Applying Terraform deployment..."
    terraform apply tfplan
    
    # Cleanup plan file
    rm -f tfplan
    
    log_success "Infrastructure deployed successfully"
}

# Update ECS services
update_ecs_services() {
    log "Updating ECS services..."
    
    local cluster_name="algo-trading-${ENVIRONMENT}-cluster"
    local services=("trading" "dashboard" "data-service")
    
    for service in "${services[@]}"; do
        local service_name="algo-trading-${ENVIRONMENT}-${service}"
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log "[DRY-RUN] Would update service: ${service_name}"
        else
            log "Forcing new deployment for ${service_name}..."
            aws ecs update-service \
                --cluster "${cluster_name}" \
                --service "${service_name}" \
                --force-new-deployment \
                --region "${AWS_REGION}" > /dev/null || true
        fi
    done
    
    log_success "ECS services updated"
}

# Wait for services to be stable
wait_for_services() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would wait for services to stabilize"
        return
    fi
    
    log "Waiting for services to stabilize..."
    
    local cluster_name="algo-trading-${ENVIRONMENT}-cluster"
    local timeout=600  # 10 minutes
    
    aws ecs wait services-stable \
        --cluster "${cluster_name}" \
        --services "algo-trading-${ENVIRONMENT}-trading" \
        --region "${AWS_REGION}" || {
            if [[ "$FORCE" == "true" ]]; then
                log_warning "Services not stable, but continuing due to --force flag"
            else
                log_error "Services failed to stabilize within timeout"
                exit 1
            fi
        }
    
    log_success "Services are stable"
}

# Run health checks
run_health_checks() {
    log "Running health checks..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY-RUN] Would run health checks"
        return
    fi
    
    "${SCRIPT_DIR}/health_check.sh" "${ENVIRONMENT}" || {
        if [[ "$FORCE" == "true" ]]; then
            log_warning "Health checks failed, but continuing due to --force flag"
        else
            log_error "Health checks failed"
            exit 1
        fi
    }
    
    log_success "Health checks passed"
}

# Get deployment outputs
get_deployment_outputs() {
    log "Deployment outputs:"
    
    local terraform_dir="${PROJECT_ROOT}/deployment/terraform"
    cd "${terraform_dir}"
    
    echo ""
    echo "==================================="
    echo "  Deployment Summary"
    echo "==================================="
    echo "Environment: ${ENVIRONMENT}"
    echo "Region: ${AWS_REGION}"
    echo ""
    
    if [[ "$DRY_RUN" != "true" ]]; then
        terraform output 2>/dev/null || true
    fi
    
    echo "==================================="
}

# Main deployment flow
main() {
    echo ""
    echo "======================================"
    echo "  Algo Trading System Deployment"
    echo "======================================"
    echo "Environment: ${ENVIRONMENT}"
    echo "Dry Run: ${DRY_RUN}"
    echo "Skip Build: ${SKIP_BUILD}"
    echo "Skip Infra: ${SKIP_INFRA}"
    echo "Force: ${FORCE}"
    echo "======================================"
    echo ""
    
    check_prerequisites
    get_aws_info
    
    # Production confirmation
    if [[ "$ENVIRONMENT" == "prod" && "$DRY_RUN" != "true" ]]; then
        echo ""
        echo -e "${YELLOW}⚠️  WARNING: You are about to deploy to PRODUCTION!${NC}"
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log "Deployment cancelled"
            exit 0
        fi
    fi
    
    build_and_push_images
    deploy_infrastructure
    update_ecs_services
    wait_for_services
    run_health_checks
    get_deployment_outputs
    
    echo ""
    log_success "Deployment completed successfully! 🚀"
}

# Run main
main
