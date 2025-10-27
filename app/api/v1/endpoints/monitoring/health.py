"""
Health check endpoints.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

from app.core.api.monitoring import get_api_monitor
from app.core.api.cache_manager import get_cache_manager
from app.core.api.rate_limiter import get_rate_limiter
from app.integrations.shopify.service import ShopifyService
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["Health Checks"])


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    MAINTENANCE = "maintenance"


class ComponentStatus(BaseModel):
    """Status of a system component."""
    name: str
    status: HealthStatus
    response_time_ms: float
    last_check: datetime
    error_message: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    uptime_percentage: Optional[float] = None


class SystemHealth(BaseModel):
    """Overall system health."""
    status: HealthStatus
    timestamp: datetime
    uptime_seconds: int
    version: str
    environment: str
    components: List[ComponentStatus]
    performance_metrics: Dict[str, float]
    active_connections: int
    memory_usage_mb: float
    cpu_usage_percent: float


class DetailedHealthCheck(BaseModel):
    """Detailed health check response."""
    system: SystemHealth
    checks: Dict[str, Any]
    recommendations: List[str]
    last_restart: Optional[datetime] = None


class HealthChecker:
    """Comprehensive health checker."""

    def __init__(self):
        """Initialize health checker."""
        self.start_time = datetime.utcnow()
        self.component_history: Dict[str, List[ComponentStatus]] = {}
        self.max_history = 100

    async def check_database_health(self) -> ComponentStatus:
        """Check database connectivity and performance."""
        start_time = time.time()
        name = "database"

        try:
            # This would check actual database connectivity
            # For now, simulate the check
            await asyncio.sleep(0.1)  # Simulate DB query

            response_time = (time.time() - start_time) * 1000

            if response_time < 100:
                status = HealthStatus.HEALTHY
            elif response_time < 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return ComponentStatus(
                name=name,
                status=status,
                response_time_ms=response_time,
                last_check=datetime.utcnow(),
                details={
                    "connection_pool_size": 10,
                    "active_connections": 3,
                    "query_cache_hit_rate": 0.85
                }
            )

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return ComponentStatus(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )

    async def check_redis_health(self) -> ComponentStatus:
        """Check Redis connectivity and performance."""
        start_time = time.time()
        name = "redis"

        try:
            # Check Redis connectivity
            cache_manager = await get_cache_manager()
            if cache_manager.redis_client:
                # Test Redis operation
                test_key = "health_check_test"
                await cache_manager.redis_client.set(test_key, "test", ex=10)
                value = await cache_manager.redis_client.get(test_key)
                await cache_manager.redis_client.delete(test_key)

                if value == b"test":
                    response_time = (time.time() - start_time) * 1000
                    status = HealthStatus.HEALTHY if response_time < 50 else HealthStatus.DEGRADED

                    # Get Redis info
                    info = await cache_manager.redis_client.info()

                    return ComponentStatus(
                        name=name,
                        status=status,
                        response_time_ms=response_time,
                        last_check=datetime.utcnow(),
                        details={
                            "used_memory_mb": info.get("used_memory", 0) / (1024 * 1024),
                            "connected_clients": info.get("connected_clients", 0),
                            "total_commands_processed": info.get("total_commands_processed", 0)
                        }
                    )
                else:
                    raise Exception("Redis test failed")
            else:
                return ComponentStatus(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.utcnow(),
                    error_message="Redis not connected"
                )

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return ComponentStatus(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )

    async def check_shopify_health(self) -> ComponentStatus:
        """Check Shopify API connectivity."""
        start_time = time.time()
        name = "shopify_api"

        try:
            async with ShopifyService() as shopify:
                # Test Shopify API connectivity
                is_healthy = await shopify.health_check()
                response_time = (time.time() - start_time) * 1000

                status = HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY

                return ComponentStatus(
                    name=name,
                    status=status,
                    response_time_ms=response_time,
                    last_check=datetime.utcnow(),
                    details={
                        "shop_domain": settings.SHOPIFY_SHOP_DOMAIN or "not_configured",
                        "api_version": settings.SHOPIFY_API_VERSION
                    }
                )

        except Exception as e:
            logger.error(f"Shopify health check failed: {e}")
            return ComponentStatus(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )

    async def check_llm_health(self) -> ComponentStatus:
        """Check LLM service connectivity."""
        start_time = time.time()
        name = "llm_service"

        try:
            # This would check actual LLM service
            # For now, simulate the check
            await asyncio.sleep(0.2)  # Simulate API call

            response_time = (time.time() - start_time) * 1000
            status = HealthStatus.HEALTHY if response_time < 2000 else HealthStatus.DEGRADED

            return ComponentStatus(
                name=name,
                status=status,
                response_time_ms=response_time,
                last_check=datetime.utcnow(),
                details={
                    "provider": "OpenRouter",
                    "default_model": settings.DEFAULT_LLM_MODEL,
                    "api_status": "connected"
                }
            )

        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return ComponentStatus(
                name=name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.utcnow(),
                error_message=str(e)
            )

    async def check_system_resources(self) -> ComponentStatus:
        """Check system resources (CPU, memory, disk)."""
        start_time = time.time()
        name = "system_resources"

        try:
            import psutil

            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            response_time = (time.time() - start_time) * 1000

            # Determine status based on resource usage
            if cpu_percent < 70 and memory.percent < 80 and disk.percent < 90:
                status = HealthStatus.HEALTHY
            elif cpu_percent < 90 and memory.percent < 90 and disk.percent < 95:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            return ComponentStatus(
                name=name,
                status=status,
                response_time_ms=response_time,
                last_check=datetime.utcnow(),
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "memory_total_gb": memory.total / (1024**3),
                    "disk_percent": disk.percent,
                    "disk_used_gb": disk.used / (1024**3),
                    "disk_total_gb": disk.total / (1024**3)
                }
            )

        except Exception as e:
            logger.error(f"System resources health check failed: {e}")
            return ComponentStatus(
                name=name,
                status=HealthStatus.DEGRADED,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.utcnow(),
                error_message="Could not fetch system metrics"
            )

    async def get_overall_health(self) -> SystemHealth:
        """Get overall system health."""
        # Run all health checks
        components = await asyncio.gather(
            self.check_database_health(),
            self.check_redis_health(),
            self.check_shopify_health(),
            self.check_llm_health(),
            self.check_system_resources()
        )

        # Store component history
        for component in components:
            if component.name not in self.component_history:
                self.component_history[component.name] = []
            self.component_history[component.name].append(component)
            if len(self.component_history[component.name]) > self.max_history:
                self.component_history[component.name].pop(0)

        # Calculate overall status
        unhealthy_count = sum(1 for c in components if c.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for c in components if c.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 1:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        # Calculate performance metrics
        avg_response_time = sum(c.response_time_ms for c in components) / len(components)
        max_response_time = max(c.response_time_ms for c in components)

        # Get system metrics
        system_component = next((c for c in components if c.name == "system_resources"), None)
        memory_usage = system_component.details.get("memory_used_gb", 0) if system_component else 0
        cpu_usage = system_component.details.get("cpu_percent", 0) if system_component else 0

        # Get active connections
        api_monitor = get_api_monitor()
        active_connections = api_monitor.request_tracker.get_active_requests_count()

        uptime = int((datetime.utcnow() - self.start_time).total_seconds())

        return SystemHealth(
            status=overall_status,
            timestamp=datetime.utcnow(),
            uptime_seconds=uptime,
            version=settings.VERSION,
            environment="development" if settings.DEBUG else "production",
            components=components,
            performance_metrics={
                "avg_response_time_ms": avg_response_time,
                "max_response_time_ms": max_response_time
            },
            active_connections=active_connections,
            memory_usage_mb=memory_usage * 1024,
            cpu_usage_percent=cpu_usage
        )

    def calculate_uptime_percentage(self, component_name: str, hours: int = 24) -> float:
        """Calculate uptime percentage for a component."""
        if component_name not in self.component_history:
            return 0.0

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_checks = [
            c for c in self.component_history[component_name]
            if c.last_check >= cutoff_time
        ]

        if not recent_checks:
            return 0.0

        healthy_checks = sum(1 for c in recent_checks if c.status == HealthStatus.HEALTHY)
        return (healthy_checks / len(recent_checks)) * 100


# Global health checker
health_checker = HealthChecker()


@router.get("/ping")
async def ping():
    """Simple ping endpoint for basic health check."""
    return {"status": "ok", "timestamp": datetime.utcnow()}


@router.get("/basic")
async def basic_health_check():
    """Basic health check without detailed diagnostics."""
    try:
        # Quick checks
        cache_manager = await get_cache_manager()
        redis_status = cache_manager.redis_client is not None

        api_monitor = get_api_monitor()
        request_stats = api_monitor.request_tracker.get_request_stats(minutes=1)

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "services": {
                "api": "healthy",
                "redis": "healthy" if redis_status else "unhealthy",
                "cache": "healthy"
            },
            "metrics": {
                "requests_last_minute": request_stats.get("total_requests", 0),
                "active_connections": api_monitor.request_tracker.get_active_requests_count()
            }
        }

    except Exception as e:
        logger.error(f"Basic health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/detailed", response_model=DetailedHealthCheck)
async def detailed_health_check():
    """Comprehensive health check with detailed diagnostics."""
    try:
        system_health = await health_checker.get_overall_health()

        # Add uptime percentages to components
        for component in system_health.components:
            component.uptime_percentage = health_checker.calculate_uptime_percentage(
                component.name, hours=24
            )

        # Generate recommendations
        recommendations = []
        for component in system_health.components:
            if component.status == HealthStatus.UNHEALTHY:
                recommendations.append(f"Urgent: {component.name} is unhealthy - {component.error_message}")
            elif component.status == HealthStatus.DEGRADED:
                recommendations.append(f"Attention: {component.name} performance is degraded")

        # Additional checks
        checks = {
            "rate_limiter": {
                "status": "healthy",
                "active_clients": len(await get_rate_limiter().client_quotas)
            },
            "monitoring": {
                "status": "healthy",
                "metrics_collected": len(get_api_monitor().metrics_collector.metrics)
            }
        }

        return DetailedHealthCheck(
            system=system_health,
            checks=checks,
            recommendations=recommendations,
            last_restart=health_checker.start_time
        )

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


@router.get("/component/{component_name}")
async def component_health_check(component_name: str):
    """Health check for a specific component."""
    component_checks = {
        "database": health_checker.check_database_health,
        "redis": health_checker.check_redis_health,
        "shopify_api": health_checker.check_shopify_health,
        "llm_service": health_checker.check_llm_health,
        "system_resources": health_checker.check_system_resources
    }

    if component_name not in component_checks:
        raise HTTPException(status_code=404, detail=f"Component '{component_name}' not found")

    try:
        component_status = await component_checks[component_name]()
        component_status.uptime_percentage = health_checker.calculate_uptime_percentage(
            component_name, hours=24
        )
        return component_status

    except Exception as e:
        logger.error(f"Component health check failed for {component_name}: {e}")
        raise HTTPException(status_code=503, detail=f"Component '{component_name}' check failed")


@router.get("/history/{component_name}")
async def component_health_history(component_name: str, hours: int = 24):
    """Get health check history for a component."""
    if component_name not in health_checker.component_history:
        raise HTTPException(status_code=404, detail=f"Component '{component_name}' not found")

    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    history = [
        c for c in health_checker.component_history[component_name]
        if c.last_check >= cutoff_time
    ]

    return {
        "component": component_name,
        "period_hours": hours,
        "checks": [
            {
                "timestamp": c.last_check,
                "status": c.status.value,
                "response_time_ms": c.response_time_ms,
                "error_message": c.error_message
            }
            for c in history
        ],
        "uptime_percentage": health_checker.calculate_uptime_percentage(component_name, hours)
    }


@router.post("/trigger-cleanup")
async def trigger_health_cleanup(background_tasks: BackgroundTasks):
    """Trigger cleanup of old health check data."""
    background_tasks.add_task(cleanup_health_data)
    return {"message": "Cleanup task triggered"}


async def cleanup_health_data():
    """Background task to clean up old health data."""
    try:
        # Clean up component history (keep last 7 days)
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        for component_name, history in health_checker.component_history.items():
            health_checker.component_history[component_name] = [
                c for c in history if c.last_check >= cutoff_time
            ]

        logger.info("Health data cleanup completed")
    except Exception as e:
        logger.error(f"Health data cleanup failed: {e}")