"""
Metrics and performance monitoring endpoints.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from loguru import logger

from app.core.api.monitoring import get_api_monitor

router = APIRouter(prefix="/metrics", tags=["Metrics"])


class MetricSummary(BaseModel):
    """Metric summary data."""
    name: str
    count: int
    min: float
    max: float
    avg: float
    sum: float
    latest: Optional[float]


class MetricsResponse(BaseModel):
    """Metrics response."""
    timestamp: datetime
    period_minutes: int
    counters: Dict[str, float]
    gauges: Dict[str, float]
    histograms: Dict[str, MetricSummary]
    timers: Dict[str, MetricSummary]


class PerformanceMetrics(BaseModel):
    """Performance metrics data."""
    endpoint: str
    method: str
    avg_duration_ms: float
    max_duration_ms: float
    min_duration_ms: float
    request_count: int
    error_rate: float
    cache_hit_rate: float


class RealTimeMetrics(BaseModel):
    """Real-time metrics."""
    active_requests: int
    requests_per_second: float
    errors_per_second: float
    avg_response_time_ms: float
    cache_hit_rate: float


@router.get("/overview", response_model=MetricsResponse)
async def get_metrics_overview(minutes: int = Query(5, ge=1, le=60, description="Time period in minutes")):
    """Get overview of all metrics for the specified time period."""
    try:
        monitor = get_api_monitor()
        metrics_collector = monitor.metrics_collector

        # Get current metric values
        all_metrics = metrics_collector.get_all_metrics()

        # Get histogram summaries
        histograms = {}
        for name in metrics_collector.histograms.keys():
            summary = metrics_collector.get_metric_summary(name, minutes)
            if summary:
                histograms[name] = MetricSummary(
                    name=name,
                    count=summary["count"],
                    min=summary["min"],
                    max=summary["max"],
                    avg=summary["avg"],
                    sum=summary["sum"],
                    latest=summary["latest"]
                )

        # Get timer summaries
        timers = {}
        for name in metrics_collector.timers.keys():
            summary = metrics_collector.get_metric_summary(name, minutes)
            if summary:
                timers[name] = MetricSummary(
                    name=name,
                    count=summary["count"],
                    min=summary["min"],
                    max=summary["max"],
                    avg=summary["avg"],
                    sum=summary["sum"],
                    latest=summary["latest"]
                )

        return MetricsResponse(
            timestamp=datetime.utcnow(),
            period_minutes=minutes,
            counters=all_metrics["counters"],
            gauges=all_metrics["gauges"],
            histograms=histograms,
            timers=timers
        )

    except Exception as e:
        logger.error(f"Error getting metrics overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/performance", response_model=List[PerformanceMetrics])
async def get_performance_metrics(minutes: int = Query(5, ge=1, le=60, description="Time period in minutes")):
    """Get performance metrics for endpoints."""
    try:
        monitor = get_api_monitor()
        request_stats = monitor.request_tracker.get_request_stats(minutes)

        # Extract performance data by endpoint
        endpoint_stats = request_stats.get("top_endpoints", {})
        performance_metrics = []

        for endpoint, count in endpoint_stats.items():
            # Get detailed stats for this endpoint
            endpoint_requests = [
                r for r in monitor.request_tracker.requests
                if r.path == endpoint and (datetime.utcnow() - r.timestamp).total_seconds() <= minutes * 60
            ]

            if endpoint_requests:
                durations = [r.duration_ms for r in endpoint_requests]
                errors = [r for r in endpoint_requests if r.status_code >= 400]
                cache_hits = [r for r in endpoint_requests if r.cache_hit]

                # Extract method from first request (assuming all same method)
                method = endpoint_requests[0].method if endpoint_requests else "GET"

                performance_metrics.append(PerformanceMetrics(
                    endpoint=endpoint,
                    method=method,
                    avg_duration_ms=sum(durations) / len(durations),
                    max_duration_ms=max(durations),
                    min_duration_ms=min(durations),
                    request_count=len(endpoint_requests),
                    error_rate=(len(errors) / len(endpoint_requests)) * 100,
                    cache_hit_rate=(len(cache_hits) / len(endpoint_requests)) * 100
                ))

        # Sort by request count
        performance_metrics.sort(key=lambda x: x.request_count, reverse=True)

        return performance_metrics

    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance metrics")


@router.get("/realtime", response_model=RealTimeMetrics)
async def get_realtime_metrics():
    """Get real-time metrics."""
    try:
        monitor = get_api_monitor()

        # Get recent request stats (last minute)
        recent_stats = monitor.request_tracker.get_request_stats(1)
        total_requests = recent_stats.get("total_requests", 0)
        error_requests = recent_stats.get("error_requests", 0)

        # Calculate rates
        requests_per_second = total_requests / 60.0
        errors_per_second = error_requests / 60.0

        return RealTimeMetrics(
            active_requests=monitor.request_tracker.get_active_requests_count(),
            requests_per_second=requests_per_second,
            errors_per_second=errors_per_second,
            avg_response_time_ms=recent_stats.get("avg_duration_ms", 0),
            cache_hit_rate=recent_stats.get("cache_hit_rate", 0)
        )

    except Exception as e:
        logger.error(f"Error getting realtime metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve realtime metrics")


@router.get("/custom/{metric_name}")
async def get_custom_metric(
    metric_name: str,
    minutes: int = Query(5, ge=1, le=60, description="Time period in minutes")
):
    """Get data for a specific custom metric."""
    try:
        monitor = get_api_monitor()
        metrics_collector = monitor.metrics_collector

        # Get metric summary
        summary = metrics_collector.get_metric_summary(metric_name, minutes)
        if not summary:
            raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")

        # Get recent data points
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        recent_metrics = [
            m for m in metrics_collector.metrics[metric_name]
            if m.timestamp >= cutoff_time
        ]

        # Prepare time series data
        time_series = []
        for metric in recent_metrics:
            time_series.append({
                "timestamp": metric.timestamp.isoformat(),
                "value": metric.value,
                "tags": metric.tags
            })

        return {
            "metric_name": metric_name,
            "period_minutes": minutes,
            "summary": summary,
            "time_series": time_series,
            "data_points": len(time_series)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting custom metric {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metric")


@router.get("/top-endpoints")
async def get_top_endpoints(minutes: int = Query(5, ge=1, le=60, description="Time period in minutes")):
    """Get top endpoints by request count."""
    try:
        monitor = get_api_monitor()
        request_stats = monitor.request_tracker.get_request_stats(minutes)

        top_endpoints = []
        for endpoint, count in request_stats.get("top_endpoints", {}).items():
            # Calculate metrics for this endpoint
            endpoint_requests = [
                r for r in monitor.request_tracker.requests
                if r.path == endpoint and (datetime.utcnow() - r.timestamp).total_seconds() <= minutes * 60
            ]

            if endpoint_requests:
                durations = [r.duration_ms for r in endpoint_requests]
                errors = [r for r in endpoint_requests if r.status_code >= 400]

                top_endpoints.append({
                    "endpoint": endpoint,
                    "request_count": len(endpoint_requests),
                    "avg_duration_ms": sum(durations) / len(durations),
                    "error_rate": (len(errors) / len(endpoint_requests)) * 100,
                    "unique_users": len(set(r.user_id for r in endpoint_requests if r.user_id))
                })

        # Sort by request count
        top_endpoints.sort(key=lambda x: x["request_count"], reverse=True)

        return {
            "period_minutes": minutes,
            "endpoints": top_endpoints[:20]  # Top 20
        }

    except Exception as e:
        logger.error(f"Error getting top endpoints: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve top endpoints")


@router.get("/errors")
async def get_error_metrics(minutes: int = Query(5, ge=1, le=60, description="Time period in minutes")):
    """Get error metrics and analysis."""
    try:
        monitor = get_api_monitor()
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)

        # Get recent error requests
        error_requests = [
            r for r in monitor.request_tracker.requests
            if r.status_code >= 400 and r.timestamp >= cutoff_time
        ]

        # Analyze errors
        error_analysis = {
            "total_errors": len(error_requests),
            "error_rate": (len(error_requests) / max(len([
                r for r in monitor.request_tracker.requests
                if r.timestamp >= cutoff_time
            ]), 1)) * 100,
            "errors_by_status": {},
            "errors_by_endpoint": {},
            "errors_by_user_agent": {},
            "recent_errors": []
        }

        for request in error_requests:
            # Group by status code
            status = request.status_code
            error_analysis["errors_by_status"][status] = error_analysis["errors_by_status"].get(status, 0) + 1

            # Group by endpoint
            endpoint = request.path
            error_analysis["errors_by_endpoint"][endpoint] = error_analysis["errors_by_endpoint"].get(endpoint, 0) + 1

            # Group by user agent
            user_agent = request.user_agent or "Unknown"
            error_analysis["errors_by_user_agent"][user_agent] = error_analysis["errors_by_user_agent"].get(user_agent, 0) + 1

        # Get recent errors (last 10)
        recent_errors = sorted(error_requests, key=lambda x: x.timestamp, reverse=True)[:10]
        error_analysis["recent_errors"] = [
            {
                "timestamp": r.timestamp.isoformat(),
                "method": r.method,
                "endpoint": r.path,
                "status_code": r.status_code,
                "duration_ms": r.duration_ms,
                "user_id": r.user_id,
                "error_message": r.error_message
            }
            for r in recent_errors
        ]

        return error_analysis

    except Exception as e:
        logger.error(f"Error getting error metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error metrics")


@router.delete("/clear")
async def clear_metrics():
    """Clear all collected metrics."""
    try:
        monitor = get_api_monitor()

        # Clear metrics
        monitor.metrics_collector.metrics.clear()
        monitor.metrics_collector.counters.clear()
        monitor.metrics_collector.gauges.clear()
        monitor.metrics_collector.histograms.clear()
        monitor.metrics_collector.timers.clear()

        # Clear request history
        monitor.request_tracker.requests.clear()

        logger.info("All metrics cleared")
        return {"message": "All metrics cleared successfully"}

    except Exception as e:
        logger.error(f"Error clearing metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear metrics")