"""
API monitoring and analytics system.
"""

import time
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

from fastapi import Request, Response
from loguru import logger

from app.core.config import settings


class MetricType(Enum):
    """Types of metrics."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertLevel(Enum):
    """Alert levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class APIMetric:
    """API metric data point."""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class RequestMetric:
    """Request-specific metric."""
    method: str
    path: str
    status_code: int
    duration_ms: float
    timestamp: datetime
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    response_size: int = 0
    request_size: int = 0
    cache_hit: bool = False
    error_message: Optional[str] = None


@dataclass
class Alert:
    """Alert definition."""
    id: str
    name: str
    level: AlertLevel
    condition: str
    threshold: float
    window_minutes: int
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    notification_channels: List[str] = field(default_factory=list)


class MetricsCollector:
    """Collects and stores metrics."""

    def __init__(self, max_samples: int = 10000):
        """Initialize metrics collector."""
        self.max_samples = max_samples
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)

    def increment_counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self.counters[key] += value
        self._add_metric(name, value, MetricType.COUNTER, tags)

    def set_gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set a gauge metric."""
        key = self._make_key(name, tags)
        self.gauges[key] = value
        self._add_metric(name, value, MetricType.GAUGE, tags)

    def record_histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a histogram value."""
        key = self._make_key(name, tags)
        self.histograms[key].append(value)
        self._add_metric(name, value, MetricType.HISTOGRAM, tags)

    def record_timer(self, name: str, duration_ms: float, tags: Dict[str, str] = None):
        """Record a timer value."""
        key = self._make_key(name, tags)
        self.timers[key].append(duration_ms)
        self._add_metric(name, duration_ms, MetricType.TIMER, tags)

    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """Create a key from name and tags."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"

    def _add_metric(self, name: str, value: float, metric_type: MetricType, tags: Dict[str, str] = None):
        """Add a metric to the storage."""
        metric = APIMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.utcnow(),
            tags=tags or {}
        )
        self.metrics[name].append(metric)

    def get_metric_summary(self, name: str, minutes: int = 5) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        recent_metrics = [
            m for m in self.metrics[name]
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        values = [m.value for m in recent_metrics]

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "sum": sum(values),
            "latest": values[-1] if values else None
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metric values."""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                key: {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values) if values else 0
                }
                for key, values in self.histograms.items()
            },
            "timers": {
                key: {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values) if values else 0
                }
                for key, values in self.timers.items()
            }
        }

    def cleanup_old_metrics(self, hours: int = 24):
        """Clean up old metrics."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        removed_count = 0

        for name, metric_deque in self.metrics.items():
            original_len = len(metric_deque)
            while metric_deque and metric_deque[0].timestamp < cutoff_time:
                metric_deque.popleft()
                removed_count += 1

        logger.debug(f"Cleaned up {removed_count} old metrics")


class RequestTracker:
    """Tracks API requests and responses."""

    def __init__(self, max_requests: int = 10000):
        """Initialize request tracker."""
        self.max_requests = max_requests
        self.requests: deque = deque(maxlen=max_requests)
        self.active_requests: Dict[str, datetime] = {}

    def start_request(self, request_id: str, request: Request) -> datetime:
        """Start tracking a request."""
        start_time = datetime.utcnow()
        self.active_requests[request_id] = start_time
        return start_time

    def end_request(self,
                   request_id: str,
                   request: Request,
                   response: Response,
                   start_time: datetime) -> RequestMetric:
        """End tracking a request and record metrics."""
        end_time = datetime.utcnow()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        # Extract request information
        user_id = getattr(request.state, 'user_id', None)
        client_id = getattr(request.state, 'client_id', None)
        user_agent = request.headers.get("user-agent")
        ip_address = request.client.host if request.client else None

        # Create request metric
        metric = RequestMetric(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            timestamp=start_time,
            user_id=user_id,
            client_id=client_id,
            user_agent=user_agent,
            ip_address=ip_address,
            response_size=len(response.body) if hasattr(response, 'body') else 0,
            request_size=0,  # Request body size not available in synchronous context
            cache_hit=getattr(request.state, 'cache_hit', False),
            error_message=getattr(request.state, 'error_message', None)
        )

        # Store request metric
        self.requests.append(metric)

        # Remove from active requests
        self.active_requests.pop(request_id, None)

        return metric

    def get_request_stats(self, minutes: int = 5) -> Dict[str, Any]:
        """Get request statistics."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        recent_requests = [
            r for r in self.requests
            if r.timestamp >= cutoff_time
        ]

        if not recent_requests:
            return {}

        # Calculate statistics
        total_requests = len(recent_requests)
        successful_requests = len([r for r in recent_requests if 200 <= r.status_code < 400])
        error_requests = total_requests - successful_requests

        durations = [r.duration_ms for r in recent_requests]
        status_codes = defaultdict(int)
        endpoints = defaultdict(int)
        methods = defaultdict(int)

        for request in recent_requests:
            status_codes[request.status_code] += 1
            endpoints[request.path] += 1
            methods[request.method] += 1

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "status_codes": dict(status_codes),
            "top_endpoints": dict(sorted(endpoints.items(), key=lambda x: x[1], reverse=True)[:10]),
            "methods": dict(methods),
            "cache_hit_rate": (len([r for r in recent_requests if r.cache_hit]) / total_requests * 100) if total_requests > 0 else 0
        }

    def get_active_requests_count(self) -> int:
        """Get count of active requests."""
        return len(self.active_requests)


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self):
        """Initialize alert manager."""
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.notification_handlers: Dict[str, Callable] = {}

    def create_alert(self,
                    alert_id: str,
                    name: str,
                    level: AlertLevel,
                    condition: str,
                    threshold: float,
                    window_minutes: int = 5,
                    notification_channels: List[str] = None) -> Alert:
        """Create a new alert."""
        alert = Alert(
            id=alert_id,
            name=name,
            level=level,
            condition=condition,
            threshold=threshold,
            window_minutes=window_minutes,
            notification_channels=notification_channels or []
        )
        self.alerts[alert_id] = alert
        return alert

    def check_alerts(self, metrics_collector: MetricsCollector, request_tracker: RequestTracker):
        """Check all alerts against current metrics."""
        for alert in self.alerts.values():
            if not alert.enabled:
                continue

            try:
                should_trigger = self._evaluate_alert_condition(alert, metrics_collector, request_tracker)
                if should_trigger:
                    self._trigger_alert(alert)
            except Exception as e:
                logger.error(f"Error evaluating alert {alert.id}: {e}")

    def _evaluate_alert_condition(self,
                                 alert: Alert,
                                 metrics_collector: MetricsCollector,
                                 request_tracker: RequestTracker) -> bool:
        """Evaluate alert condition."""
        # Parse condition (simple implementation)
        if alert.condition == "error_rate":
            stats = request_tracker.get_request_stats(alert.window_minutes)
            error_rate = (stats.get("error_requests", 0) / stats.get("total_requests", 1)) * 100
            return error_rate > alert.threshold

        elif alert.condition == "response_time":
            stats = request_tracker.get_request_stats(alert.window_minutes)
            avg_duration = stats.get("avg_duration_ms", 0)
            return avg_duration > alert.threshold

        elif alert.condition == "request_count":
            stats = request_tracker.get_request_stats(alert.window_minutes)
            return stats.get("total_requests", 0) > alert.threshold

        # Add more condition types as needed
        return False

    def _trigger_alert(self, alert: Alert):
        """Trigger an alert."""
        alert.last_triggered = datetime.utcnow()
        alert.trigger_count += 1

        # Add to history
        self.alert_history.append({
            "alert_id": alert.id,
            "name": alert.name,
            "level": alert.level.value,
            "triggered_at": alert.last_triggered,
            "trigger_count": alert.trigger_count
        })

        # Send notifications
        for channel in alert.notification_channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    asyncio.create_task(handler(alert))
                except Exception as e:
                    logger.error(f"Error sending alert notification: {e}")

        logger.warning(f"Alert triggered: {alert.name} ({alert.level.value})")

    def register_notification_handler(self, channel: str, handler: Callable):
        """Register a notification handler."""
        self.notification_handlers[channel] = handler

    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert["triggered_at"] >= cutoff_time
        ]


