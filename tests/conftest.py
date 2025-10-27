"""
Pytest configuration and shared fixtures for Shop Assistant AI testing.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator, Dict, Any
from datetime import datetime
import json
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.core.database.base import Base
from app.models.user import User
from app.core.auth import get_current_user
from app.core.llm.llm_manager import LLMManager
from app.core.llm.prompt_templates import PromptManager


# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)

TestSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_setup():
    """Set up test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_db_setup) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def test_client(db_session) -> Generator[TestClient, None, None]:
    """Create a test client with database dependency override."""
    def override_get_db():
        return db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
async def mock_llm_manager() -> AsyncMock:
    """Create a mock LLM manager for testing."""
    mock = AsyncMock(spec=LLMManager)

    # Mock common LLM responses
    mock.generate_response.return_value = {
        "content": "This is a mock LLM response for testing purposes.",
        "model": "gpt-4",
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}
    }

    mock.generate_embedding.return_value = [0.1] * 1536  # Mock embedding vector

    return mock


@pytest.fixture
async def mock_prompt_manager() -> MagicMock:
    """Create a mock prompt manager for testing."""
    mock = MagicMock(spec=PromptManager)
    mock.get_prompt.return_value = "This is a mock prompt for testing."
    return mock


@pytest.fixture
async def test_user() -> Dict[str, Any]:
    """Create a test user."""
    return {
        "id": "test_user_123",
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
        "created_at": datetime.utcnow()
    }


@pytest.fixture
async def authenticated_user(test_user) -> Dict[str, Any]:
    """Create an authenticated user for testing."""
    return test_user


@pytest.fixture
def mock_current_user(authenticated_user):
    """Mock the current user dependency."""
    def override_get_current_user():
        return authenticated_user

    return override_get_current_user


@pytest.fixture
async def test_agent() -> Dict[str, Any]:
    """Create a test agent."""
    return {
        "id": "agent_001",
        "name": "Test Agent",
        "email": "agent@example.com",
        "status": "online",
        "skills": ["customer_service", "technical_support"],
        "max_concurrent_conversations": 5,
        "average_rating": 4.5,
        "created_at": datetime.utcnow()
    }


@pytest.fixture
async def test_conversation() -> Dict[str, Any]:
    """Create a test conversation."""
    return {
        "id": "conv_001",
        "customer_id": "cust_001",
        "agent_id": "agent_001",
        "status": "active",
        "messages": [
            {
                "id": "msg_001",
                "role": "customer",
                "content": "Hello, I need help with my order",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            },
            {
                "id": "msg_002",
                "role": "agent",
                "content": "I'd be happy to help you with your order. Can you provide your order number?",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            }
        ],
        "metadata": {
            "source": "web_chat",
            "customer_tier": "premium",
            "language": "en"
        },
        "created_at": datetime.utcnow()
    }


@pytest.fixture
async def test_product_data() -> Dict[str, Any]:
    """Create test product data."""
    return {
        "id": "prod_001",
        "title": "Test Product",
        "description": "This is a test product for testing purposes",
        "price": {
            "amount": 29.99,
            "currency_code": "USD"
        },
        "inventory": {
            "available": 100,
            "locations": [
                {"location_id": "loc_001", "available": 50},
                {"location_id": "loc_002", "available": 50}
            ]
        },
        "variants": [
            {
                "id": "var_001",
                "title": "Test Variant",
                "price": {"amount": 29.99, "currency_code": "USD"},
                "sku": "TEST-001"
            }
        ],
        "images": [
            {
                "url": "https://example.com/image.jpg",
                "alt_text": "Test product image"
            }
        ],
        "tags": ["test", "sample"],
        "created_at": datetime.utcnow()
    }


@pytest.fixture
async def test_shopify_response() -> Dict[str, Any]:
    """Create a mock Shopify API response."""
    return {
        "data": {
            "products": {
                "edges": [
                    {
                        "node": {
                            "id": "gid://shopify/Product/1",
                            "title": "Test Product",
                            "description": "Test description",
                            "priceRangeV2": {
                                "minVariantPrice": {
                                    "amount": "29.99",
                                    "currencyCode": "USD"
                                }
                            }
                        }
                    }
                ]
            }
        },
        "extensions": {
            "cost": {
                "requestedQueryCost": 10,
                "actualQueryCost": 8
            }
        }
    }


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.delete.return_value = 1
    mock.exists.return_value = False
    mock.expire.return_value = True
    return mock


@pytest.fixture
def sample_llm_response() -> Dict[str, Any]:
    """Sample LLM response for testing."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test response from the LLM."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "total_tokens": 25
        }
    }


@pytest.fixture
def sample_embedding_response() -> Dict[str, Any]:
    """Sample embedding response for testing."""
    return {
        "object": "list",
        "data": [
            {
                "object": "embedding",
                "embedding": [0.1] * 1536,  # Mock embedding vector
                "index": 0
            }
        ],
        "model": "text-embedding-ada-002",
        "usage": {
            "prompt_tokens": 8,
            "total_tokens": 8
        }
    }


@pytest.fixture
def error_responses():
    """Sample error responses for testing."""
    return {
        "rate_limit_error": {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded"
            }
        },
        "authentication_error": {
            "error": {
                "message": "Invalid authentication credentials",
                "type": "authentication_error",
                "code": "invalid_api_key"
            }
        },
        "api_error": {
            "error": {
                "message": "An error occurred",
                "type": "api_error",
                "code": "api_error"
            }
        }
    }


@pytest.fixture
def test_data_dir():
    """Return the path to the test data directory."""
    import os
    return os.path.join(os.path.dirname(__file__), "data")


# Custom pytest markers
pytest_plugins = []

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "security: mark test as a security test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "external: mark test as requiring external services"
    )