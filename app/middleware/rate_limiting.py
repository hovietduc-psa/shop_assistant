"""
API rate limiting and throttling middleware.
"""

import time
import asyncio
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import redis.asyncio as redis
from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger

from app.core.config import settings


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests: int
    window_seconds: int
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst_size: Optional[int] = None
    key_generator: Optional[str] = None


@dataclass
class RateLimitResult:
    """Rate limit check result."""
    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    current_usage: int = 0
    limit: int = 0


class RedisRateLimiter:
    """Redis-based rate limiter implementation."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: Optional[int] = None
    ) -> RateLimitResult:
        """Check if request is allowed based on rate limit configuration."""
        if current_time is None:
            current_time = int(time.time())

        if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._sliding_window_check(key, config, current_time)
        elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._fixed_window_check(key, config, current_time)
        elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            return await self._token_bucket_check(key, config, current_time)
        elif config.strategy == RateLimitStrategy.LEAKY_BUCKET:
            return await self._leaky_bucket_check(key, config, current_time)
        else:
            # Default to sliding window
            return await self._sliding_window_check(key, config, current_time)

    async def _sliding_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Sliding window rate limiting."""
        pipeline = self.redis.pipeline()
        now = current_time
        window_start = now - config.window_seconds

        # Remove old entries
        pipeline.zremrangebyscore(key, 0, window_start)

        # Count current requests
        pipeline.zcard(key)

        # Add current request
        pipeline.zadd(key, {str(now): now})

        # Set expiration
        pipeline.expire(key, config.window_seconds)

        results = await pipeline.execute()

        current_requests = results[1]
        allowed = current_requests < config.requests

        if allowed:
            remaining = config.requests - current_requests - 1
        else:
            remaining = 0

        # Calculate reset time (oldest request timestamp + window)
        oldest_request = await self.redis.zrange(key, 0, 0, withscores=True)
        if oldest_request:
            reset_time = int(oldest_request[0][1]) + config.window_seconds
        else:
            reset_time = now + config.window_seconds

        retry_after = reset_time - now if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, remaining),
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=current_requests,
            limit=config.requests
        )

    async def _fixed_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Fixed window rate limiting."""
        window_key = f"{key}:{current_time // config.window_seconds}"

        pipeline = self.redis.pipeline()
        pipeline.incr(window_key)
        pipeline.expire(window_key, config.window_seconds)

        results = await pipeline.execute()
        current_requests = results[0]

        allowed = current_requests <= config.requests
        remaining = max(0, config.requests - current_requests)
        reset_time = ((current_time // config.window_seconds) + 1) * config.window_seconds
        retry_after = reset_time - current_time if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=current_requests,
            limit=config.requests
        )

    async def _token_bucket_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Token bucket rate limiting."""
        bucket_key = f"bucket:{key}"
        burst_size = config.burst_size or config.requests

        # Get current bucket state
        bucket_data = await self.redis.hmget(bucket_key, "tokens", "last_refill")
        tokens = float(bucket_data[0] or config.requests)
        last_refill = float(bucket_data[1] or current_time)

        # Calculate tokens to add
        time_passed = current_time - last_refill
        tokens_to_add = (time_passed / config.window_seconds) * config.requests
        new_tokens = min(burst_size, tokens + tokens_to_add)

        # Check if request can be processed
        allowed = new_tokens >= 1

        if allowed:
            new_tokens -= 1

        # Update bucket state
        await self.redis.hmset(bucket_key, {
            "tokens": new_tokens,
            "last_refill": current_time
        })
        await self.redis.expire(bucket_key, config.window_seconds * 2)

        remaining = int(new_tokens)
        reset_time = current_time + config.window_seconds
        retry_after = config.window_seconds if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=int(burst_size - new_tokens),
            limit=burst_size
        )

    async def _leaky_bucket_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Leaky bucket rate limiting."""
        bucket_key = f"leaky:{key}"
        burst_size = config.burst_size or config.requests
        leak_rate = config.requests / config.window_seconds

        # Get current bucket state
        bucket_data = await self.redis.hmget(bucket_key, "queue_size", "last_leak")
        queue_size = float(bucket_data[0] or 0)
        last_leak = float(bucket_data[1] or current_time)

        # Calculate leaked requests
        time_passed = current_time - last_leak
        leaked = time_passed * leak_rate
        new_queue_size = max(0, queue_size - leaked)

        # Check if request can be added to queue
        allowed = new_queue_size < burst_size

        if allowed:
            new_queue_size += 1

        # Update bucket state
        await self.redis.hmset(bucket_key, {
            "queue_size": new_queue_size,
            "last_leak": current_time
        })
        await self.redis.expire(bucket_key, config.window_seconds * 2)

        remaining = int(burst_size - new_queue_size)
        reset_time = current_time + int((new_queue_size / leak_rate) if new_queue_size > 0 else 0)
        retry_after = int(new_queue_size / leak_rate) if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=int(new_queue_size),
            limit=burst_size
        )


class InMemoryRateLimiter:
    """In-memory rate limiter for development/testing."""

    def __init__(self):
        self.storage: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: Optional[int] = None
    ) -> RateLimitResult:
        """Check rate limit using in-memory storage."""
        if current_time is None:
            current_time = int(time.time())

        async with self.lock:
            if key not in self.storage:
                self.storage[key] = {
                    "requests": [],
                    "tokens": config.requests,
                    "last_refill": current_time,
                    "queue_size": 0,
                    "last_leak": current_time
                }

            storage = self.storage[key]

            if config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return self._sliding_window_check_memory(key, config, current_time, storage)
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._token_bucket_check_memory(key, config, current_time, storage)
            else:
                # Default to sliding window for in-memory
                return self._sliding_window_check_memory(key, config, current_time, storage)

    def _sliding_window_check_memory(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int,
        storage: Dict[str, Any]
    ) -> RateLimitResult:
        """Sliding window check in memory."""
        window_start = current_time - config.window_seconds

        # Remove old requests
        storage["requests"] = [req_time for req_time in storage["requests"] if req_time > window_start]

        # Add current request
        storage["requests"].append(current_time)

        current_requests = len(storage["requests"])
        allowed = current_requests <= config.requests
        remaining = max(0, config.requests - current_requests)

        # Calculate reset time
        if storage["requests"]:
            reset_time = min(storage["requests"]) + config.window_seconds
        else:
            reset_time = current_time + config.window_seconds

        retry_after = reset_time - current_time if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=current_requests,
            limit=config.requests
        )

    def _token_bucket_check_memory(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int,
        storage: Dict[str, Any]
    ) -> RateLimitResult:
        """Token bucket check in memory."""
        burst_size = config.burst_size or config.requests

        # Calculate tokens to add
        time_passed = current_time - storage["last_refill"]
        tokens_to_add = (time_passed / config.window_seconds) * config.requests
        new_tokens = min(burst_size, storage["tokens"] + tokens_to_add)

        # Check if request can be processed
        allowed = new_tokens >= 1

        if allowed:
            new_tokens -= 1

        # Update storage
        storage["tokens"] = new_tokens
        storage["last_refill"] = current_time

        remaining = int(new_tokens)
        reset_time = current_time + config.window_seconds
        retry_after = config.window_seconds if not allowed else None

        return RateLimitResult(
            allowed=allowed,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            current_usage=int(burst_size - new_tokens),
            limit=burst_size
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app,
        redis_client: Optional[redis.Redis] = None,
        default_config: Optional[RateLimitConfig] = None
    ):
        super().__init__(app)

        if redis_client:
            self.rate_limiter = RedisRateLimiter(redis_client)
        else:
            self.rate_limiter = InMemoryRateLimiter()
            logger.warning("Using in-memory rate limiter. Use Redis for production.")

        self.default_config = default_config or RateLimitConfig(
            requests=100,
            window_seconds=60,
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )

        # Endpoint-specific configurations
        self.endpoint_configs = {
            # Chat endpoints
            r"/api/v1/chat/message": RateLimitConfig(
                requests=30,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),
            r"/api/v1/chat/dialogue/test": RateLimitConfig(
                requests=5,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),

            # NLU endpoints
            r"/api/v1/nlu/.*": RateLimitConfig(
                requests=50,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),

            # Search endpoints - FEATURE DISABLED
            # r"/api/v1/chat/dialogue/search-similar": RateLimitConfig(
            #     requests=20,
            #     window_seconds=60,
            #     strategy=RateLimitStrategy.SLIDING_WINDOW
            # ),

            # Quality assessment
            r"/api/v1/chat/dialogue/quality": RateLimitConfig(
                requests=10,
                window_seconds=60,
                strategy=RateLimitStrategy.SLIDING_WINDOW
            ),
        }

    async def dispatch(self, request: Request, call_next):
        """Process request through rate limiting middleware."""
        try:
            # Get rate limit key
            rate_limit_key = await self._get_rate_limit_key(request)

            # Get configuration for this endpoint
            config = await self._get_config_for_endpoint(request)

            # Check rate limit
            result = await self.rate_limiter.check_rate_limit(rate_limit_key, config)

            # Add rate limit headers
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(result.limit)
            response.headers["X-RateLimit-Remaining"] = str(result.remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset_time)
            response.headers["X-RateLimit-Used"] = str(result.current_usage)

            if not result.allowed:
                logger.warning(f"Rate limit exceeded for key: {rate_limit_key}")

                # Return 429 Too Many Requests
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": result.retry_after,
                        "limit": result.limit,
                        "window_seconds": config.window_seconds
                    },
                    headers={
                        "Retry-After": str(result.retry_after or config.window_seconds),
                        "X-RateLimit-Limit": str(result.limit),
                        "X-RateLimit-Remaining": str(result.remaining),
                        "X-RateLimit-Reset": str(result.reset_time),
                        "X-RateLimit-Used": str(result.current_usage)
                    }
                )

            return response

        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # Fail open - allow request if rate limiting fails
            return await call_next(request)

    async def _get_rate_limit_key(self, request: Request) -> str:
        """Generate rate limit key for request."""
        # Try to get user ID from request (if authenticated)
        user_id = getattr(request.state, "user_id", None)

        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        client_ip = request.client.host
        forwarded_for = request.headers.get("X-Forwarded-For")

        if forwarded_for:
            # Get the original client IP from the forwarded header
            client_ip = forwarded_for.split(",")[0].strip()

        return f"ip:{client_ip}"

    async def _get_config_for_endpoint(self, request: Request) -> RateLimitConfig:
        """Get rate limit configuration for specific endpoint."""
        import re

        path = request.url.path

        # Check for matching endpoint patterns
        for pattern, config in self.endpoint_configs.items():
            if re.match(pattern, path):
                return config

        # Use default configuration
        return self.default_config


class RateLimitService:
    """Service for managing rate limits programmatically."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        if redis_client:
            self.rate_limiter = RedisRateLimiter(redis_client)
        else:
            self.rate_limiter = InMemoryRateLimiter()

    async def check_custom_rate_limit(
        self,
        key: str,
        requests: int,
        window_seconds: int,
        strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    ) -> RateLimitResult:
        """Check custom rate limit."""
        config = RateLimitConfig(
            requests=requests,
            window_seconds=window_seconds,
            strategy=strategy
        )

        return await self.rate_limiter.check_rate_limit(key, config)

    async def reset_rate_limit(self, key: str) -> bool:
        """Reset rate limit for a specific key."""
        try:
            if hasattr(self.rate_limiter, 'redis'):
                # Redis implementation
                await self.rate_limiter.redis.delete(key)
                return True
            else:
                # In-memory implementation
                async with self.rate_limiter.lock:
                    if key in self.rate_limiter.storage:
                        del self.rate_limiter.storage[key]
                    return True
        except Exception as e:
            logger.error(f"Failed to reset rate limit for key {key}: {e}")
            return False

    async def get_rate_limit_status(self, key: str, config: RateLimitConfig) -> Dict[str, Any]:
        """Get current rate limit status without consuming a request."""
        result = await self.rate_limiter.check_rate_limit(key, config)

        return {
            "key": key,
            "limit": result.limit,
            "remaining": result.remaining,
            "used": result.current_usage,
            "reset_time": result.reset_time,
            "allowed": result.allowed
        }


# Dependency injection for FastAPI
async def get_rate_limit_service(
    redis_client: redis.Redis = Depends(get_redis_client)
) -> RateLimitService:
    """Get rate limit service instance."""
    return RateLimitService(redis_client)