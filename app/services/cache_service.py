"""
Enhanced caching service for performance optimization.
Implements multi-level caching with Redis backend and intelligent cache invalidation.
"""

import json
import hashlib
import asyncio
from typing import Any, Optional, Dict, List, Union, Callable
from datetime import datetime, timedelta
from functools import wraps
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory caching only")

from app.core.config import settings


class CacheService:
    """High-performance caching service with Redis backend and fallback."""

    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}  # Simple in-memory fallback
        self.memory_cache_expiry = {}
        self.default_ttl = 3600  # 1 hour default
        self.max_memory_items = 1000
        self._redis_initialized = False

    async def _init_redis(self):
        """Initialize Redis connection."""
        if REDIS_AVAILABLE and settings.REDIS_URL and not self._redis_initialized:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test connection
                await self.redis_client.ping()
                self._redis_initialized = True
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis cache: {e}")
                self.redis_client = None
                self._redis_initialized = True  # Don't try again
        else:
            logger.warning("Redis not configured, using in-memory cache only")

    async def ensure_redis_initialized(self):
        """Ensure Redis is initialized before use."""
        if not self._redis_initialized:
            await self._init_redis()

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments."""
        key_data = {
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{prefix}:{key_hash}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            await self.ensure_redis_initialized()
            # Try Redis first
            if self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    return json.loads(value)

            # Fallback to memory cache
            if key in self.memory_cache:
                # Check expiry
                if key in self.memory_cache_expiry:
                    if datetime.utcnow() > self.memory_cache_expiry[key]:
                        del self.memory_cache[key]
                        del self.memory_cache_expiry[key]
                        return None
                return self.memory_cache[key]

            return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Set value in cache with optional TTL and tags."""
        try:
            await self.ensure_redis_initialized()
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value, default=str)

            # Set in Redis
            redis_success = False
            if self.redis_client:
                try:
                    await self.redis_client.setex(key, ttl, serialized_value)

                    # Add tags for group invalidation
                    if tags:
                        for tag in tags:
                            tag_key = f"tag:{tag}"
                            await self.redis_client.sadd(tag_key, key)
                            await self.redis_client.expire(tag_key, ttl)

                    redis_success = True
                except Exception as e:
                    logger.error(f"Redis set error: {e}")

            # Fallback to memory cache
            if not redis_success:
                # Clean up old items if cache is full
                if len(self.memory_cache) >= self.max_memory_items:
                    self._cleanup_memory_cache()

                self.memory_cache[key] = value
                self.memory_cache_expiry[key] = datetime.utcnow() + timedelta(seconds=ttl)

            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            # Delete from Redis
            if self.redis_client:
                await self.redis_client.delete(key)

            # Delete from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
            if key in self.memory_cache_expiry:
                del self.memory_cache_expiry[key]

            return True

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cache entries with given tag."""
        try:
            invalidated_count = 0

            if self.redis_client:
                tag_key = f"tag:{tag}"
                keys = await self.redis_client.smembers(tag_key)

                if keys:
                    # Delete all keys with this tag
                    await self.redis_client.delete(*keys)
                    await self.redis_client.delete(tag_key)
                    invalidated_count = len(keys)

            # Invalidate from memory cache (approximate)
            keys_to_delete = []
            for key in self.memory_cache:
                if f"tag:{tag}" in key:  # Simple tag detection for memory cache
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                del self.memory_cache[key]
                if key in self.memory_cache_expiry:
                    del self.memory_cache_expiry[key]
                invalidated_count += 1

            logger.info(f"Invalidated {invalidated_count} cache entries for tag: {tag}")
            return invalidated_count

        except Exception as e:
            logger.error(f"Cache invalidation error for tag {tag}: {e}")
            return 0

    async def clear_all(self) -> bool:
        """Clear all cache entries."""
        try:
            if self.redis_client:
                await self.redis_client.flushdb()

            self.memory_cache.clear()
            self.memory_cache_expiry.clear()

            logger.info("Cache cleared successfully")
            return True

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def _cleanup_memory_cache(self):
        """Clean up expired entries from memory cache."""
        now = datetime.utcnow()
        expired_keys = [
            key for key, expiry in self.memory_cache_expiry.items()
            if now > expiry
        ]

        for key in expired_keys:
            if key in self.memory_cache:
                del self.memory_cache[key]
            del self.memory_cache_expiry[key]

    def cache_result(
        self,
        prefix: str,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        key_generator: Optional[Callable] = None
    ):
        """Decorator to cache function results."""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                if key_generator:
                    cache_key = key_generator(*args, **kwargs)
                else:
                    cache_key = self._generate_key(prefix, *args, **kwargs)

                # Try to get from cache
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result

                # Execute function and cache result
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    await self.set(cache_key, result, ttl, tags)
                    return result

                except Exception as e:
                    logger.error(f"Function execution error in cache decorator: {e}")
                    raise

            return wrapper
        return decorator

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            # Ensure Redis is initialized before checking connection status
            await self.ensure_redis_initialized()

            # Check Redis connection with actual ping test
            redis_connected = False
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    redis_connected = True
                except Exception as e:
                    logger.warning(f"Redis ping failed: {e}")
                    redis_connected = False

            stats = {
                "memory_cache_size": len(self.memory_cache),
                "memory_cache_max_items": self.max_memory_items,
                "redis_connected": redis_connected,
                "redis_initialized": self._redis_initialized
            }

            if self.redis_client and redis_connected:
                try:
                    info = await self.redis_client.info()
                    stats.update({
                        "redis_used_memory": info.get("used_memory_human", "N/A"),
                        "redis_connected_clients": info.get("connected_clients", 0),
                        "redis_total_commands_processed": info.get("total_commands_processed", 0),
                        "redis_keyspace_hits": info.get("keyspace_hits", 0),
                        "redis_keyspace_misses": info.get("keyspace_misses", 0)
                    })
                except Exception as e:
                    logger.error(f"Error getting Redis stats: {e}")

            return stats

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# Global cache service instance
cache_service = CacheService()


# Predefined cache keys and TTL values
class CacheKeys:
    """Standardized cache keys."""

    # Product cache
    PRODUCT_SEARCH = "product_search"
    PRODUCT_DETAILS = "product_details"
    PRODUCT_CATEGORIES = "product_categories"

    # Order cache
    ORDER_STATUS = "order_status"
    ORDER_HISTORY = "order_history"

    # Policy cache
    POLICY_CONTENT = "policy_content"
    FAQ_CONTENT = "faq_content"

    # Store cache
    STORE_INFO = "store_info"
    CONTACT_INFO = "contact_info"

    # Analytics cache
    ANALYTICS_SUMMARY = "analytics_summary"
    CONVERSATION_METRICS = "conversation_metrics"


class CacheTTL:
    """Cache TTL values in seconds."""

    VERY_SHORT = 60      # 1 minute
    SHORT = 300          # 5 minutes
    MEDIUM = 1800        # 30 minutes
    LONG = 3600          # 1 hour
    VERY_LONG = 86400    # 24 hours


# Cache decorators for common use cases
def cache_product_search(ttl: int = CacheTTL.MEDIUM):
    """Cache product search results."""
    return cache_service.cache_result(
        prefix=CacheKeys.PRODUCT_SEARCH,
        ttl=ttl,
        tags=["products", "search"]
    )


def cache_product_details(ttl: int = CacheTTL.LONG):
    """Cache product details."""
    return cache_service.cache_result(
        prefix=CacheKeys.PRODUCT_DETAILS,
        ttl=ttl,
        tags=["products", "details"]
    )


def cache_order_status(ttl: int = CacheTTL.SHORT):
    """Cache order status information."""
    return cache_service.cache_result(
        prefix=CacheKeys.ORDER_STATUS,
        ttl=ttl,
        tags=["orders", "status"]
    )


def cache_policy_content(ttl: int = CacheTTL.VERY_LONG):
    """Cache policy content."""
    return cache_service.cache_result(
        prefix=CacheKeys.POLICY_CONTENT,
        ttl=ttl,
        tags=["policies"]
    )


def cache_analytics_summary(ttl: int = CacheTTL.SHORT):
    """Cache analytics summaries."""
    return cache_service.cache_result(
        prefix=CacheKeys.ANALYTICS_SUMMARY,
        ttl=ttl,
        tags=["analytics"]
    )