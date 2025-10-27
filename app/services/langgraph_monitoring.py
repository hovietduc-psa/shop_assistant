"""
Performance monitoring system for LangGraph Phase 3.
Real-time metrics collection, analysis, and optimization recommendations.
"""

import time
import asyncio
import statistics
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from loguru import logger

@dataclass
class PerformanceMetric:
    """Single performance metric entry."""
    timestamp: float
    processing_time: float
    phase: str
    path_taken: str
    tools_used: List[str]
    entities_count: int
    llm_calls_count: int
    success: bool
    error_type: Optional[str] = None
    response_length: int = 0
    cache_hit: bool = False
    thread_id: str = ""

@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0

    # Phase breakdown
    phase_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Path breakdown
    path_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Tool usage stats
    tool_usage: Dict[str, int] = field(default_factory=dict)

    # Error breakdown
    error_stats: Dict[str, int] = field(default_factory=dict)

    # Cache performance
    cache_hit_rate: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    # Recent performance (last 100 requests)
    recent_avg_response_time: float = 0.0

class LangGraphMonitor:
    """
    Performance monitoring system for LangGraph workflows.

    Phase 3 implementation that provides:
    - Real-time performance tracking
    - Automated analysis and insights
    - Performance optimization recommendations
    - Alerting for performance degradation
    """

    def __init__(self, max_history: int = 10000, alert_thresholds: Optional[Dict[str, float]] = None):
        """
        Initialize performance monitor.

        Args:
            max_history: Maximum number of metrics to keep in memory
            alert_thresholds: Threshold values for alerting
        """
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.alert_thresholds = alert_thresholds or {
            "response_time_p95": 10.0,  # 95th percentile should be under 10s
            "error_rate": 0.05,         # Error rate should be under 5%
            "success_rate": 0.95,       # Success rate should be above 95%
            "cache_hit_rate": 0.30       # Cache hit rate should be above 30%
        }

        self.last_alert_time: Dict[str, float] = {}
        self.alert_cooldown = 300  # 5 minutes between alerts

        # Background monitoring tasks
        self.monitoring_active = True
        asyncio.create_task(self._background_analysis())
        asyncio.create_task(self._cleanup_old_data())

    def record_metric(self,
                     processing_time: float,
                     phase: str,
                     path_taken: str,
                     tools_used: List[str],
                     entities_count: int,
                     llm_calls_count: int,
                     success: bool,
                     error_type: Optional[str] = None,
                     response_length: int = 0,
                     cache_hit: bool = False,
                     thread_id: str = ""):
        """
        Record a performance metric.

        Args:
            processing_time: Total processing time in seconds
            phase: Workflow phase used
            path_taken: Processing path taken (simple/parallel)
            tools_used: List of tools used
            entities_count: Number of entities extracted
            llm_calls_count: Number of LLM calls made
            success: Whether the request was successful
            error_type: Type of error if failed
            response_length: Length of response in characters
            cache_hit: Whether response was served from cache
            thread_id: Conversation thread ID
        """
        metric = PerformanceMetric(
            timestamp=time.time(),
            processing_time=processing_time,
            phase=phase,
            path_taken=path_taken,
            tools_used=tools_used,
            entities_count=entities_count,
            llm_calls_count=llm_calls_count,
            success=success,
            error_type=error_type,
            response_length=response_length,
            cache_hit=cache_hit,
            thread_id=thread_id
        )

        self.metrics_history.append(metric)

        # Check for immediate alerts
        self._check_immediate_alerts(metric)

    def get_stats(self, time_window: Optional[int] = None) -> PerformanceStats:
        """
        Calculate performance statistics.

        Args:
            time_window: Time window in seconds (None for all data)

        Returns:
            Performance statistics
        """
        current_time = time.time()

        # Filter metrics by time window
        if time_window:
            cutoff_time = current_time - time_window
            metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        else:
            metrics = list(self.metrics_history)

        if not metrics:
            return PerformanceStats()

        # Calculate basic stats
        total_requests = len(metrics)
        successful_requests = sum(1 for m in metrics if m.success)
        failed_requests = total_requests - successful_requests

        processing_times = [m.processing_time for m in metrics]

        stats = PerformanceStats(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            average_response_time=statistics.mean(processing_times),
            min_response_time=min(processing_times),
            max_response_time=max(processing_times),
            median_response_time=statistics.median(processing_times),
            p95_response_time=self._percentile(processing_times, 95),
            p99_response_time=self._percentile(processing_times, 99)
        )

        # Phase breakdown
        phase_groups = {}
        for metric in metrics:
            if metric.phase not in phase_groups:
                phase_groups[metric.phase] = []
            phase_groups[metric.phase].append(metric.processing_time)

        for phase, times in phase_groups.items():
            stats.phase_stats[phase] = {
                "count": len(times),
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times)
            }

        # Path breakdown
        path_groups = {}
        for metric in metrics:
            if metric.path_taken not in path_groups:
                path_groups[metric.path_taken] = []
            path_groups[metric.path_taken].append(metric.processing_time)

        for path, times in path_groups.items():
            stats.path_stats[path] = {
                "count": len(times),
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times)
            }

        # Tool usage
        tool_counts = {}
        for metric in metrics:
            for tool in metric.tools_used:
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        stats.tool_usage = tool_counts

        # Error breakdown
        error_counts = {}
        for metric in metrics:
            if metric.error_type:
                error_counts[metric.error_type] = error_counts.get(metric.error_type, 0) + 1
        stats.error_stats = error_counts

        # Cache performance
        cache_hits = sum(1 for m in metrics if m.cache_hit)
        cache_misses = total_requests - cache_hits
        stats.cache_hits = cache_hits
        stats.cache_misses = cache_misses
        stats.cache_hit_rate = (cache_hits / total_requests) if total_requests > 0 else 0

        # Recent performance (last 100 requests)
        recent_metrics = metrics[-100:] if len(metrics) >= 100 else metrics
        if recent_metrics:
            recent_times = [m.processing_time for m in recent_metrics]
            stats.recent_avg_response_time = statistics.mean(recent_times)

        return stats

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)
        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def _check_immediate_alerts(self, metric: PerformanceMetric):
        """Check for immediate performance alerts."""
        current_time = time.time()

        # Response time alert
        if metric.processing_time > 15.0:  # Very slow response
            self._send_alert("high_response_time", {
                "response_time": metric.processing_time,
                "phase": metric.phase,
                "path": metric.path_taken
            }, current_time)

        # Error alert
        if not metric.success:
            self._send_alert("request_failure", {
                "error_type": metric.error_type,
                "phase": metric.phase,
                "tools_used": metric.tools_used
            }, current_time)

    def _send_alert(self, alert_type: str, data: Dict[str, Any], current_time: float):
        """Send performance alert with cooldown."""
        last_alert_time = self.last_alert_time.get(alert_type, 0)

        if current_time - last_alert_time > self.alert_cooldown:
            logger.warning(f"Performance Alert [{alert_type}]: {data}")
            self.last_alert_time[alert_type] = current_time

            # In production, you would send to monitoring system
            # e.g., Slack, PagerDuty, DataDog, etc.

    async def _background_analysis(self):
        """Background task for periodic performance analysis."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(60)  # Analyze every minute
                await self._analyze_performance_trends()
                await self._check_threshold_alerts()
            except Exception as e:
                logger.error(f"Background analysis error: {e}")
                await asyncio.sleep(30)

    async def _analyze_performance_trends(self):
        """Analyze performance trends over time."""
        if len(self.metrics_history) < 100:
            return

        # Get stats for different time windows
        recent_stats = self.get_stats(300)    # Last 5 minutes
        older_stats = self.get_stats(1800)    # Last 30 minutes

        if recent_stats.total_requests < 10 or older_stats.total_requests < 10:
            return

        # Compare recent vs older performance
        time_change = recent_stats.average_response_time - older_stats.average_response_time
        error_rate_change = (recent_stats.failed_requests / recent_stats.total_requests) - \
                          (older_stats.failed_requests / older_stats.total_requests)

        # Detect degradation
        if time_change > 2.0:  # Response time increased by 2+ seconds
            logger.warning(f"Performance degradation detected: +{time_change:.2f}s response time")

        if error_rate_change > 0.02:  # Error rate increased by 2%+
            logger.warning(f"Error rate degradation detected: +{error_rate_change*100:.1f}%")

    async def _check_threshold_alerts(self):
        """Check against configured alert thresholds."""
        stats = self.get_stats(300)  # Last 5 minutes

        if stats.total_requests < 10:
            return

        current_time = time.time()

        # Response time alert
        if stats.p95_response_time > self.alert_thresholds["response_time_p95"]:
            self._send_alert("high_p95_response_time", {
                "p95_response_time": stats.p95_response_time,
                "threshold": self.alert_thresholds["response_time_p95"],
                "total_requests": stats.total_requests
            }, current_time)

        # Error rate alert
        error_rate = stats.failed_requests / stats.total_requests
        if error_rate > self.alert_thresholds["error_rate"]:
            self._send_alert("high_error_rate", {
                "error_rate": error_rate,
                "threshold": self.alert_thresholds["error_rate"],
                "failed_requests": stats.failed_requests,
                "total_requests": stats.total_requests
            }, current_time)

        # Success rate alert
        success_rate = stats.successful_requests / stats.total_requests
        if success_rate < self.alert_thresholds["success_rate"]:
            self._send_alert("low_success_rate", {
                "success_rate": success_rate,
                "threshold": self.alert_thresholds["success_rate"],
                "successful_requests": stats.successful_requests,
                "total_requests": stats.total_requests
            }, current_time)

        # Cache hit rate alert
        if stats.cache_hit_rate < self.alert_thresholds["cache_hit_rate"]:
            self._send_alert("low_cache_hit_rate", {
                "cache_hit_rate": stats.cache_hit_rate,
                "threshold": self.alert_thresholds["cache_hit_rate"],
                "cache_hits": stats.cache_hits,
                "total_requests": stats.total_requests
            }, current_time)

    async def _cleanup_old_data(self):
        """Background task to clean up old data."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Keep only recent data (last 24 hours)
                cutoff_time = time.time() - 86400
                original_size = len(self.metrics_history)

                # Filter in-place
                self.metrics_history = deque(
                    (m for m in self.metrics_history if m.timestamp >= cutoff_time),
                    maxlen=self.max_history
                )

                cleaned_count = original_size - len(self.metrics_history)
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} old performance metrics")

            except Exception as e:
                logger.error(f"Data cleanup error: {e}")
                await asyncio.sleep(300)

    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate optimization recommendations based on performance data.

        Returns:
            List of optimization recommendations
        """
        if len(self.metrics_history) < 50:
            return [{"message": "Insufficient data for recommendations", "priority": "info"}]

        stats = self.get_stats(1800)  # Last 30 minutes
        recommendations = []

        # Response time recommendations
        if stats.average_response_time > 8.0:
            recommendations.append({
                "message": f"Average response time ({stats.average_response_time:.2f}s) is high. Consider optimizing LLM calls or enabling caching.",
                "priority": "high",
                "metric": "response_time",
                "value": stats.average_response_time
            })

        # Cache recommendations
        if stats.cache_hit_rate < 0.20:
            recommendations.append({
                "message": f"Cache hit rate ({stats.cache_hit_rate*100:.1f}%) is low. Consider implementing more aggressive caching.",
                "priority": "medium",
                "metric": "cache_hit_rate",
                "value": stats.cache_hit_rate
            })

        # Tool usage recommendations
        if stats.tool_usage:
            most_used_tool = max(stats.tool_usage.items(), key=lambda x: x[1])
            if most_used_tool[1] > stats.total_requests * 0.5:
                recommendations.append({
                    "message": f"Tool '{most_used_tool[0]}' is used in {most_used_tool[1]/stats.total_requests*100:.1f}% of requests. Consider optimizing this tool or caching its results.",
                    "priority": "medium",
                    "metric": "tool_usage",
                    "value": most_used_tool
                })

        # Error recommendations
        if stats.failed_requests > 0:
            most_common_error = max(stats.error_stats.items(), key=lambda x: x[1])
            recommendations.append({
                "message": f"Most common error: '{most_common_error[0]}' ({most_common_error[1]} occurrences). Investigate and fix root cause.",
                "priority": "high",
                "metric": "error_analysis",
                "value": most_common_error
            })

        # Phase performance recommendations
        for phase, phase_stat in stats.phase_stats.items():
            if phase_stat["avg_time"] > 10.0:
                recommendations.append({
                    "message": f"Phase '{phase}' average time ({phase_stat['avg_time']:.2f}s) is high. Consider optimizing this phase.",
                    "priority": "medium",
                    "metric": "phase_performance",
                    "value": {phase: phase_stat}
                })

        # Path performance recommendations
        for path, path_stat in stats.path_stats.items():
            if path == "parallel" and path_stat["avg_time"] > stats.path_stats.get("simple", {}).get("avg_time", 0):
                recommendations.append({
                    "message": f"Parallel path is slower than simple path. Consider adjusting routing logic.",
                    "priority": "low",
                    "metric": "path_efficiency",
                    "value": path_stat
                })

        return recommendations if recommendations else [{"message": "Performance looks good!", "priority": "success"}]

    def stop_monitoring(self):
        """Stop background monitoring tasks."""
        self.monitoring_active = False
        logger.info("Performance monitoring stopped")

# Global monitor instance
langgraph_monitor = LangGraphMonitor()