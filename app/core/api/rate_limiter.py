"""
Advanced rate limiting with tiers and quota management.
"""

import time
import asyncio
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

import redis.asyncio as redis
from fastapi import Request, HTTPException, status
from loguru import logger

from app.core.config import settings


class RateLimitTier(Enum):
    """Rate limit tiers."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    UNLIMITED = "unlimited"


class RateLimitPeriod(Enum):
    """Rate limit periods."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    tier: RateLimitTier
    requests: int
    period: RateLimitPeriod
    burst_limit: int = 0
    concurrent_requests: int = 0
    features: List[str] = field(default_factory=list)
    priority: int = 0

    def get_period_seconds(self) -> int:
        """Get period in seconds."""
        multipliers = {
            RateLimitPeriod.SECOND: 1,
            RateLimitPeriod.MINUTE: 60,
            RateLimitPeriod.HOUR: 3600,
            RateLimitPeriod.DAY: 86400,
            RateLimitPeriod.WEEK: 604800,
            RateLimitPeriod.MONTH: 2592000,  # 30 days
        }
        return multipliers.get(self.period, 60)


@dataclass
class ClientQuota:
    """Client quota information."""
    client_id: str
    tier: RateLimitTier
    monthly_requests: int = 0
    monthly_limit: int = 0
    reset_date: datetime = field(default_factory=lambda: datetime.utcnow().replace(day=1))
    features: List[str] = field(default_factory=list)
    custom_limits: Dict[str, RateLimitRule] = field(default_factory=dict)


