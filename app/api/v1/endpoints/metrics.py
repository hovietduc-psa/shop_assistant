"""
Metrics and monitoring endpoints.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Query, HTTPException, Response
from loguru import logger

from app.monitoring.metrics import (
    get_metrics_collector,
    get_performance_monitor,
    llm_tracker,
    nlu_tracker,
    dialogue_tracker
)

router = APIRouter()


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    time_window_hours: Optional[int] = Query(1, ge=1, le=24, description="Time window in hours"),
    metric_names: Optional[List[str]] = Query(None, description="Specific metric names to retrieve"),
    format: Optional[str] = Query("json", regex="^(json|prometheus)$", description="Output format")
):
    """
    Get application metrics.

    Args:
        time_window_hours: Time window for metrics (1-24 hours)
        metric_names: Specific metrics to retrieve (optional)
        format: Output format (json or prometheus)

    Returns:
        Metrics data in requested format
    """
    try:
        metrics_collector = get_metrics_collector()
        time_window = timedelta(hours=time_window_hours)

        if format == "prometheus":
            prometheus_data = metrics_collector.export_prometheus_format()
            return Response(content=prometheus_data, media_type="text/plain")

        # JSON format
        if metric_names:
            # Get specific metrics
            summaries = {}
            for name in metric_names:
                summary = metrics_collector.get_metric_summary(name, time_window)
                if summary:
                    summaries[name] = summary
        else:
            # Get all metrics
            summaries = metrics_collector.get_all_metrics_summaries(time_window)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_window_hours": time_window_hours,
            "metrics": summaries
        }

    except Exception as e:
        logger.error(f"Failed to retrieve metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/metrics/llm", response_model=Dict[str, Any])
async def get_llm_metrics(
    time_window_hours: Optional[int] = Query(1, ge=1, le=24),
    model: Optional[str] = Query(None, description="Filter by model name")
):
    """
    Get LLM service metrics.

    Args:
        time_window_hours: Time window for metrics
        model: Filter by specific model

    Returns:
        LLM metrics data
    """
    try:
        metrics_collector = get_metrics_collector()
        time_window = timedelta(hours=time_window_hours)

        llm_metrics = [
            "llm_requests_total",
            "llm_request_duration_seconds",
            "llm_tokens_used_total"
        ]

        summaries = {}
        for metric_name in llm_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, time_window)
            if summary:
                summaries[metric_name] = summary

        # Filter by model if specified
        if model:
            filtered_summaries = {}
            for metric_name, summary in summaries.items():
                # This would require more sophisticated filtering in a real implementation
                filtered_summaries[metric_name] = summary
            summaries = filtered_summaries

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_window_hours": time_window_hours,
            "model_filter": model,
            "metrics": summaries
        }

    except Exception as e:
        logger.error(f"Failed to retrieve LLM metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve LLM metrics")


@router.get("/metrics/nlu", response_model=Dict[str, Any])
async def get_nlu_metrics(
    time_window_hours: Optional[int] = Query(1, ge=1, le=24)
):
    """
    Get NLU service metrics.

    Args:
        time_window_hours: Time window for metrics

    Returns:
        NLU metrics data
    """
    try:
        metrics_collector = get_metrics_collector()
        time_window = timedelta(hours=time_window_hours)

        nlu_metrics = [
            "nlu_intent_classification_duration_seconds",
            "nlu_intent_confidence",
            "nlu_intent_classification_accuracy",
            "nlu_entity_extraction_duration_seconds",
            "nlu_entities_found_count",
            "nlu_sentiment_analysis_duration_seconds",
            "nlu_sentiment_confidence"
        ]

        summaries = {}
        for metric_name in nlu_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, time_window)
            if summary:
                summaries[metric_name] = summary

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_window_hours": time_window_hours,
            "metrics": summaries
        }

    except Exception as e:
        logger.error(f"Failed to retrieve NLU metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve NLU metrics")


@router.get("/metrics/dialogue", response_model=Dict[str, Any])
async def get_dialogue_metrics(
    time_window_hours: Optional[int] = Query(1, ge=1, le=24)
):
    """
    Get dialogue service metrics.

    Args:
        time_window_hours: Time window for metrics

    Returns:
        Dialogue metrics data
    """
    try:
        metrics_collector = get_metrics_collector()
        time_window = timedelta(hours=time_window_hours)

        dialogue_metrics = [
            "dialogue_state_transitions_total",
            "dialogue_transition_confidence",
            "conversation_quality_score"
        ]

        summaries = {}
        for metric_name in dialogue_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, time_window)
            if summary:
                summaries[metric_name] = summary

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "time_window_hours": time_window_hours,
            "metrics": summaries
        }

    except Exception as e:
        logger.error(f"Failed to retrieve dialogue metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dialogue metrics")


@router.get("/metrics/system", response_model=Dict[str, Any])
async def get_system_metrics():
    """
    Get current system metrics.

    Returns:
        Current system performance metrics
    """
    try:
        performance_monitor = get_performance_monitor()
        metrics_collector = get_metrics_collector()

        # Collect fresh system metrics
        await performance_monitor.collect_system_metrics()

        system_metrics = [
            "system_cpu_usage_percent",
            "system_memory_usage_percent",
            "system_memory_used_bytes",
            "system_memory_available_bytes",
            "system_disk_usage_percent",
            "system_disk_used_bytes",
            "system_disk_free_bytes",
            "process_memory_rss_bytes",
            "process_memory_vms_bytes",
            "process_cpu_percent",
            "process_num_threads",
            "active_connections",
            "application_uptime_seconds"
        ]

        summaries = {}
        for metric_name in system_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, timedelta(minutes=5))
            if summary:
                summaries[metric_name] = summary

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": summaries
        }

    except Exception as e:
        logger.error(f"Failed to retrieve system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system metrics")


@router.get("/metrics/overview", response_model=Dict[str, Any])
async def get_metrics_overview():
    """
    Get metrics overview dashboard data.

    Returns:
        Overview metrics for dashboard display
    """
    try:
        metrics_collector = get_metrics_collector()
        performance_monitor = get_performance_monitor()

        # Collect fresh metrics
        await performance_monitor.collect_system_metrics()
        await performance_monitor.collect_application_metrics()

        # Get key metrics for different time windows
        time_windows = {
            "last_5_minutes": timedelta(minutes=5),
            "last_hour": timedelta(hours=1),
            "last_24_hours": timedelta(hours=24)
        }

        overview = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {},
            "application": {},
            "services": {}
        }

        # System metrics (current)
        system_metrics = [
            "system_cpu_usage_percent",
            "system_memory_usage_percent",
            "system_disk_usage_percent"
        ]

        for metric_name in system_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, timedelta(minutes=5))
            if summary and "current" in summary:
                overview["system"][metric_name] = summary["current"]

        # Application metrics (last hour)
        app_metrics = [
            "http_requests_total",
            "http_request_duration_seconds",
            "active_connections"
        ]

        for metric_name in app_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, timedelta(hours=1))
            if summary:
                overview["application"][metric_name] = summary

        # Service metrics (last 24 hours)
        service_metrics = [
            "llm_requests_total",
            "llm_request_duration_seconds",
            "nlu_intent_classification_accuracy",
            "conversation_quality_score"
        ]

        for metric_name in service_metrics:
            summary = metrics_collector.get_metric_summary(metric_name, timedelta(hours=24))
            if summary:
                overview["services"][metric_name] = summary

        return overview

    except Exception as e:
        logger.error(f"Failed to retrieve metrics overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics overview")


@router.get("/metrics/alerts", response_model=Dict[str, Any])
async def get_metrics_alerts():
    """
    Get metrics-based alerts.

    Returns:
        Active alerts based on metric thresholds
    """
    try:
        metrics_collector = get_metrics_collector()
        performance_monitor = get_performance_monitor()

        # Collect fresh metrics
        await performance_monitor.collect_system_metrics()

        alerts = []

        # Define alert thresholds
        alert_thresholds = {
            "system_cpu_usage_percent": {"warning": 80, "critical": 90},
            "system_memory_usage_percent": {"warning": 80, "critical": 90},
            "system_disk_usage_percent": {"warning": 85, "critical": 95},
            "http_request_duration_seconds": {"warning": 2.0, "critical": 5.0},
            "llm_request_duration_seconds": {"warning": 10.0, "critical": 20.0},
            "conversation_quality_score": {"warning": 0.6, "critical": 0.4}
        }

        # Check thresholds
        for metric_name, thresholds in alert_thresholds.items():
            summary = metrics_collector.get_metric_summary(metric_name, timedelta(minutes=5))
            if not summary:
                continue

            current_value = None
            if "current" in summary:
                current_value = summary["current"]
            elif "mean" in summary:
                current_value = summary["mean"]
            elif "latest" in summary:
                current_value = summary["latest"]

            if current_value is not None:
                if current_value >= thresholds["critical"]:
                    alerts.append({
                        "metric": metric_name,
                        "severity": "critical",
                        "current_value": current_value,
                        "threshold": thresholds["critical"],
                        "message": f"Critical: {metric_name} is {current_value:.2f} (threshold: {thresholds['critical']})",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif current_value >= thresholds["warning"]:
                    alerts.append({
                        "metric": metric_name,
                        "severity": "warning",
                        "current_value": current_value,
                        "threshold": thresholds["warning"],
                        "message": f"Warning: {metric_name} is {current_value:.2f} (threshold: {thresholds['warning']})",
                        "timestamp": datetime.utcnow().isoformat()
                    })

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_alerts": len(alerts),
            "alerts": alerts
        }

    except Exception as e:
        logger.error(f"Failed to retrieve metrics alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics alerts")


@router.post("/metrics/custom", response_model=Dict[str, Any])
async def record_custom_metric(
    metric_name: str,
    metric_value: float,
    metric_type: str = Query("gauge", regex="^(counter|gauge|histogram|timer)$"),
    labels: Optional[Dict[str, str]] = None
):
    """
    Record a custom metric.

    Args:
        metric_name: Name of the metric
        metric_value: Value to record
        metric_type: Type of metric (counter, gauge, histogram, timer)
        labels: Optional labels for the metric

    Returns:
        Confirmation of metric recording
    """
    try:
        metrics_collector = get_metrics_collector()

        if metric_type == "counter":
            metrics_collector.increment_counter(metric_name, metric_value, labels)
        elif metric_type == "gauge":
            metrics_collector.set_gauge(metric_name, metric_value, labels)
        elif metric_type == "histogram":
            metrics_collector.record_histogram(metric_name, metric_value, labels)
        elif metric_type == "timer":
            metrics_collector.record_timer(metric_name, metric_value, labels)

        return {
            "message": f"Metric {metric_name} recorded successfully",
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metric_type": metric_type,
            "labels": labels or {},
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to record custom metric: {e}")
        raise HTTPException(status_code=500, detail="Failed to record custom metric")