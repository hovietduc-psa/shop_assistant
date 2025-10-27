"""
API performance monitoring and metrics collection.
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
import statistics
from collections import defaultdict, deque
from functools import wraps
import psutil
import redis.asyncio as redis
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from app.core.config import settings


class MetricType(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class MetricValue:
    """Metric value with timestamp."""
    value: float
    timestamp: datetime
    labels: Optional[Dict[str, str]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.labels is None:
            self.labels = {}


@dataclass
class MetricDefinition:
    """Metric definition."""
    name: str
    metric_type: MetricType
    description: str
    labels: Optional[List[str]] = None
    unit: Optional[str] = None


class MetricsCollector:
    """Central metrics collection system."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.metric_definitions: Dict[str, MetricDefinition] = {}

        # Define standard metrics
        self._define_standard_metrics()

    def _define_standard_metrics(self):
        """Define standard application metrics."""
        standard_metrics = [
            MetricDefinition(
                name="http_requests_total",
                metric_type=MetricType.COUNTER,
                description="Total HTTP requests",
                labels=["method", "endpoint", "status_code"],
                unit="requests"
            ),
            MetricDefinition(
                name="http_request_duration_seconds",
                metric_type=MetricType.HISTOGRAM,
                description="HTTP request duration in seconds",
                labels=["method", "endpoint"],
                unit="seconds"
            ),
            MetricDefinition(
                name="active_connections",
                metric_type=MetricType.GAUGE,
                description="Number of active connections",
                unit="connections"
            ),
            MetricDefinition(
                name="system_cpu_usage_percent",
                metric_type=MetricType.GAUGE,
                description="System CPU usage percentage",
                unit="percent"
            ),
            MetricDefinition(
                name="system_memory_usage_percent",
                metric_type=MetricType.GAUGE,
                description="System memory usage percentage",
                unit="percent"
            ),
            MetricDefinition(
                name="llm_requests_total",
                metric_type=MetricType.COUNTER,
                description="Total LLM API requests",
                labels=["model", "status"],
                unit="requests"
            ),
            MetricDefinition(
                name="llm_request_duration_seconds",
                metric_type=MetricType.HISTOGRAM,
                description="LLM request duration in seconds",
                labels=["model"],
                unit="seconds"
            ),
            MetricDefinition(
                name="conversation_quality_score",
                metric_type=MetricType.GAUGE,
                description="Conversation quality score",
                labels=["conversation_id"],
                unit="score"
            ),
            MetricDefinition(
                name="nlu_intent_classification_accuracy",
                metric_type=MetricType.GAUGE,
                description="NLU intent classification accuracy",
                unit="percent"
            ),
            MetricDefinition(
                name="dialogue_state_transitions_total",
                metric_type=MetricType.COUNTER,
                description="Total dialogue state transitions",
                labels=["from_state", "to_state"],
                unit="transitions"
            )
        ]

        for metric_def in standard_metrics:
            self.metric_definitions[metric_def.name] = metric_def

    def increment_counter(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric."""
        self.counters[name] += value
        self._record_metric(name, value, labels)

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Set a gauge metric value."""
        self.gauges[name] = value
        self._record_metric(name, value, labels)

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a histogram metric value."""
        self.histograms[name].append(value)
        # Keep only last 1000 values
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
        self._record_metric(name, value, labels)

    def record_timer(
        self,
        name: str,
        duration: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a timer metric."""
        self.timers[name].append(duration)
        # Keep only last 1000 values
        if len(self.timers[name]) > 1000:
            self.timers[name] = self.timers[name][-1000:]
        self._record_metric(name, duration, labels)

    def _record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Record a metric value with timestamp."""
        metric_value = MetricValue(
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {}
        )
        self.metrics[name].append(metric_value)

        # Store in Redis if available
        if self.redis:
            asyncio.create_task(self._store_metric_in_redis(name, metric_value))

    async def _store_metric_in_redis(self, name: str, metric_value: MetricValue):
        """Store metric in Redis for persistence."""
        try:
            key = f"metrics:{name}"
            data = {
                "value": metric_value.value,
                "timestamp": metric_value.timestamp.isoformat(),
                "labels": metric_value.labels
            }
            await self.redis.lpush(key, json.dumps(data))
            await self.redis.expire(key, 3600)  # Keep for 1 hour
        except Exception as e:
            logger.error(f"Failed to store metric in Redis: {e}")

    def get_metric_summary(
        self,
        name: str,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get metric summary for a specific metric."""
        if name not in self.metrics:
            return {}

        cutoff_time = datetime.utcnow() - (time_window or timedelta(hours=1))
        recent_values = [
            mv.value for mv in self.metrics[name]
            if mv.timestamp > cutoff_time
        ]

        if not recent_values:
            return {}

        metric_def = self.metric_definitions.get(name)
        summary = {
            "name": name,
            "type": metric_def.metric_type.value if metric_def else "unknown",
            "description": metric_def.description if metric_def else "",
            "count": len(recent_values),
            "latest": recent_values[-1] if recent_values else None,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Add statistics based on metric type
        if metric_def and metric_def.metric_type in [MetricType.HISTOGRAM, MetricType.TIMER]:
            summary.update({
                "min": min(recent_values),
                "max": max(recent_values),
                "mean": statistics.mean(recent_values),
                "median": statistics.median(recent_values),
                "p95": self._percentile(recent_values, 95),
                "p99": self._percentile(recent_values, 99)
            })
        elif metric_def and metric_def.metric_type == MetricType.COUNTER:
            summary.update({
                "total": sum(recent_values),
                "rate": len(recent_values) / (time_window or timedelta(hours=1)).total_seconds()
            })
        elif metric_def and metric_def.metric_type == MetricType.GAUGE:
            summary.update({
                "current": recent_values[-1],
                "min": min(recent_values),
                "max": max(recent_values),
                "mean": statistics.mean(recent_values)
            })

        return summary

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_all_metrics_summaries(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get summaries for all metrics."""
        summaries = {}
        for name in self.metrics.keys():
            summary = self.get_metric_summary(name, time_window)
            if summary:
                summaries[name] = summary
        return summaries

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for name, metric_def in self.metric_definitions.items():
            if name in self.counters:
                lines.append(f"# HELP {name} {metric_def.description}")
                lines.append(f"# TYPE {name} {metric_def.metric_type.value}")
                lines.append(f"{name} {self.counters[name]}")

            elif name in self.gauges:
                lines.append(f"# HELP {name} {metric_def.description}")
                lines.append(f"# TYPE {name} {metric_def.metric_type.value}")
                lines.append(f"{name} {self.gauges[name]}")

            elif name in self.histograms and self.histograms[name]:
                lines.append(f"# HELP {name} {metric_def.description}")
                lines.append(f"# TYPE {name} {metric_def.metric_type.value}")
                values = self.histograms[name]
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_bucket{{le=\"+Inf\"}} {len(values)}")

        return "\n".join(lines)


class PerformanceMonitor:
    """Performance monitoring utility."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self.start_time = time.time()

    async def collect_system_metrics(self):
        """Collect system performance metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics.set_gauge("system_cpu_usage_percent", cpu_percent)

            # Memory metrics
            memory = psutil.virtual_memory()
            self.metrics.set_gauge("system_memory_usage_percent", memory.percent)
            self.metrics.set_gauge("system_memory_used_bytes", memory.used)
            self.metrics.set_gauge("system_memory_available_bytes", memory.available)

            # Disk metrics
            disk = psutil.disk_usage('/')
            self.metrics.set_gauge("system_disk_usage_percent", (disk.used / disk.total) * 100)
            self.metrics.set_gauge("system_disk_used_bytes", disk.used)
            self.metrics.set_gauge("system_disk_free_bytes", disk.free)

            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            self.metrics.set_gauge("process_memory_rss_bytes", process_memory.rss)
            self.metrics.set_gauge("process_memory_vms_bytes", process_memory.vms)
            self.metrics.set_gauge("process_cpu_percent", process.cpu_percent())
            self.metrics.set_gauge("process_num_threads", process.num_threads())

            # Network metrics
            network = psutil.net_io_counters()
            self.metrics.increment_counter("network_bytes_sent", network.bytes_sent)
            self.metrics.increment_counter("network_bytes_recv", network.bytes_recv)

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    async def collect_application_metrics(self):
        """Collect application-specific metrics."""
        try:
            # Active connections (placeholder - would be tracked by connection middleware)
            self.metrics.set_gauge("active_connections", 0)

            # Request metrics (updated by middleware)
            uptime = time.time() - self.start_time
            self.metrics.set_gauge("application_uptime_seconds", uptime)

        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")


def track_request_metrics(metrics_collector: MetricsCollector):
    """Decorator to track request metrics for API endpoints."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            method = "UNKNOWN"
            endpoint = "UNKNOWN"
            status_code = 200

            try:
                # Extract request info if available
                if args and hasattr(args[0], '__class__'):
                    # This is a rough approximation - in practice you'd get this from middleware
                    pass

                result = await func(*args, **kwargs)

                # Record successful request
                duration = time.time() - start_time
                metrics_collector.increment_counter(
                    "http_requests_total",
                    labels={"method": method, "endpoint": endpoint, "status_code": str(status_code)}
                )
                metrics_collector.record_histogram(
                    "http_request_duration_seconds",
                    duration,
                    labels={"method": method, "endpoint": endpoint}
                )

                return result

            except Exception as e:
                duration = time.time() - start_time
                status_code = 500

                metrics_collector.increment_counter(
                    "http_requests_total",
                    labels={"method": method, "endpoint": endpoint, "status_code": str(status_code)}
                )
                metrics_collector.record_histogram(
                    "http_request_duration_seconds",
                    duration,
                    labels={"method": method, "endpoint": endpoint}
                )
                metrics_collector.increment_counter(
                    "http_errors_total",
                    labels={"method": method, "endpoint": endpoint, "error_type": type(e).__name__}
                )

                raise

        return wrapper
    return decorator


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    def __init__(self, app, metrics_collector: MetricsCollector):
        super().__init__(app)
        self.metrics = metrics_collector

    async def dispatch(self, request: Request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Extract request information
        method = request.method
        endpoint = request.url.path
        status_code = response.status_code

        # Record metrics
        self.metrics.increment_counter(
            "http_requests_total",
            labels={
                "method": method,
                "endpoint": endpoint,
                "status_code": str(status_code)
            }
        )

        self.metrics.record_histogram(
            "http_request_duration_seconds",
            duration,
            labels={
                "method": method,
                "endpoint": endpoint
            }
        )

        # Record error metrics
        if status_code >= 400:
            self.metrics.increment_counter(
                "http_errors_total",
                labels={
                    "method": method,
                    "endpoint": endpoint,
                    "status_code": str(status_code)
                }
            )

        # Add metrics headers
        response.headers["X-Metrics-Request-Duration"] = f"{duration:.3f}s"

        return response


# Global metrics collector instance
metrics_collector = MetricsCollector()
performance_monitor = PerformanceMonitor(metrics_collector)


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return metrics_collector


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return performance_monitor


# Background task to collect metrics
async def metrics_collection_task():
    """Background task to periodically collect metrics."""
    while True:
        try:
            await performance_monitor.collect_system_metrics()
            await performance_monitor.collect_application_metrics()
            await asyncio.sleep(30)  # Collect every 30 seconds
        except Exception as e:
            logger.error(f"Metrics collection task error: {e}")
            await asyncio.sleep(60)  # Wait longer on error


# LLM service metrics tracking
class LLMMetricsTracker:
    """Track LLM service metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def track_request(
        self,
        model: str,
        duration: float,
        success: bool,
        tokens_used: Optional[int] = None
    ):
        """Track an LLM request."""
        status = "success" if success else "error"

        self.metrics.increment_counter(
            "llm_requests_total",
            labels={"model": model, "status": status}
        )

        self.metrics.record_histogram(
            "llm_request_duration_seconds",
            duration,
            labels={"model": model}
        )

        if tokens_used:
            self.metrics.increment_counter(
                "llm_tokens_used_total",
                tokens_used,
                labels={"model": model}
            )


# NLU service metrics tracking
class NLUMetricsTracker:
    """Track NLU service metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def track_intent_classification(
        self,
        predicted_intent: str,
        true_intent: Optional[str] = None,
        confidence: float = 0.0,
        duration: float = 0.0
    ):
        """Track intent classification metrics."""
        self.metrics.record_histogram(
            "nlu_intent_classification_duration_seconds",
            duration
        )

        self.metrics.record_histogram(
            "nlu_intent_confidence",
            confidence
        )

        if true_intent:
            accuracy = 1.0 if predicted_intent == true_intent else 0.0
            self.metrics.record_histogram(
                "nlu_intent_classification_accuracy",
                accuracy
            )

    def track_entity_extraction(
        self,
        entities_found: int,
        duration: float = 0.0
    ):
        """Track entity extraction metrics."""
        self.metrics.record_histogram(
            "nlu_entity_extraction_duration_seconds",
            duration
        )

        self.metrics.record_histogram(
            "nlu_entities_found_count",
            entities_found
        )

    def track_sentiment_analysis(
        self,
        sentiment: str,
        confidence: float = 0.0,
        duration: float = 0.0
    ):
        """Track sentiment analysis metrics."""
        self.metrics.record_histogram(
            "nlu_sentiment_analysis_duration_seconds",
            duration
        )

        self.metrics.record_histogram(
            "nlu_sentiment_confidence",
            confidence
        )


# Dialogue service metrics tracking
class DialogueMetricsTracker:
    """Track dialogue service metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector

    def track_state_transition(
        self,
        from_state: str,
        to_state: str,
        confidence: float = 0.0
    ):
        """Track dialogue state transition."""
        self.metrics.increment_counter(
            "dialogue_state_transitions_total",
            labels={"from_state": from_state, "to_state": to_state}
        )

        self.metrics.record_histogram(
            "dialogue_transition_confidence",
            confidence,
            labels={"from_state": from_state, "to_state": to_state}
        )

    def track_conversation_quality(
        self,
        conversation_id: str,
        quality_score: float,
        dimensions: Dict[str, float]
    ):
        """Track conversation quality metrics."""
        self.metrics.record_histogram(
            "conversation_quality_score",
            quality_score,
            labels={"conversation_id": conversation_id}
        )

        for dimension, score in dimensions.items():
            self.metrics.record_histogram(
                f"conversation_quality_{dimension}_score",
                score,
                labels={"conversation_id": conversation_id}
            )


# Global tracker instances
llm_tracker = LLMMetricsTracker(metrics_collector)
nlu_tracker = NLUMetricsTracker(metrics_collector)
dialogue_tracker = DialogueMetricsTracker(metrics_collector)