"""
Monitoring and health check API endpoints.
"""

from .health import router as health_router
from .metrics import router as metrics_router
from .analytics import router as analytics_router
from .alerts import router as alerts_router
from .cache import router as cache_router

__all__ = ["health_router", "metrics_router", "analytics_router", "alerts_router", "cache_router"]