class APIMonitor:
    """Main API monitoring system."""

    def __init__(self):
        """Initialize API monitor."""
        self.metrics_collector = MetricsCollector()
        self.request_tracker = RequestTracker()
        self.alert_manager = AlertManager()
        self.enabled = True
        self.cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the monitoring system."""
        if not self.enabled:
            return

        # Create default alerts
        self._create_default_alerts()

        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("API monitoring system started")

    async def stop(self):
        """Stop the monitoring system."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("API monitoring system stopped")

    def _create_default_alerts(self):
        """Create default alerts."""
        # High error rate alert
        self.alert_manager.create_alert(
            "high_error_rate",
            "High Error Rate",
            AlertLevel.WARNING,
            "error_rate",
            threshold=5.0,  # 5% error rate
            window_minutes=5
        )

        # Slow response time alert
        self.alert_manager.create_alert(
            "slow_response_time",
            "Slow Response Time",
            AlertLevel.WARNING,
            "response_time",
            threshold=1000.0,  # 1 second
            window_minutes=5
        )

        # High request volume alert
        self.alert_manager.create_alert(
            "high_request_volume",
            "High Request Volume",
            AlertLevel.INFO,
            "request_count",
            threshold=1000,  # 1000 requests
            window_minutes=5
        )

    async def _cleanup_loop(self):
        """Periodic cleanup loop."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                self.metrics_collector.cleanup_old_metrics()
                logger.debug("API monitoring cleanup completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"API monitoring cleanup error: {e}")

    def record_request(self,
                      request: Request,
                      response: Response,
                      start_time: datetime,
                      request_id: str) -> RequestMetric:
        """Record a request metric."""
        # Update general metrics
        self.metrics_collector.increment_counter("api_requests_total", tags={
            "method": request.method,
            "endpoint": request.url.path,
            "status": str(response.status_code)
        })

        if response.status_code >= 400:
            self.metrics_collector.increment_counter("api_errors_total", tags={
                "method": request.method,
                "endpoint": request.url.path,
                "status": str(response.status_code)
            })

        # Record timer
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        self.metrics_collector.record_timer("api_request_duration_ms", duration_ms, tags={
            "method": request.method,
            "endpoint": request.url.path
        })

        # Track detailed request
        metric = self.request_tracker.end_request(request_id, request, response, start_time)

        # Check alerts
        self.alert_manager.check_alerts(self.metrics_collector, self.request_tracker)

        return metric

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get data for monitoring dashboard."""
        return {
            "metrics": self.metrics_collector.get_all_metrics(),
            "request_stats": self.request_tracker.get_request_stats(minutes=60),
            "active_requests": self.request_tracker.get_active_requests_count(),
            "recent_alerts": self.alert_manager.get_alert_history(hours=24),
            "system_health": self._get_system_health()
        }

    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        request_stats = self.request_tracker.get_request_stats(minutes=5)
        error_rate = (request_stats.get("error_requests", 0) / max(request_stats.get("total_requests", 1), 1)) * 100
        avg_response_time = request_stats.get("avg_duration_ms", 0)

        # Determine health status
        if error_rate > 10 or avg_response_time > 5000:
            status = "unhealthy"
        elif error_rate > 5 or avg_response_time > 2000:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "error_rate": error_rate,
            "avg_response_time_ms": avg_response_time,
            "active_requests": self.request_tracker.get_active_requests_count(),
            "uptime": "N/A"  # Would track actual uptime
        }


# Global monitor instance
api_monitor = APIMonitor()


def get_api_monitor() -> APIMonitor:
    """Get the global API monitor instance."""
    return api_monitor


# Decorator for monitoring endpoints
def monitor_endpoint(endpoint_name: Optional[str] = None):
    """Decorator to monitor an endpoint."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not api_monitor.enabled:
                return await func(*args, **kwargs)

            # Extract request from kwargs
            request = kwargs.get('request')
            if not request:
                return await func(*args, **kwargs)

            # Generate request ID and start tracking
            import uuid
            request_id = str(uuid.uuid4())
            start_time = api_monitor.request_tracker.start_request(request_id, request)

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Create mock response for monitoring
                response = type('MockResponse', (), {
                    'status_code': 200,
                    'body': str(result).encode() if result else b''
                })()

                # Record the request
                api_monitor.record_request(request, response, start_time, request_id)

                return result

            except Exception as e:
                # Record error
                response = type('MockResponse', (), {
                    'status_code': 500,
                    'body': str(e).encode()
                })()

                api_monitor.record_request(request, response, start_time, request_id)
                raise

        return wrapper
    return decorator