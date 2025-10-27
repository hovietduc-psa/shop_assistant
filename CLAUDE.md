# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Shop Assistant AI is an AI-powered sales and consulting agent built with FastAPI. It provides 24/7 customer support through natural conversations, integrates with e-commerce platforms (Shopify), and includes advanced AI capabilities using OpenRouter and Cohere for LLM and embedding services.

## Development Commands

### Docker Development (Recommended)
```bash
# Start development environment with hot reload
docker-compose -f docker-compose.dev.yml up -d

# Start with additional tools (pgAdmin, Redis Commander)
docker-compose -f docker-compose.dev.yml --profile tools up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f app

# Stop environment
docker-compose -f docker-compose.dev.yml down
```

### Local Development
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows: venv\Scripts\activate
# On Unix: source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Start databases (if not using Docker for full stack)
docker-compose up db redis -d

# Run database migrations
alembic upgrade head

# Start development server
python run.py
# OR
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m "not slow"    # Skip slow tests
pytest -m e2e          # End-to-end tests

# Run single test file
pytest app/tests/test_main.py

# Run with verbose output
pytest -v -s
```

### Code Quality
```bash
# Format code
black app/
isort app/

# Lint code
flake8 app/
mypy app/

# Security check
bandit -r app/

# Run pre-commit hooks manually
pre-commit run --all-files
```

### Database Management
```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Downgrade migration
alembic downgrade -1

# View migration history
alembic history

# View current revision
alembic current
```

## Architecture Overview

### Core Application Structure
- **`app/main.py`**: FastAPI application entry point with middleware, exception handlers, and router configuration
- **`app/core/config.py`**: Centralized configuration using Pydantic settings with environment variable support
- **`app/api/v1/router.py`**: Main API router aggregating all endpoint routers
- **`app/db/`**: Database configuration and session management using SQLAlchemy with async support
- **`app/models/`**: SQLAlchemy ORM models for database entities
- **`app/schemas/`**: Pydantic schemas for request/response validation and serialization

### Service Layer Architecture
- **`app/services/llm.py`**: LLM integration service using OpenRouter API for multiple model access
- **`app/services/embedding.py`**: Embedding generation using Cohere API for semantic search
- **`app/services/nlu.py`**: Natural language understanding for intent classification and entity extraction
- **`app/services/dialogue.py`**: Conversation management and context handling
- **`app/services/memory.py`**: Conversation memory and session management
- **`app/services/quality.py`**: Response quality assessment and metrics

### Integration Layer
- **`app/integrations/shopify/`**: Complete Shopify integration with GraphQL and REST API support
  - `client.py`: Shopify API client with authentication
  - `service.py`: Business logic for Shopify operations
  - `models.py`: Pydantic models for Shopify data
  - `webhooks.py`: Webhook handling and event processing

### Middleware Stack
- **Security Middleware**: Rate limiting with Redis, request validation, security headers
- **Logging Middleware**: Structured logging with request tracing and correlation IDs
- **Rate Limiting**: Token bucket algorithm with Redis backend
- **Validation**: Request/response validation and sanitization

### Intelligence Layer
- **`app/core/intelligence/`**: AI-powered intelligence features
  - `escalation.py`: Intelligent human agent handoff decisions
  - `quality.py`: Response quality assessment and coaching
  - `sentiment.py`: Sentiment analysis and emotional intelligence
  - `supervisor.py`: AI supervision and oversight capabilities

### API Endpoints Structure
- **Authentication**: `/api/v1/auth/` - JWT-based authentication with refresh tokens
- **Chat**: `/api/v1/chat/` - Real-time conversation management with WebSocket support
- **AI Services**: `/api/v1/ai/` - AI capabilities including intent, entities, and sentiment
- **Shopify**: `/api/v1/products/`, `/api/v1/orders/`, `/api/v1/customers/` - E-commerce integration
- **Monitoring**: `/api/v1/monitoring/` - Health checks, metrics, and analytics
- **Agents**: `/api/v1/agents/` - Agent management and routing system

## Key Technologies and Patterns

### Async/Await Architecture
The application uses async/await throughout for high-performance concurrent request handling. Database operations use asyncpg (PostgreSQL) and async Redis for non-blocking I/O.

### Dependency Injection
FastAPI's dependency injection system is used extensively for database sessions, authentication, and service layer access. Custom dependencies are defined in `app/core/dependencies.py`.

### Configuration Management
Environment-based configuration using Pydantic settings with `.env` file support. All sensitive data (API keys, database URLs) are stored in environment variables.

### Error Handling
Centralized error handling with custom exception classes and structured error responses. Custom exception handlers are registered in `app/utils/error_handlers.py`.

### Testing Strategy
- **Unit tests**: Fast tests for individual functions and classes
- **Integration tests**: Database and external service integration
- **E2E tests**: Full request-response cycle testing
- **Coverage target**: 85% minimum coverage requirement

### Database Design
SQLAlchemy 2.0 with async support, using Alembic for database migrations. The schema supports conversation management, user authentication, and integration data.

### Security Implementation
- JWT authentication with refresh token rotation
- Rate limiting using Redis token bucket algorithm
- Input validation and sanitization
- CORS configuration for cross-origin requests
- Security headers and audit logging

## Development Guidelines

### Code Style
- Python 3.9+ with type hints required
- Black formatter with 88-character line length
- isort for import organization
- flake8 for linting with E203/W503 exceptions
- mypy for static type checking

### Git Workflow
- Feature branches from main/master
- Conventional commit messages
- Pre-commit hooks enforced
- Pull requests required for code review

### Environment Setup
- Development: `docker-compose.dev.yml` with hot reload
- Production: `docker-compose.yml` with optimized builds
- Environment-specific configurations in `.env` files

### API Design
- RESTful principles with OpenAPI 3.0 documentation
- Pydantic schemas for all request/response models
- Consistent error response format
- HTTP status codes following REST conventions

### Monitoring and Observability
- Structured logging with JSON format
- Prometheus metrics for application performance
- Health check endpoints for monitoring systems
- Request tracing with correlation IDs

## Common Development Tasks

### Adding New API Endpoints
1. Create Pydantic schemas in `app/schemas/`
2. Implement business logic in `app/services/`
3. Add endpoint in appropriate `app/api/v1/endpoints/` module
4. Register router in `app/api/v1/router.py`
5. Add tests in `app/tests/`

### Database Schema Changes
1. Modify SQLAlchemy models in `app/models/`
2. Generate migration: `alembic revision --autogenerate`
3. Review generated migration file
4. Apply migration: `alembic upgrade head`

### Adding New Integrations
1. Create client in `app/integrations/{service}/client.py`
2. Add service layer in `app/integrations/{service}/service.py`
3. Create Pydantic models for API responses
4. Add endpoints in `app/api/v1/endpoints/`
5. Configure environment variables in `app/core/config.py`

### Testing New Features
1. Write unit tests for business logic
2. Add integration tests for external services
3. Create E2E tests for API endpoints
4. Ensure coverage meets 85% threshold
5. Run test suite: `pytest --cov=app`