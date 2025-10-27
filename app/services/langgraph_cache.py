"""
Advanced caching system for LangGraph Phase 3.
Implements intelligent response caching with Redis and fallback mechanisms.
"""

import json
import hashlib
import time
import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory fallback")

from app.core.config import settings


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    data: Any
    timestamp: float
    ttl: int
    hits: int = 0
    key_hash: str = ""
    metadata: Dict[str, Any] = None

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() > (self.timestamp + self.ttl)

    def increment_hit(self):
        """Increment hit counter."""
        self.hits += 1


class LangGraphCache:
    """
    Advanced caching system for LangGraph workflows.

    Phase 3 implementation that provides:
    - Redis-based distributed caching
    - In-memory fallback
    - Intelligent cache key generation
    - Automatic cache invalidation
    - Performance metrics
    """

    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 3600):
        """
        Initialize cache system.

        Args:
            redis_url: Redis connection URL
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self.redis_client = None
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "redis_hits": 0,
            "memory_hits": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }

        # Initialize Redis if available
        if REDIS_AVAILABLE and (redis_url or getattr(settings, 'REDIS_URL', None)):
            try:
                self.redis_client = redis.from_url(
                    redis_url or getattr(settings, 'REDIS_URL', 'redis://localhost:6379'),
                    encoding='utf-8',
                    decode_responses=True
                )
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis: {e}")
                self.redis_client = None

        if not self.redis_client:
            logger.warning("Using in-memory cache only")

        # Start background cleanup task
        asyncio.create_task(self._background_cleanup())

    def _generate_cache_key(self,
                          user_message: str,
                          entities: List[Dict[str, Any]],
                          tools_used: List[str],
                          workflow_phase: str = "phase2") -> str:
        """
        Generate intelligent cache key based on message content and context.

        Args:
            user_message: Original user message
            entities: Extracted entities
            tools_used: Tools used in processing
            workflow_phase: Phase of workflow used

        Returns:
            Cache key string
        """
        # Normalize message (lowercase, remove extra whitespace)
        normalized_message = " ".join(user_message.lower().split())

        # Create entity signature
        entity_signature = ""
        if entities:
            # Sort entities by text for consistent key generation
            sorted_entities = sorted(entities, key=lambda x: x.get("text", ""))
            entity_texts = [e.get("text", "") for e in sorted_entities]
            entity_signature = "|".join(entity_texts)

        # Create tools signature
        tools_signature = ",".join(sorted(tools_used))

        # Combine all components
        key_components = [
            normalized_message[:200],  # Truncate long messages
            entity_signature,
            tools_signature,
            workflow_phase
        ]

        key_string = "|".join(key_components)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"langgraph:{workflow_phase}:{key_hash}"

    async def get(self,
                 cache_key: str,
                 include_metadata: bool = False) -> Optional[Union[Any, Dict[str, Any]]]:
        """
        Get value from cache (Redis first, then memory).

        Args:
            cache_key: Cache key
            include_metadata: Whether to include cache metadata

        Returns:
            Cached value or None
        """
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.cache_stats["hits"] += 1
                    self.cache_stats["redis_hits"] += 1

                    data = json.loads(cached_data)
                    if include_metadata:
                        return {
                            "data": data.get("data"),
                            "metadata": {
                                "cached_at": data.get("timestamp"),
                                "ttl": data.get("ttl"),
                                "source": "redis",
                                "hits": data.get("hits", 0)
                            }
                        }
                    return data.get("data")

            except Exception as e:
                logger.error(f"Redis get error: {e}")

        # Fallback to memory cache
        if cache_key in self.memory_cache:
            entry = self.memory_cache[cache_key]

            if not entry.is_expired():
                entry.increment_hit()
                self.cache_stats["hits"] += 1
                self.cache_stats["memory_hits"] += 1

                if include_metadata:
                    return {
                        "data": entry.data,
                        "metadata": {
                            "cached_at": entry.timestamp,
                            "ttl": entry.ttl,
                            "source": "memory",
                            "hits": entry.hits
                        }
                    }
                return entry.data
            else:
                # Remove expired entry
                del self.memory_cache[cache_key]
                self.cache_stats["evictions"] += 1

        self.cache_stats["misses"] += 1
        return None

    async def set(self,
                 cache_key: str,
                 value: Any,
                 ttl: Optional[int] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Set value in cache (both Redis and memory).

        Args:
            cache_key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            metadata: Additional metadata

        Returns:
            True if successful, False otherwise
        """
        ttl = ttl or self.default_ttl
        timestamp = time.time()

        # Prepare cache data
        cache_data = {
            "data": value,
            "timestamp": timestamp,
            "ttl": ttl,
            "hits": 0,
            "metadata": metadata or {}
        }

        # Save to Redis
        redis_success = False
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(cache_data)
                )
                redis_success = True
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        # Save to memory cache (always)
        self.memory_cache[cache_key] = CacheEntry(
            data=value,
            timestamp=timestamp,
            ttl=ttl,
            metadata=metadata or {}
        )

        self.cache_stats["sets"] += 1
        return redis_success

    async def delete(self, cache_key: str) -> bool:
        """
        Delete value from cache.

        Args:
            cache_key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        success = True

        # Delete from Redis
        if self.redis_client:
            try:
                await self.redis_client.delete(cache_key)
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                success = False

        # Delete from memory
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]

        self.cache_stats["deletes"] += 1
        return success

    async def get_or_set(self,
                        cache_key: str,
                        value_func,
                        ttl: Optional[int] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Any:
        """
        Get value from cache or set using provided function.

        Args:
            cache_key: Cache key
            value_func: Async function to generate value if not cached
            ttl: Time to live in seconds
            metadata: Additional metadata

        Returns:
            Cached or generated value
        """
        # Try to get from cache first
        cached_value = await self.get(cache_key)
        if cached_value is not None:
            return cached_value

        # Generate new value
        try:
            new_value = await value_func()
            await self.set(cache_key, new_value, ttl, metadata)
            return new_value
        except Exception as e:
            logger.error(f"Error generating cached value: {e}")
            raise

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.

        Args:
            pattern: Pattern to match (supports wildcards)

        Returns:
            Number of entries invalidated
        """
        invalidated_count = 0

        # Invalidate from Redis
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
                    invalidated_count += len(keys)
            except Exception as e:
                logger.error(f"Redis pattern deletion error: {e}")

        # Invalidate from memory cache
        memory_keys_to_delete = []
        for key in self.memory_cache.keys():
            if self._match_pattern(key, pattern):
                memory_keys_to_delete.append(key)

        for key in memory_keys_to_delete:
            del self.memory_cache[key]

        invalidated_count += len(memory_keys_to_delete)
        logger.info(f"Invalidated {invalidated_count} cache entries matching pattern: {pattern}")

        return invalidated_count

    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for cache keys."""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        import re
        return bool(re.match(regex_pattern, key))

    async def invalidate_phase(self, phase: str) -> int:
        """
        Invalidate all cache entries for a specific phase.

        Args:
            phase: Phase to invalidate (e.g., "phase1", "phase2")

        Returns:
            Number of entries invalidated
        """
        pattern = f"langgraph:{phase}:*"
        return await self.invalidate_pattern(pattern)

    async def cleanup_expired(self) -> int:
        """
        Clean up expired entries from memory cache.

        Returns:
            Number of entries cleaned up
        """
        expired_keys = []
        current_time = time.time()

        for key, entry in self.memory_cache.items():
            if current_time > (entry.timestamp + entry.ttl):
                expired_keys.append(key)

        for key in expired_keys:
            del self.memory_cache[key]

        self.cache_stats["evictions"] += len(expired_keys)
        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    async def _background_cleanup(self):
        """Background task to clean up expired cache entries."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self.cleanup_expired()
            except Exception as e:
                logger.error(f"Background cleanup error: {e}")
                await asyncio.sleep(60)  # Wait before retry

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache performance statistics.

        Returns:
            Cache statistics
        """
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        stats = {
            **self.cache_stats,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests,
            "memory_cache_size": len(self.memory_cache),
            "redis_available": self.redis_client is not None
        }

        if self.redis_client:
            try:
                # Get Redis info
                redis_info = asyncio.run(self.redis_client.info())
                stats["redis_memory_used"] = redis_info.get("used_memory_human", "N/A")
                stats["redis_connected_clients"] = redis_info.get("connected_clients", 0)
            except Exception as e:
                logger.error(f"Failed to get Redis info: {e}")

        return stats

    async def clear_all(self) -> bool:
        """
        Clear all cache entries.

        Returns:
            True if successful, False otherwise
        """
        success = True

        # Clear Redis
        if self.redis_client:
            try:
                await self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
                success = False

        # Clear memory cache
        self.memory_cache.clear()

        # Reset stats
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "redis_hits": 0,
            "memory_hits": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }

        logger.info("All cache entries cleared")
        return success

    def get_memory_usage(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.

        Returns:
            Memory usage information
        """
        total_entries = len(self.memory_cache)
        total_size = 0

        for key, entry in self.memory_cache.items():
            # Rough estimation of memory usage
            total_size += len(key.encode()) + len(str(entry.data).encode()) + 100  # Overhead

        return {
            "total_entries": total_entries,
            "estimated_size_bytes": total_size,
            "estimated_size_mb": round(total_size / (1024 * 1024), 2),
            "average_entry_size": total_size / total_entries if total_entries > 0 else 0
        }


