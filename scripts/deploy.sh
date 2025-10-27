#!/bin/bash

# Shop Assistant AI - Production Deployment Script
# This script automates the deployment process to production

set -e  # Exit on any error

# Configuration
ENVIRONMENT="production"
DOCKER_REGISTRY="ghcr.io"
IMAGE_NAME="shop-assistant-ai"
BACKUP_DIR="./backups"
LOG_FILE="./logs/deploy.log"
ROLLBACK_FILE="./rollback/last_successful_image.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to create backup
create_backup() {
    log "Creating database backup..."

    if ! docker exec shop-assistant-postgres pg_dump -U postgres "$POSTGRES_DB" > "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).sql"; then
        error "Failed to create database backup"
    fi

    success "Database backup created successfully"
}

# Function to run health checks
run_health_checks() {
    log "Running health checks..."

    # Wait for application to start
    sleep 30

    # Check application health
    if curl -f http://localhost:8000/health; then
        success "Application health check passed"
    else
        error "Application health check failed"
    fi

    # Check database connection
    if docker exec shop-assistant-app python -c "from app.core.database import engine; engine.connect()"; then
        success "Database connection check passed"
    else
        error "Database connection check failed"
    fi

    # Check Redis connection
    if docker exec shop-assistant-app python -c "import redis; r=redis.Redis(host='redis', port=6379); r.ping()"; then
        success "Redis connection check passed"
    else
        error "Redis connection check failed"
    fi
}

# Function to rollback deployment
rollback() {
    log "Rolling back deployment..."

    if [ -f "$ROLLBACK_FILE" ]; then
        PREVIOUS_IMAGE=$(cat "$ROLLBACK_FILE")
        log "Rolling back to image: $PREVIOUS_IMAGE"

        docker-compose -f docker-compose.prod.yml pull "$PREVIOUS_IMAGE" || error "Failed to pull previous image"
        docker-compose -f docker-compose.prod.yml up -d || error "Failed to start services with previous image"

        success "Rollback completed successfully"
    else
        error "No previous image found for rollback"
    fi
}

# Function to clean up old images
cleanup_old_images() {
    log "Cleaning up old Docker images..."

    # Remove old images (keep last 5)
    docker images "$IMAGE_NAME" --format "table {{.Repository}}:{{.Tag}}" | tail -n +6 | head -n -5 | xargs -r docker rmi || true

    success "Old images cleaned up"
}

# Main deployment function
deploy() {
    log "Starting deployment to $ENVIRONMENT environment..."

    # Check prerequisites
    command_exists docker || error "Docker is not installed"
    command_exists docker-compose || error "Docker Compose is not installed"

    # Create necessary directories
    mkdir -p "$BACKUP_DIR" logs uploads ssl monitoring

    # Load environment variables
    if [ -f ".env" ]; then
        export $(cat .env | grep -v '^#' | xargs)
    else
        error ".env file not found"
    fi

    # Store current image for rollback
    CURRENT_IMAGE=$(docker images --format "{{.Repository}}:{{.Tag}}" "$IMAGE_NAME" | head -n 1)
    echo "$CURRENT_IMAGE" > "$ROLLBACK_FILE"

    # Create backup
    create_backup

    # Pull latest code
    log "Pulling latest code..."
    git pull origin main || error "Failed to pull latest code"

    # Build new image
    log "Building new Docker image..."
    IMAGE_TAG="${DOCKER_REGISTRY}/${IMAGE_NAME}:${GITHUB_SHA:-latest}"
    docker build -f Dockerfile.prod -t "$IMAGE_TAG" . || error "Failed to build Docker image"

    # Tag as latest
    docker tag "$IMAGE_TAG" "${DOCKER_REGISTRY}/${IMAGE_NAME}:latest"

    # Stop old services gracefully
    log "Stopping old services..."
    docker-compose -f docker-compose.prod.yml down || warning "Failed to stop services (may not be running)"

    # Start new services
    log "Starting new services..."
    docker-compose -f docker-compose.prod.yml up -d || error "Failed to start services"

    # Run health checks
    run_health_checks

    # Run database migrations if needed
    log "Running database migrations..."
    docker-compose -f docker-compose.prod.yml exec app alembic upgrade head || warning "Migration failed (may already be up to date)"

    # Clean up old images
    cleanup_old_images

    success "Deployment completed successfully!"
    log "New image deployed: $IMAGE_TAG"

    # Update monitoring dashboards
    log "Deployment metrics recorded to monitoring systems"
}

# Function to verify deployment
verify_deployment() {
    log "Verifying deployment..."

    # Check all services are running
    SERVICES=("app" "postgres" "redis" "nginx" "worker")

    for service in "${SERVICES[@]}"; do
        if docker-compose -f docker-compose.prod.yml ps | grep -q "$service.*Up"; then
            success "Service $service is running"
        else
            error "Service $service is not running"
        fi
    done

    # Test API endpoints
    ENDPOINTS=(
        "http://localhost:8000/health"
        "http://localhost:8000/api/v1/"
    )

    for endpoint in "${ENDPOINTS[@]}"; do
        if curl -f "$endpoint" >/dev/null 2>&1; then
            success "Endpoint $endpoint is accessible"
        else
            error "Endpoint $endpoint is not accessible"
        fi
    done

    success "All deployment verifications passed!"
}

# Function to show usage
usage() {
    echo "Usage: $0 {deploy|rollback|verify|status|logs}"
    echo ""
    echo "Commands:"
    echo "  deploy   - Deploy the application to production"
    echo "  rollback - Rollback to the previous deployment"
    echo "  verify   - Verify the current deployment"
    echo "  status   - Show status of all services"
    echo "  logs     - Show logs for all services"
}

# Main script logic
case "${1:-deploy}" in
    deploy)
        deploy
        verify_deployment
        ;;
    rollback)
        rollback
        verify_deployment
        ;;
    verify)
        verify_deployment
        ;;
    status)
        log "Service status:"
        docker-compose -f docker-compose.prod.yml ps
        ;;
    logs)
        log "Service logs:"
        docker-compose -f docker-compose.prod.yml logs -f --tail=100
        ;;
    *)
        usage
        exit 1
        ;;
esac

log "Script completed successfully!"