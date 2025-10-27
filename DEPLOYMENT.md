# Deployment Guide for Shop Assistant AI (Phase 4)

This guide covers the complete deployment process for Shop Assistant AI with all Phase 4 enterprise features including LangGraph optimization, advanced security, and comprehensive monitoring.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Local Development Setup](#local-development-setup)
4. [Docker Deployment](#docker-deployment)
5. [Production Deployment](#production-deployment)
6. [CI/CD Pipeline](#cicd-pipeline)
7. [Monitoring and Observability](#monitoring-and-observability)
8. [Security Configuration](#security-configuration)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+), macOS, or Windows 10/11
- **Docker**: Version 20.10+ with Docker Compose v2.0+
- **Python**: 3.11+ (for local development)
- **Memory**: Minimum 8GB RAM (16GB+ recommended for production)
- **Storage**: Minimum 20GB free space
- **Network**: Stable internet connection for external API dependencies

### Required Software

1. **Docker & Docker Compose**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install docker.io docker-compose-plugin

   # macOS (using Homebrew)
   brew install docker docker-compose

   # Windows
   # Download and install Docker Desktop from https://www.docker.com/products/docker-desktop
   ```

2. **Git**
   ```bash
   # Ubuntu/Debian
   sudo apt install git

   # macOS
   brew install git

   # Windows
   # Download from https://git-scm.com/download/win
   ```

3. **Node.js** (for development tools)
   ```bash
   # Using Node Version Manager (recommended)
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   nvm install 18
   nvm use 18
   ```

### External Services

- **Database**: PostgreSQL 15+ (or use provided Docker container)
- **Cache**: Redis 7+ (or use provided Docker container)
- **External APIs**:
  - OpenRouter API key (for LLM services)
  - Cohere API key (for embedding services)
  - Shopify API credentials (if using Shopify integration)

## Environment Configuration

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/shop-assistant-ai.git
cd shop-assistant-ai
```

### 2. Environment Variables

Create environment configuration files:

#### Development Environment (`.env`)

```bash
# Copy example configuration
cp .env.example .env

# Edit with your values
nano .env
```

Required variables:

```bash
# Application
PROJECT_NAME="Shop Assistant AI"
VERSION="0.1.0"
ENVIRONMENT="development"
DEBUG=true
USE_LANGGRAPH=true

# Security
SECRET_KEY=your-super-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/shop_assistant

# Redis
REDIS_URL=redis://localhost:6379/0

# External APIs
OPENROUTER_API_KEY=your-openrouter-api-key
COHERE_API_KEY=your-cohere-api-key

# Shopify (optional)
SHOPIFY_ACCESS_TOKEN=your-shopify-access-token
SHOPIFY_STORE_URL=your-store.myshopify.com

# Logging
LOG_LEVEL=INFO
```

#### Production Environment (`.env.prod`)

```bash
# Production configuration with security hardening
ENVIRONMENT=production
DEBUG=false
USE_LANGGRAPH=true

# Use strong, randomly generated secrets
SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=postgresql://postgres:strong-password@postgres:5432/shop_assistant_prod
REDIS_URL=redis://redis:6379/0

# Enable all security features
ENABLE_SECURITY_MIDDLEWARE=true
ENABLE_RATE_LIMITING=true
ENABLE_THREAT_DETECTION=true

# Monitoring
ENABLE_METRICS=true
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true

# Logging
LOG_LEVEL=WARNING
STRUCTURED_LOGGING=true
```

### 3. SSL/TLS Configuration (Production)

```bash
# Create SSL directory
mkdir -p config/ssl

# Generate self-signed certificates (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout config/ssl/server.key \
  -out config/ssl/server.crt

# For production, use certificates from Let's Encrypt or your CA
```

## Local Development Setup

### Option 1: Direct Python Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Start databases (if not using Docker services)
docker-compose up db redis -d

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Docker Development

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f app

# Stop environment
docker-compose -f docker-compose.dev.yml down
```

### Development Tools

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Code formatting
black app/
isort app/

# Linting
flake8 app/
mypy app/

# Security checks
bandit -r app/
safety check
```

## Docker Deployment

### Build Custom Image

```bash
# Build for production
docker build -f Dockerfile --target production -t shop-assistant-ai:latest .

# Build for development
docker build -f Dockerfile --target development -t shop-assistant-ai:dev .
```

### Run with Docker Compose

```bash
# Development
docker-compose -f docker-compose.dev.yml up -d

# Production
docker-compose -f docker-compose.prod.yml up -d

# With specific profile
docker-compose -f docker-compose.prod.yml --profile monitoring up -d
```

### Container Management

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f app

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale app=3

# Stop services
docker-compose down

# Remove volumes (WARNING: This deletes data)
docker-compose down -v
```

## Production Deployment

### Automated Deployment Script

Use the provided deployment script for production deployments:

```bash
# Make script executable
chmod +x scripts/deploy.sh

# Deploy to production
./scripts/deploy.sh deploy

# Deploy specific version
./scripts/deploy.sh deploy v1.2.3

# Rollback deployment
./scripts/deploy.sh rollback

# Verify deployment
./scripts/deploy.sh verify

# View deployment status
./scripts/deploy.sh status

# View logs
./scripts/deploy.sh logs
```

### Manual Production Deployment

#### 1. Prepare Infrastructure

```bash
# Create production directories
mkdir -p logs data uploads backups config

# Set proper permissions
chmod 755 logs data uploads backups
chmod 600 config/ssl/*
```

#### 2. Deploy Services

```bash
# Start infrastructure services
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for services to be ready
sleep 30

# Run database migrations
docker-compose -f docker-compose.prod.yml run --rm app alembic upgrade head

# Deploy application stack
docker-compose -f docker-compose.prod.yml up -d

# Deploy monitoring stack
docker-compose -f docker-compose.prod.yml --profile monitoring up -d
```

#### 3. Verify Deployment

```bash
# Check service health
curl http://localhost:8000/health

# Check API endpoints
curl http://localhost:8000/api/v1/

# Run smoke tests
python scripts/smoke_tests.py
```

### Load Balancer Configuration

#### Nginx Configuration (`config/nginx.conf`)

```nginx
upstream app_servers {
    server app:8000;
    # Add more servers for horizontal scaling
    # server app_2:8000;
    # server app_3:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL configuration
    ssl_certificate /etc/nginx/ssl/server.crt;
    ssl_certificate_key /etc/nginx/ssl/server.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        proxy_pass http://app_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Apply rate limiting
        limit_req zone=api burst=20 nodelay;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://app_servers;
        access_log off;
    }

    # Static files
    location /static/ {
        alias /app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## CI/CD Pipeline

### GitHub Actions Workflow

The project includes a comprehensive CI/CD pipeline (`.github/workflows/ci-cd.yml`) that:

1. **Code Quality Checks**
   - Formatting (Black, isort)
   - Linting (flake8, mypy)
   - Security scanning (bandit, safety)

2. **Testing**
   - Unit tests with coverage
   - Integration tests
   - Phase 4 feature tests
   - Security tests

3. **Docker Build**
   - Multi-platform builds (amd64, arm64)
   - Security scanning (Trivy)
   - Registry pushing

4. **Deployment**
   - Automated staging deployments
   - Production deployments on releases
   - Rollback capabilities

### Pipeline Triggers

- **Push to `develop`**: Staging deployment
- **Push to `main`**: Production deployment
- **Pull Request**: Testing and validation
- **Release**: Production deployment with version tag

### Environment Variables in GitHub

Set these in your GitHub repository settings:

```bash
# Required
OPENROUTER_API_KEY
COHERE_API_KEY
POSTGRES_PASSWORD
SECRET_KEY

# Optional
SHOPIFY_ACCESS_TOKEN
SHOPIFY_STORE_URL
GRAFANA_PASSWORD
```

## Monitoring and Observability

### Prometheus Metrics

Access metrics at: `http://localhost:9090`

Key metrics available:

- Application performance metrics
- Database connection pool metrics
- Redis cache metrics
- HTTP request metrics
- Custom business metrics

### Grafana Dashboards

Access dashboards at: `http://localhost:3000`

Default credentials: `admin/admin` (change in production)

Available dashboards:

1. **Application Overview**
2. **Database Performance**
3. **Cache Performance**
4. **Security Monitoring**
5. **Business Intelligence**

### Log Aggregation

Logs are collected and stored in Loki, accessible through Grafana.

#### Log Structure

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "message": "Request processed",
  "request_id": "req_123456",
  "method": "POST",
  "path": "/api/v1/chat",
  "status_code": 200,
  "duration_ms": 150,
  "user_id": "user_123",
  "security_events": 0
}
```

### Alerting

Configure alerts in Prometheus (`config/prometheus.yml`):

```yaml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

rule_files:
  - "alert_rules.yml"
```

Example alert rules (`config/alert_rules.yml`):

```yaml
groups:
  - name: shop_assistant_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High response time detected
          description: "95th percentile response time is {{ $value }} seconds"
```

## Security Configuration

### Enterprise Security Features

The application includes comprehensive security features:

1. **Rate Limiting**
   - IP-based rate limiting
   - User-based rate limiting
   - Endpoint-specific limits
   - Custom rules support

2. **Threat Detection**
   - SQL injection detection
   - XSS detection
   - Path traversal detection
   - Brute force protection
   - DDoS protection

3. **Security Headers**
   - Content Security Policy
   - X-Frame-Options
   - X-Content-Type-Options
   - Strict-Transport-Security

4. **Authentication & Authorization**
   - JWT-based authentication
   - Role-based access control
   - API key management

### Security Monitoring

Monitor security events through:

1. **Security Dashboard**: `http://localhost:8000/security/dashboard`
2. **Grafana Security Panel**: `http://localhost:3000/d/security`
3. **Log Analysis**: Through Loki in Grafana

### Security Best Practices

1. **Regular Updates**
   ```bash
   # Update base images
   docker-compose pull
   docker-compose up -d

   # Update Python dependencies
   pip install --upgrade -r requirements.txt
   ```

2. **Security Scanning**
   ```bash
   # Run security scans
   bandit -r app/
   safety check
   trivy image shop-assistant-ai:latest
   ```

3. **Access Control**
   - Use strong, unique passwords
   - Implement multi-factor authentication
   - Regular user access reviews
   - Principle of least privilege

## Backup and Recovery

### Database Backups

Automated backups are configured in the production Compose file:

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres shop_assistant > backup.sql

# Restore from backup
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U postgres shop_assistant < backup.sql
```

### Application State Backups

```bash
# Backup Redis data
docker-compose -f docker-compose.prod.yml exec redis redis-cli BGSAVE
docker cp shop-assistant-redis:/data/dump.rdb ./backups/

# Backup application data
docker run --rm -v shop-assistant-ai_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/app_data_backup.tar.gz -C /data .
```

### Disaster Recovery

1. **Recovery Procedure**
   ```bash
   # Stop services
   docker-compose -f docker-compose.prod.yml down

   # Restore data
   # Restore database
   # Restore Redis data
   # Restore application data

   # Start services
   docker-compose -f docker-compose.prod.yml up -d

   # Verify recovery
   ./scripts/deploy.sh verify
   ```

2. **Recovery Time Objective (RTO)**: 30 minutes
3. **Recovery Point Objective (RPO)**: 15 minutes

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues

```bash
# Check database status
docker-compose -f docker-compose.prod.yml ps postgres

# Check database logs
docker-compose -f docker-compose.prod.yml logs postgres

# Test connection
docker-compose -f docker-compose.prod.yml exec app python -c "from app.core.database import engine; print(engine.connect())"
```

#### 2. Redis Connection Issues

```bash
# Check Redis status
docker-compose -f docker-compose.prod.yml ps redis

# Test Redis connection
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check Redis logs
docker-compose -f docker-compose.prod.yml logs redis
```

#### 3. Application Startup Issues

```bash
# Check application logs
docker-compose -f docker-compose.prod.yml logs app

# Check environment variables
docker-compose -f docker-compose.prod.yml exec app env | grep -E "(DATABASE_URL|REDIS_URL|SECRET_KEY)"

# Debug mode
docker-compose -f docker-compose.prod.yml run --rm app python -m app.main
```

#### 4. Performance Issues

```bash
# Check resource usage
docker stats

# Check database performance
docker-compose -f docker-compose.prod.yml exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# Check slow queries
docker-compose -f docker-compose.prod.yml exec postgres psql -U postgres -c "SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# Security health
curl http://localhost:8000/security/health

# Database health
docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U postgres

# Redis health
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping
```

### Performance Tuning

#### Database Optimization

```sql
-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_conversations_user_id ON conversations(user_id);
CREATE INDEX CONCURRENTLY idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX CONCURRENTLY idx_cache_entries_key ON cache_entries(key);
CREATE INDEX CONCURRENTLY idx_cache_entries_expires_at ON cache_entries(expires_at);

-- Update statistics
ANALYZE;

-- Check query performance
EXPLAIN ANALYZE SELECT * FROM conversations WHERE user_id = 'user_id';
```

#### Application Optimization

```bash
# Worker processes
# Adjust number of workers based on CPU cores
# Formula: (2 * CPU cores) + 1

# Memory limits
# Monitor memory usage and adjust limits
docker stats --no-stream

# Connection pooling
# Configure database connection pool size
# Default: 20 connections per worker
```

### Getting Help

1. **Check Logs**: Always check application and service logs first
2. **Health Checks**: Verify all services are healthy
3. **Documentation**: Refer to the complete API documentation at `/docs`
4. **Community**: Join our Discord community for support
5. **Issues**: Report bugs on GitHub Issues

---

## Next Steps

After completing deployment:

1. **Configure Monitoring**: Set up alerting rules and notification channels
2. **Security Hardening**: Review and configure security settings
3. **Performance Tuning**: Optimize based on your specific workload
4. **Backup Strategy**: Implement automated backup testing
5. **Documentation**: Create internal documentation for your team

For additional help or questions, refer to the project's GitHub repository or contact the support team.