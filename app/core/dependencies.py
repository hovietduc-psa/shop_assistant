"""
FastAPI dependency functions.
"""

from typing import AsyncGenerator, Optional
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status
from app.db.session import get_db
from app.models.user import User

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import ShopifyConfig
from app.core.config import settings


async def get_shopify_service() -> AsyncGenerator[ShopifyService, None]:
    """
    Dependency to get Shopify service instance.

    Provides a configured ShopifyService for API endpoints.
    Handles proper lifecycle management with async context manager.
    """
    config = ShopifyConfig(
        shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
        access_token=settings.SHOPIFY_ACCESS_TOKEN,
        api_version=settings.SHOPIFY_API_VERSION,
        webhook_secret=settings.SHOPIFY_WEBHOOK_SECRET,
        app_secret=settings.SHOPIFY_APP_SECRET
    )

    async with ShopifyService(config) as shopify:
        yield shopify


async def get_shopify_config() -> ShopifyConfig:
    """
    Dependency to get Shopify configuration.

    Returns the current Shopify configuration from settings.
    """
    return ShopifyConfig(
        shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
        access_token=settings.SHOPIFY_ACCESS_TOKEN,
        api_version=settings.SHOPIFY_API_VERSION,
        webhook_secret=settings.SHOPIFY_WEBHOOK_SECRET,
        app_secret=settings.SHOPIFY_APP_SECRET
    )


def get_database_session(db: Session = Depends(get_db)) -> Session:
    """
    Dependency to get database session.

    This is a simple wrapper around get_db for consistency.
    """
    return db


async def get_current_user(
    db: Session = Depends(get_db)
) -> User:
    """
    Mock dependency to get current authenticated user.

    In a development environment, this returns a mock user.
    In production, this would validate tokens and return the actual user.
    """
    # For development purposes, return a mock user
    # In production, this would validate JWT tokens, sessions, etc.

    # Create a mock user object (not persisted to database)
    mock_user = User(
        id="dev-user-id",
        username="dev_user",
        email="dev@example.com",
        full_name="Development User",
        is_active=True,
        is_verified=True,
        is_superuser=True,
        roles=["admin", "user"]
    )

    # Set mock attributes that wouldn't be in the constructor
    mock_user.hashed_password = "mock_hash"
    mock_user.created_at = None  # Will be set by database
    mock_user.updated_at = None  # Will be set by database
    mock_user.last_login = None
    mock_user.profile_data = {}
    mock_user.preferences = {}
    mock_user.api_keys = []
    mock_user.metadata = {}

    return mock_user


def get_current_user_optional(
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional dependency to get current user.

    Returns None if no user is authenticated, useful for optional features.
    """
    # For now, always return the mock user
    # In production, this would check for authentication and return None if not authenticated
    return get_current_user(db)


# Additional dependency functions can be added here as needed