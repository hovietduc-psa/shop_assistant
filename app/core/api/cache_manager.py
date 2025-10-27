"""
Advanced API caching strategies with Redis backend.
"""

import json
import pickle
import hashlib
import time
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from functools import wraps

import redis.asyncio as redis
from fastapi import Request, Response
from loguru import logger

from app.core.config import settings

T = TypeVar('T')


class CacheStrategy(Enum):
    """Caching strategies."""
    NO_CACHE = "no_cache"
    CACHE_FIRST = "cache_first"
    NETWORK_FIRST = "network_first"
    CACHE_ONLY = "cache_only"
    CACHE_THEN_NETWORK = "cache_then_network"
    NETWORK_THEN_CACHE = "network_then_cache"


class CacheKeyGenerator:
    """Generates cache keys for requests."""

    @staticmethod
    def generate_key(method: str,
                    path: str,
                    query_params: Dict[str, Any],
                    headers: Dict[str, str],
                    user_context: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key from request components."""
        # Create a normalized representation
        key_data = {
            "method": method.upper(),
            "path": path,
            "query": sorted(query_params.items()),
            "user": user_context or {}
        }

        # Add relevant headers
        relevant_headers = ["accept", "accept-language", "authorization"]
        for header in relevant_headers:
            if header in headers:
                if header == "authorization":
                    # Hash authorization header for privacy
                    key_data["headers"] = {header: hashlib.sha256(headers[header].encode()).hexdigest()[:16]}
                else:
                    key_data["headers"] = {header: headers[header]}

        # Create hash of the key data
        key_str = json.dumps(key_data, sort_keys=True, separators=(',', ':'))
        key_hash = hashlib.sha256(key_str.encode('utf-8')).hexdigest()

        return f"api_cache:{key_hash}"

    @staticmethod
    def generate_data_key(data_type: str,
                          identifier: str,
                          version: str = "v1") -> str:
        """Generate cache key for data."""
        return f"data_cache:{version}:{data_type}:{identifier}"

    @staticmethod
    def generate_query_key(query_type: str,
                          query_params: Dict[str, Any],
                          version: str = "v1") -> str:
        """Generate cache key for query results."""
        query_str = json.dumps(sorted(query_params.items()), sort_keys=True)
        query_hash = hashlib.sha256(query_str.encode('utf-8')).hexdigest()
        return f"query_cache:{version}:{query_type}:{query_hash}"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    size_bytes: int = 0
    etag: Optional[str] = None
    content_type: Optional[str] = None

    def __post_init__(self):
        """Calculate entry size."""
        if isinstance(self.data, (str, bytes)):
            self.size_bytes = len(self.data)
        else:
            self.size_bytes = len(pickle.dumps(self.data))

    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.utcnow()


class CacheConfig:
    """Cache configuration."""

    def __init__(self):
        """Initialize cache configuration."""
        self.default_ttl = 300  # 5 minutes
        self.max_ttl = 3600  # 1 hour
        self.max_entries = 10000
        self.max_size_mb = 100
        self.cleanup_interval = 300  # 5 minutes
        self.compression_threshold = 1024  # 1KB

        # TTL settings by data type
        self.ttl_settings = {
            "user_data": 900,      # 15 minutes
            "product_data": 1800,  # 30 minutes
            "search_results": 300, # 5 minutes
            "analytics": 3600,     # 1 hour
            "config": 86400,       # 24 hours
            "static": 604800       # 7 days
        }


class AdvancedCacheManager:
    """Advanced cache manager with Redis backend."""

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize cache manager."""
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self.config = CacheConfig()
        self.key_generator = CacheKeyGenerator()
        self.local_cache: Dict[str, CacheEntry] = {}  # Fallback cache
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=False,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            await self.redis_client.ping()
            logger.info("Cache manager connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis for caching: {e}")
            self.redis_client = None

    async def get(self,
                  key: str,
                  default: Any = None,
                  strategy: CacheStrategy = CacheStrategy.CACHE_FIRST) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found
            strategy: Caching strategy

        Returns:
            Cached value or default
        """
        try:
            if strategy == CacheStrategy.NO_CACHE:
                return default

            # Try Redis first
            if self.redis_client:
                cached_data = await self.redis_client.get(key)
                if cached_data:
                    entry = pickle.loads(cached_data)
                    entry.touch()
                    self.stats["hits"] += 1
                    return entry.data

            # Fallback to local cache
            if key in self.local_cache:
                entry = self.local_cache[key]
                if not entry.is_expired():
                    entry.touch()
                    self.stats["hits"] += 1
                    return entry.data
                else:
                    del self.local_cache[key]

            self.stats["misses"] += 1
            return default

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            self.stats["misses"] += 1
            return default

    async def set(self,
                  key: str,
                  value: Any,
                  ttl: Optional[int] = None,
                  tags: Optional[List[str]] = None,
                  content_type: Optional[str] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Cache tags for invalidation
            content_type: Content type of the data

        Returns:
            True if successful
        """
        try:
            ttl = ttl or self.config.default_ttl
            ttl = min(ttl, self.config.max_ttl)

            # Create cache entry
            expires_at = datetime.utcnow() + timedelta(seconds=ttl) if ttl > 0 else None
            entry = CacheEntry(
                data=value,
                created_at=datetime.utcnow(),
                expires_at=expires_at,
                tags=tags or [],
                content_type=content_type
            )

            # Store in Redis
            if self.redis_client:
                serialized_entry = pickle.dumps(entry)
                await self.redis_client.setex(key, ttl, serialized_entry)

                # Store tags for invalidation
                if tags:
                    for tag in tags:
                        tag_key = f"tag:{tag}"
                        await self.redis_client.sadd(tag_key, key)
                        await self.redis_client.expire(tag_key, ttl)

            # Store in local cache as fallback
            self.local_cache[key] = entry

            # Clean up if needed
            await self._cleanup_local_cache()

            self.stats["sets"] += 1
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            if self.redis_client:
                await self.redis_client.delete(key)

            if key in self.local_cache:
                del self.local_cache[key]

            self.stats["deletes"] += 1
            return True

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate cache entries by tags."""
        invalidated_count = 0

        try:
            if self.redis_client:
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    keys = await self.redis_client.smembers(tag_key)
                    if keys:
                        await self.redis_client.delete(*keys)
                        invalidated_count += len(keys)
                    await self.redis_client.delete(tag_key)

            # Clean local cache
            keys_to_remove = []
            for key, entry in self.local_cache.items():
                if any(tag in entry.tags for tag in tags):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.local_cache[key]
                invalidated_count += 1

            logger.info(f"Invalidated {invalidated_count} cache entries by tags: {tags}")
            return invalidated_count

        except Exception as e:
            logger.error(f"Cache invalidation error for tags {tags}: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hit_rate = 0
        total_requests = self.stats["hits"] + self.stats["misses"]
        if total_requests > 0:
            hit_rate = (self.stats["hits"] / total_requests) * 100

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "sets": self.stats["sets"],
            "deletes": self.stats["deletes"],
            "evictions": self.stats["evictions"],
            "local_cache_size": len(self.local_cache),
            "redis_connected": self.redis_client is not None
        }

    async def clear_all(self) -> bool:
        """Clear all cache entries."""
        try:
            if self.redis_client:
                # Delete all cache keys
                pattern = "*_cache:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)

            # Clear local cache
            self.local_cache.clear()

            logger.info("Cleared all cache entries")
            return True

        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False

    def _cleanup_local_cache(self):
        """Clean up expired entries from local cache."""
        now = datetime.utcnow()
        keys_to_remove = []

        for key, entry in self.local_cache.items():
            if entry.is_expired():
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.local_cache[key]
            self.stats["evictions"] += 1

        # Remove oldest entries if cache is too large
        if len(self.local_cache) > self.config.max_entries:
            # Sort by last accessed time
            sorted_entries = sorted(
                self.local_cache.items(),
                key=lambda x: x[1].last_accessed or x[1].created_at
            )

            # Remove oldest entries
            entries_to_remove = sorted_entries[:len(self.local_cache) - self.config.max_entries]
            for key, _ in entries_to_remove:
                del self.local_cache[key]
                self.stats["evictions"] += 1


def cache_response(ttl: int = 300,
                   tags: Optional[List[str]] = None,
                   strategy: CacheStrategy = CacheStrategy.CACHE_FIRST,
                   key_generator: Optional[Callable] = None,
                   vary_on: Optional[List[str]] = None):
    """
    Decorator for caching response data.

    Args:
        ttl: Time to live in seconds
        tags: Cache tags for invalidation
        strategy: Caching strategy
        key_generator: Custom key generator function
        vary_on: List of request attributes to vary cache on
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Extract request from kwargs if available
            request = kwargs.get('request')
            if not request:
                return await func(*args, **kwargs)

            # Generate cache key
            if key_generator:
                cache_key = key_generator(request, *args, **kwargs)
            else:
                cache_key = CacheKeyGenerator.generate_key(
                    method=request.method,
                    path=request.url.path,
                    query_params=dict(request.query_params),
                    headers=dict(request.headers)
                )

            # Get cache manager
            from . import cache_manager

            # Try to get from cache
            if strategy != CacheStrategy.NETWORK_FIRST:
                cached_response = await cache_manager.get(cache_key)
                if cached_response is not None:
                    return cached_response

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl=ttl, tags=tags)

            return result

        return wrapper
    return decorator


