"""
Cache management and monitoring endpoints.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from app.services.cache_service import cache_service
from app.db.session import get_db

router = APIRouter(prefix="/cache", tags=["Cache Management"])


class CacheStats(BaseModel):
    """Cache statistics model."""
    memory_cache_size: int
    memory_cache_max_items: int
    redis_connected: bool
    redis_initialized: Optional[bool] = None
    redis_used_memory: Optional[str] = None
    redis_connected_clients: Optional[int] = None
    redis_total_commands_processed: Optional[int] = None
    redis_keyspace_hits: Optional[int] = None
    redis_keyspace_misses: Optional[int] = None


class CacheOperation(BaseModel):
    """Cache operation result."""
    success: bool
    message: str
    affected_keys: int = 0


@router.get("/stats", response_model=CacheStats)
async def get_cache_stats():
    """Get cache performance statistics."""
    try:
        stats = await cache_service.get_cache_stats()
        return CacheStats(**stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache statistics")


@router.post("/clear", response_model=CacheOperation)
async def clear_cache(
    confirm: bool = Query(False, description="Must be true to confirm cache clearing"),
    pattern: Optional[str] = Query(None, description="Clear only keys matching this pattern")
):
    """Clear cache entries."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true to clear cache"
        )

    try:
        if pattern:
            # For now, we don't implement pattern-based clearing
            # This would require more complex Redis commands
            await cache_service.clear_all()
            message = f"All cache cleared (pattern filtering not implemented)"
        else:
            await cache_service.clear_all()
            message = "All cache cleared successfully"

        return CacheOperation(
            success=True,
            message=message,
            affected_keys=0  # We don't track exact count in current implementation
        )

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.post("/invalidate", response_model=CacheOperation)
async def invalidate_cache_by_tag(
    tag: str = Query(..., description="Cache tag to invalidate")
):
    """Invalidate cache entries by tag."""
    try:
        invalidated_count = await cache_service.invalidate_by_tag(tag)

        return CacheOperation(
            success=True,
            message=f"Invalidated {invalidated_count} cache entries for tag: {tag}",
            affected_keys=invalidated_count
        )

    except Exception as e:
        logger.error(f"Error invalidating cache by tag {tag}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache for tag: {tag}")


@router.get("/health")
async def cache_health_check():
    """Check cache system health."""
    try:
        # Test basic cache operations
        test_key = f"health_check_{datetime.utcnow().timestamp()}"
        test_value = {"test": True, "timestamp": datetime.utcnow().isoformat()}

        # Test set
        set_success = await cache_service.set(test_key, test_value, ttl=60)
        if not set_success:
            return {
                "status": "unhealthy",
                "message": "Cache set operation failed",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Test get
        retrieved_value = await cache_service.get(test_key)
        if retrieved_value != test_value:
            return {
                "status": "unhealthy",
                "message": "Cache get operation failed",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Clean up test key
        await cache_service.delete(test_key)

        # Get cache stats
        stats = await cache_service.get_cache_stats()

        return {
            "status": "healthy",
            "message": "Cache system operating normally",
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Cache health check error: {e}")
        return {
            "status": "unhealthy",
            "message": f"Cache health check failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/performance")
async def get_cache_performance_metrics():
    """Get detailed cache performance metrics."""
    try:
        stats = await cache_service.get_cache_stats()

        # Calculate performance indicators
        memory_usage_percent = (stats.get("memory_cache_size", 0) /
                              stats.get("memory_cache_max_items", 1)) * 100

        performance_metrics = {
            "cache_stats": stats,
            "performance_indicators": {
                "memory_usage_percent": round(memory_usage_percent, 2),
                "cache_efficiency": "good" if memory_usage_percent < 80 else "warning",
                "redis_status": "connected" if stats.get("redis_connected") else "disconnected"
            },
            "recommendations": []
        }

        # Add recommendations based on metrics
        if memory_usage_percent > 90:
            performance_metrics["recommendations"].append(
                "Memory cache is near capacity, consider increasing max_memory_items"
            )

        if not stats.get("redis_connected"):
            performance_metrics["recommendations"].append(
                "Redis is not connected, consider enabling Redis for better performance"
            )

        return performance_metrics

    except Exception as e:
        logger.error(f"Error getting cache performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache performance metrics")


@router.get("/tags")
async def get_cache_tags():
    """Get information about cache tags (Redis only)."""
    try:
        # This would require implementing tag enumeration in the cache service
        # For now, return known tag categories
        known_tags = [
            "products",
            "search",
            "details",
            "orders",
            "status",
            "policies",
            "analytics"
        ]

        return {
            "available_tags": known_tags,
            "note": "This shows known tag categories. Actual tag enumeration requires Redis implementation.",
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error getting cache tags: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache tags")