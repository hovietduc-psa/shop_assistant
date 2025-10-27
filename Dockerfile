# Multi-stage Dockerfile for Shop Assistant AI with LangGraph Phase 4
# Optimized for production with enterprise security features

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    USE_LANGGRAPH=true \
    REDIS_URL=redis://redis:6379/0 \
    DATABASE_URL=postgresql://postgres:password@postgres:5432/shop_assistant

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements-docker.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements-docker.txt

# Development stage
FROM base as development

# Install development dependencies
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt

# Copy source code
COPY . .

# Set permissions
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base as production

# Copy source code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY run.py ./

# Install application
RUN pip install -e .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/uploads /app/security && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Testing stage
FROM development as testing

# Run tests
RUN python -m pytest --cov=app --cov-report=html --cov-report=term-missing

# Security scanning stage
FROM base as security

# Install security tools
RUN pip install bandit safety

# Copy source code
COPY . .

# Run security checks
RUN bandit -r app/ -f json -o security-report.json && \
    safety check --json --output safety-report.json

# Final production stage with security
FROM production

# Default to production stage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]