class AdvancedRateLimiter:
    """Advanced rate limiter with Redis backend."""

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize the rate limiter."""
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict] = {}  # Fallback local cache
        self.tier_rules = self._initialize_tier_rules()
        self.client_quotas: Dict[str, ClientQuota] = {}
        self.concurrent_requests: Dict[str, int] = {}

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            logger.info("Rate limiter connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for rate limiting: {e}")
            self.redis_client = None

    def _initialize_tier_rules(self) -> Dict[RateLimitTier, List[RateLimitRule]]:
        """Initialize default tier rules."""
        return {
            RateLimitTier.FREE: [
                RateLimitRule(RateLimitTier.FREE, 100, RateLimitPeriod.MINUTE, burst_limit=20),
                RateLimitRule(RateLimitTier.FREE, 1000, RateLimitPeriod.HOUR),
                RateLimitRule(RateLimitTier.FREE, 10000, RateLimitPeriod.DAY),
            ],
            RateLimitTier.BASIC: [
                RateLimitRule(RateLimitTier.BASIC, 300, RateLimitPeriod.MINUTE, burst_limit=50),
                RateLimitRule(RateLimitTier.BASIC, 5000, RateLimitPeriod.HOUR),
                RateLimitRule(RateLimitTier.BASIC, 50000, RateLimitPeriod.DAY),
            ],
            RateLimitTier.PROFESSIONAL: [
                RateLimitRule(RateLimitTier.PROFESSIONAL, 1000, RateLimitPeriod.MINUTE, burst_limit=100),
                RateLimitRule(RateLimitTier.PROFESSIONAL, 20000, RateLimitPeriod.HOUR),
                RateLimitRule(RateLimitTier.PROFESSIONAL, 200000, RateLimitPeriod.DAY),
            ],
            RateLimitTier.ENTERPRISE: [
                RateLimitRule(RateLimitTier.ENTERPRISE, 5000, RateLimitPeriod.MINUTE, burst_limit=500),
                RateLimitRule(RateLimitTier.ENTERPRISE, 100000, RateLimitPeriod.HOUR),
                RateLimitRule(RateLimitTier.ENTERPRISE, 1000000, RateLimitPeriod.DAY),
            ],
            RateLimitTier.UNLIMITED: [],  # No limits
        }

    async def is_allowed(self,
                        request: Request,
                        client_id: str,
                        tier: Optional[RateLimitTier] = None,
                        custom_rules: Optional[List[RateLimitRule]] = None) -> Tuple[bool, Dict[str, any]]:
        """
        Check if request is allowed based on rate limits.

        Args:
            request: FastAPI request object
            client_id: Client identifier
            tier: Rate limit tier
            custom_rules: Custom rate limit rules

        Returns:
            Tuple of (allowed, limit_info)
        """
        if not tier:
            tier = RateLimitTier.FREE  # Default tier

        # Get rules for this tier
        rules = custom_rules or self.tier_rules.get(tier, [])

        # Check each rule
        for rule in rules:
            allowed, info = await self._check_rule(request, client_id, rule)
            if not allowed:
                return False, info

        # Check concurrent request limit
        if rule.concurrent_requests > 0:
            concurrent_count = self.concurrent_requests.get(client_id, 0)
            if concurrent_count >= rule.concurrent_requests:
                return False, {
                    "limit": rule.concurrent_requests,
                    "remaining": 0,
                    "reset_time": int(time.time()) + 60,
                    "retry_after": 60,
                    "error": "Concurrent request limit exceeded"
                }

        return True, {
            "tier": tier.value,
            "limits": [{"requests": r.requests, "period": r.period.value} for r in rules]
        }

    async def _check_rule(self,
                         request: Request,
                         client_id: str,
                         rule: RateLimitRule) -> Tuple[bool, Dict[str, any]]:
        """Check a specific rate limit rule."""
        current_time = int(time.time())
        period_seconds = rule.get_period_seconds()
        window_start = current_time - (current_time % period_seconds)

        # Create Redis key
        key = f"rate_limit:{client_id}:{rule.tier.value}:{rule.period.value}:{window_start}"

        try:
            if self.redis_client:
                return await self._check_redis_rule(key, rule, current_time)
            else:
                return await self._check_local_rule(key, rule, current_time)
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiting fails
            return True, {}

    async def _check_redis_rule(self,
                               key: str,
                               rule: RateLimitRule,
                               current_time: int) -> Tuple[bool, Dict[str, any]]:
        """Check rate limit using Redis."""
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, rule.get_period_seconds())
        results = await pipe.execute()

        current_count = results[0]

        if current_count > rule.requests:
            # Calculate reset time
            period_seconds = rule.get_period_seconds()
            reset_time = current_time + (period_seconds - (current_time % period_seconds))

            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "current": current_count,
                "reset_time": reset_time,
                "retry_after": reset_time - current_time,
                "error": "Rate limit exceeded"
            }

        return True, {
            "limit": rule.requests,
            "remaining": rule.requests - current_count,
            "current": current_count,
            "reset_time": current_time + rule.get_period_seconds()
        }

    async def _check_local_rule(self,
                               key: str,
                               rule: RateLimitRule,
                               current_time: int) -> Tuple[bool, Dict[str, any]]:
        """Check rate limit using local cache (fallback)."""
        # Clean up old entries
        cutoff_time = current_time - rule.get_period_seconds()
        self._cleanup_local_cache(cutoff_time)

        # Get or create entry
        if key not in self.local_cache:
            self.local_cache[key] = {
                "count": 0,
                "reset_time": current_time + rule.get_period_seconds()
            }

        entry = self.local_cache[key]
        entry["count"] += 1

        if entry["count"] > rule.requests:
            return False, {
                "limit": rule.requests,
                "remaining": 0,
                "current": entry["count"],
                "reset_time": entry["reset_time"],
                "retry_after": max(0, entry["reset_time"] - current_time),
                "error": "Rate limit exceeded"
            }

        return True, {
            "limit": rule.requests,
            "remaining": rule.requests - entry["count"],
            "current": entry["count"],
            "reset_time": entry["reset_time"]
        }

    def _cleanup_local_cache(self, cutoff_time: int):
        """Clean up old local cache entries."""
        to_remove = []
        for key, entry in self.local_cache.items():
            if entry.get("reset_time", 0) < cutoff_time:
                to_remove.append(key)

        for key in to_remove:
            del self.local_cache[key]

    async def get_client_stats(self, client_id: str) -> Dict[str, any]:
        """Get rate limiting statistics for a client."""
        stats = {
            "client_id": client_id,
            "tier": RateLimitTier.FREE.value,
            "current_usage": {},
            "limits": {},
            "monthly_usage": 0,
            "monthly_limit": 0
        }

        # Get client quota if available
        quota = self.client_quotas.get(client_id)
        if quota:
            stats["tier"] = quota.tier.value
            stats["monthly_usage"] = quota.monthly_requests
            stats["monthly_limit"] = quota.monthly_limit

        # Get current usage for each period
        current_time = int(time.time())
        for period in RateLimitPeriod:
            period_seconds = {
                RateLimitPeriod.SECOND: 1,
                RateLimitPeriod.MINUTE: 60,
                RateLimitPeriod.HOUR: 3600,
                RateLimitPeriod.DAY: 86400,
            }.get(period)

            if period_seconds:
                window_start = current_time - (current_time % period_seconds)
                key = f"rate_limit:{client_id}:*:{period.value}:{window_start}"

                try:
                    if self.redis_client:
                        # Get all keys for this period
                        pattern = f"rate_limit:{client_id}:*:{period.value}:*"
                        keys = await self.redis_client.keys(pattern)
                        total = 0
                        if keys:
                            values = await self.redis_client.mget(keys)
                            total = sum(int(v or 0) for v in values)
                        stats["current_usage"][period.value] = total
                    else:
                        # Local cache fallback
                        total = 0
                        for key, entry in self.local_cache.items():
                            if f":{period.value}:" in key and entry.get("reset_time", 0) > current_time:
                                total += entry.get("count", 0)
                        stats["current_usage"][period.value] = total

                except Exception as e:
                    logger.error(f"Error getting client stats: {e}")
                    stats["current_usage"][period.value] = 0

        return stats

    async def set_client_quota(self, client_id: str, quota: ClientQuota):
        """Set quota for a specific client."""
        self.client_quotas[client_id] = quota

        # Store in Redis for persistence
        if self.redis_client:
            quota_key = f"client_quota:{client_id}"
            quota_data = {
                "tier": quota.tier.value,
                "monthly_limit": quota.monthly_limit,
                "features": quota.features,
                "reset_date": quota.reset_date.isoformat()
            }
            await self.redis_client.hset(quota_key, mapping=quota_data)
            await self.redis_client.expire(quota_key, 86400 * 30)  # 30 days

    async def add_custom_rule(self, client_id: str, rule: RateLimitRule):
        """Add custom rate limit rule for a client."""
        if client_id not in self.client_quotas:
            self.client_quotas[client_id] = ClientQuota(
                client_id=client_id,
                tier=rule.tier
            )

        self.client_quotas[client_id].custom_limits[rule.tier.value] = rule

    def increment_concurrent(self, client_id: str):
        """Increment concurrent request count."""
        current = self.concurrent_requests.get(client_id, 0)
        self.concurrent_requests[client_id] = current + 1

    def decrement_concurrent(self, client_id: str):
        """Decrement concurrent request count."""
        current = self.concurrent_requests.get(client_id, 0)
        if current > 0:
            self.concurrent_requests[client_id] = current - 1

    async def reset_limits(self, client_id: str):
        """Reset rate limits for a client."""
        # Delete Redis keys
        if self.redis_client:
            pattern = f"rate_limit:{client_id}:*"
            keys = await self.redis_client.keys(pattern)
            if keys:
                await self.redis_client.delete(*keys)

        # Clear local cache
        keys_to_remove = [key for key in self.local_cache.keys() if key.startswith(f"rate_limit:{client_id}:")]
        for key in keys_to_remove:
            del self.local_cache[key]

    async def get_global_stats(self) -> Dict[str, any]:
        """Get global rate limiting statistics."""
        stats = {
            "active_clients": len(self.concurrent_requests),
            "total_quotas": len(self.client_quotas),
            "redis_connected": self.redis_client is not None,
            "tier_distribution": {},
            "concurrent_requests": dict(self.concurrent_requests)
        }

        # Count clients by tier
        for quota in self.client_quotas.values():
            tier = quota.tier.value
            stats["tier_distribution"][tier] = stats["tier_distribution"].get(tier, 0) + 1

        return stats


# Global rate limiter instance
rate_limiter = AdvancedRateLimiter()


async def get_rate_limiter() -> AdvancedRateLimiter:
    """Get the global rate limiter instance."""
    if not rate_limiter.redis_client:
        await rate_limiter.initialize()
    return rate_limiter


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    def __init__(self, app, rate_limiter: AdvancedRateLimiter):
        """Initialize the middleware."""
        self.app = app
        self.rate_limiter = rate_limiter

    async def __call__(self, scope, receive, send):
        """ASGI callable."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract client ID from request
        client_id = self._extract_client_id(scope)

        # Get client tier (could be from JWT, API key, etc.)
        tier = self._get_client_tier(scope, client_id)

        # Create mock request for rate limiting
        request = type('MockRequest', (), {
            'method': scope.get('method'),
            'url': {'path': scope.get('path', '')},
            'headers': dict(scope.get('headers', []))
        })()

        # Check rate limits
        allowed, limit_info = await self.rate_limiter.is_allowed(
            request, client_id, tier
        )

        if not allowed:
            # Send rate limit exceeded response
            response = {
                'status': status.HTTP_429_TOO_MANY_REQUESTS,
                'headers': [
                    (b'content-type', b'application/json'),
                    (b'x-ratelimit-limit', str(limit_info.get('limit', 0)).encode()),
                    (b'x-ratelimit-remaining', str(limit_info.get('remaining', 0)).encode()),
                    (b'x-ratelimit-reset', str(limit_info.get('reset_time', 0)).encode()),
                    (b'retry-after', str(limit_info.get('retry_after', 60)).encode()),
                ]
            }

            # Send response
            await send({
                'type': 'http.response.start',
                **response
            })
            await send({
                'type': 'http.response.body',
                'body': json.dumps({
                    'error': 'Rate limit exceeded',
                    'details': limit_info
                }).encode()
            })
            return

        # Track concurrent requests
        self.rate_limiter.increment_concurrent(client_id)

        try:
            # Process request
            await self.app(scope, receive, send)
        finally:
            # Clean up concurrent request tracking
            self.rate_limiter.decrement_concurrent(client_id)

    def _extract_client_id(self, scope) -> str:
        """Extract client ID from request scope."""
        # This could be from API key, JWT, IP address, etc.
        headers = dict(scope.get('headers', []))

        # Try API key
        api_key = headers.get(b'x-api-key', b'').decode()
        if api_key:
            return f"api_key:{api_key}"

        # Try Authorization header
        auth = headers.get(b'authorization', b'').decode()
        if auth and auth.startswith('Bearer '):
            return f"jwt:{auth[7:20]}..."  # First few chars of JWT

        # Fall back to client IP
        client = scope.get('client')
        if client:
            return f"ip:{client[0]}"

        return "unknown"

    def _get_client_tier(self, scope, client_id: str) -> RateLimitTier:
        """Get rate limit tier for client."""
        # This would typically look up from database or configuration
        # For now, return default tier
        return RateLimitTier.FREE