class ResponseCache:
    """
    Specialized cache for LangGraph responses.

    Caches complete responses with intelligent invalidation
    based on conversation context and tool results.
    """

    def __init__(self, base_cache: LangGraphCache):
        """
        Initialize response cache.

        Args:
            base_cache: Base cache instance
        """
        self.cache = base_cache

    async def cache_response(self,
                           user_message: str,
                           response_data: Dict[str, Any],
                           entities: List[Dict[str, Any]],
                           tools_used: List[str],
                           workflow_phase: str = "phase2",
                           ttl: int = 1800) -> bool:  # 30 minutes default
        """
        Cache a complete response.

        Args:
            user_message: Original user message
            response_data: Response data to cache
            entities: Extracted entities
            tools_used: Tools used
            workflow_phase: Workflow phase
            ttl: Time to live

        Returns:
            True if cached successfully
        """
        cache_key = self.cache._generate_cache_key(
            user_message, entities, tools_used, workflow_phase
        )

        metadata = {
            "user_message": user_message,
            "entities_count": len(entities),
            "tools_used": tools_used,
            "workflow_phase": workflow_phase,
            "response_length": len(str(response_data)),
            "cached_at": datetime.now().isoformat()
        }

        return await self.cache.set(cache_key, response_data, ttl, metadata)

    async def get_cached_response(self,
                               user_message: str,
                               entities: List[Dict[str, Any]],
                               tools_used: List[str],
                               workflow_phase: str = "phase2") -> Optional[Dict[str, Any]]:
        """
        Get cached response if available.

        Args:
            user_message: Original user message
            entities: Extracted entities
            tools_used: Tools used
            workflow_phase: Workflow phase

        Returns:
            Cached response data or None
        """
        cache_key = self.cache._generate_cache_key(
            user_message, entities, tools_used, workflow_phase
        )

        return await self.cache.get(cache_key, include_metadata=True)

    async def invalidate_conversation_responses(self, conversation_id: str) -> int:
        """
        Invalidate all responses for a conversation.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Number of entries invalidated
        """
        # In a real implementation, you would track cache keys per conversation
        # For now, we'll invalidate all responses as a safety measure
        return await self.cache.invalidate_pattern("langgraph:*:*")