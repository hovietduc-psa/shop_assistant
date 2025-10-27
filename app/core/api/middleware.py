"""
Advanced API middleware for enhanced functionality.
"""

import time
import uuid
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger

from app.core.config import settings


class MiddlewareType(Enum):
    """Types of middleware."""
    CORS = "cors"
    AUTHENTICATION = "authentication"
    RATE_LIMITING = "rate_limiting"
    LOGGING = "logging"
    SECURITY = "security"
    CACHE = "cache"
    VERSIONING = "versioning"
    REQUEST_TRACKING = "request_tracking"


@dataclass
class MiddlewareConfig:
    """Configuration for middleware."""
    enabled: bool = True
    priority: int = 100
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


class AdvancedCORSMiddleware(BaseHTTPMiddleware):
    """Advanced CORS middleware with dynamic configuration."""

    def __init__(self, app, config: MiddlewareConfig = None):
        super().__init__(app)
        self.config = config or MiddlewareConfig()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle CORS with dynamic configuration."""
        response = await call_next(request)

        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"

        return response


class APIVersionMiddleware(BaseHTTPMiddleware):
    """API versioning middleware."""

    def __init__(self, app, default_version: str = "v1"):
        super().__init__(app)
        self.default_version = default_version

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle API versioning."""
        # Add version header
        response = await call_next(request)
        response.headers["API-Version"] = self.default_version
        return response


class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Request tracking middleware for analytics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track requests for analytics."""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Add request ID to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add tracking headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = str(time.time() - start_time)

        return response


class UsageLimitMiddleware(BaseHTTPMiddleware):
    """Usage limiting middleware for API quotas."""

    def __init__(self, app, daily_limit: int = 10000):
        super().__init__(app)
        self.daily_limit = daily_limit
        self.usage_tracker = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Enforce usage limits."""
        client_ip = request.client.host
        today = datetime.now().strftime("%Y-%m-%d")

        # Check usage
        key = f"{client_ip}:{today}"
        current_usage = self.usage_tracker.get(key, 0)

        if current_usage >= self.daily_limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Daily usage limit exceeded",
                    "limit": self.daily_limit,
                    "reset_time": "tomorrow"
                }
            )

        # Process request
        response = await call_next(request)

        # Update usage
        self.usage_tracker[key] = current_usage + 1
        response.headers["X-Usage-Count"] = str(current_usage + 1)
        response.headers["X-Usage-Limit"] = str(self.daily_limit)

        return response


class MiddlewareManager:
    """Manager for API middleware."""

    def __init__(self):
        self.middleware_configs = {}
        self.middleware_instances = {}

    def register_middleware(self, name: str, middleware_class: type, config: MiddlewareConfig = None):
        """Register a middleware."""
        self.middleware_configs[name] = {
            "class": middleware_class,
            "config": config or MiddlewareConfig()
        }

    def get_middleware_stack(self, app) -> List[BaseHTTPMiddleware]:
        """Get ordered middleware stack."""
        # Sort by priority
        sorted_configs = sorted(
            self.middleware_configs.items(),
            key=lambda x: x[1]["config"].priority
        )

        middleware_stack = []
        for name, config in sorted_configs:
            if config["config"].enabled:
                try:
                    instance = config["class"](app, config["config"])
                    middleware_stack.append(instance)
                    self.middleware_instances[name] = instance
                except Exception as e:
                    logger.error(f"Failed to initialize middleware {name}: {e}")

        return middleware_stack

    def get_middleware_stats(self) -> Dict[str, Any]:
        """Get middleware statistics."""
        return {
            "registered_middleware": list(self.middleware_configs.keys()),
            "active_middleware": list(self.middleware_instances.keys()),
            "total_registered": len(self.middleware_configs),
            "total_active": len(self.middleware_instances)
        }


# Global middleware manager
middleware_manager = MiddlewareManager()

# Register default middleware
middleware_manager.register_middleware(
    "cors",
    AdvancedCORSMiddleware,
    MiddlewareConfig(priority=100, enabled=True)
)

middleware_manager.register_middleware(
    "versioning",
    APIVersionMiddleware,
    MiddlewareConfig(priority=200, enabled=True)
)

middleware_manager.register_middleware(
    "request_tracking",
    RequestTrackingMiddleware,
    MiddlewareConfig(priority=300, enabled=True)
)

middleware_manager.register_middleware(
    "usage_limit",
    UsageLimitMiddleware,
    MiddlewareConfig(priority=400, enabled=True, config={"daily_limit": 10000})
)


def get_middleware_manager() -> MiddlewareManager:
    """Get the global middleware manager."""
    return middleware_manager