class ResponseCache:
    """Response cache for HTTP responses."""

    def __init__(self, cache_manager: AdvancedCacheManager):
        """Initialize response cache."""
        self.cache_manager = cache_manager

    async def get_cached_response(self,
                                 request: Request,
                                 ttl: int = 300) -> Optional[Response]:
        """Get cached HTTP response."""
        cache_key = CacheKeyGenerator.generate_key(
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            headers=dict(request.headers)
        )

        cached_data = await self.cache_manager.get(cache_key)
        if cached_data:
            return Response(
                content=cached_data["content"],
                status_code=cached_data["status_code"],
                headers=cached_data["headers"],
                media_type=cached_data["media_type"]
            )

        return None

    async def cache_response(self,
                            request: Request,
                            response: Response,
                            ttl: int = 300,
                            tags: Optional[List[str]] = None):
        """Cache HTTP response."""
        cache_key = CacheKeyGenerator.generate_key(
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            headers=dict(request.headers)
        )

        response_data = {
            "content": response.body,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "media_type": response.media_type
        }

        await self.cache_manager.set(cache_key, response_data, ttl=ttl, tags=tags)


# Global cache manager instance
cache_manager = AdvancedCacheManager()


async def get_cache_manager() -> AdvancedCacheManager:
    """Get the global cache manager instance."""
    if not cache_manager.redis_client:
        await cache_manager.initialize()
    return cache_manager