"""
API analytics and reporting endpoints.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session

from app.core.api.monitoring import get_api_monitor
from app.services.conversation_analytics import conversation_analytics_service
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class UsageAnalytics(BaseModel):
    """Usage analytics data."""
    period_days: int
    total_requests: int
    unique_users: int
    unique_clients: int
    avg_requests_per_user: float
    top_endpoints: List[Dict[str, Any]]
    usage_by_hour: Dict[str, int]
    error_trends: Dict[str, float]


class PerformanceAnalytics(BaseModel):
    """Performance analytics data."""
    period_days: int
    avg_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    slowest_endpoints: List[Dict[str, Any]]
    performance_trends: Dict[str, List[float]]
    cache_performance: Dict[str, float]


class ClientAnalytics(BaseModel):
    """Client analytics data."""
    client_id: str
    total_requests: int
    avg_response_time_ms: float
    error_rate: float
    top_endpoints: List[str]
    first_seen: datetime
    last_seen: datetime
    quota_utilization: float


@router.get("/usage", response_model=UsageAnalytics)
async def get_usage_analytics(days: int = Query(7, ge=1, le=90, description="Analysis period in days")):
    """Get usage analytics for the specified period."""
    try:
        monitor = get_api_monitor()
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        # Filter requests for the period
        period_requests = [
            r for r in monitor.request_tracker.requests
            if r.timestamp >= cutoff_time
        ]

        # Calculate basic metrics
        total_requests = len(period_requests)
        unique_users = len(set(r.user_id for r in period_requests if r.user_id))
        unique_clients = len(set(r.client_id for r in period_requests if r.client_id))
        avg_requests_per_user = total_requests / max(unique_users, 1)

        # Get top endpoints
        endpoint_counts = {}
        for request in period_requests:
            endpoint = f"{request.method} {request.path}"
            endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

        top_endpoints = [
            {"endpoint": endpoint, "count": count, "percentage": (count / total_requests) * 100}
            for endpoint, count in sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]

        # Calculate usage by hour
        usage_by_hour = {}
        for request in period_requests:
            hour = request.timestamp.strftime("%H:00")
            usage_by_hour[hour] = usage_by_hour.get(hour, 0) + 1

        # Calculate error trends
        error_trends = {}
        for i in range(days):
            day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_requests = [
                r for r in period_requests
                if r.timestamp.strftime("%Y-%m-%d") == day
            ]
            day_errors = len([r for r in day_requests if r.status_code >= 400])
            error_rate = (day_errors / len(day_requests)) * 100 if day_requests else 0
            error_trends[day] = error_rate

        return UsageAnalytics(
            period_days=days,
            total_requests=total_requests,
            unique_users=unique_users,
            unique_clients=unique_clients,
            avg_requests_per_user=avg_requests_per_user,
            top_endpoints=top_endpoints,
            usage_by_hour=usage_by_hour,
            error_trends=error_trends
        )

    except Exception as e:
        logger.error(f"Error generating usage analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate usage analytics")


@router.get("/performance", response_model=PerformanceAnalytics)
async def get_performance_analytics(days: int = Query(7, ge=1, le=90, description="Analysis period in days")):
    """Get performance analytics for the specified period."""
    try:
        monitor = get_api_monitor()
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        # Filter requests for the period
        period_requests = [
            r for r in monitor.request_tracker.requests
            if r.timestamp >= cutoff_time
        ]

        if not period_requests:
            return PerformanceAnalytics(
                period_days=days,
                avg_response_time_ms=0,
                p95_response_time_ms=0,
                p99_response_time_ms=0,
                slowest_endpoints=[],
                performance_trends={},
                cache_performance={}
            )

        # Calculate response time metrics
        durations = [r.duration_ms for r in period_requests]
        durations.sort()

        avg_response_time_ms = sum(durations) / len(durations)
        p95_response_time_ms = durations[int(len(durations) * 0.95)]
        p99_response_time_ms = durations[int(len(durations) * 0.99)]

        # Get slowest endpoints
        endpoint_performance = {}
        for request in period_requests:
            endpoint = f"{request.method} {request.path}"
            if endpoint not in endpoint_performance:
                endpoint_performance[endpoint] = []
            endpoint_performance[endpoint].append(request.duration_ms)

        slowest_endpoints = []
        for endpoint, times in endpoint_performance.items():
            avg_time = sum(times) / len(times)
            slowest_endpoints.append({
                "endpoint": endpoint,
                "avg_response_time_ms": avg_time,
                "request_count": len(times)
            })

        slowest_endpoints.sort(key=lambda x: x["avg_response_time_ms"], reverse=True)
        slowest_endpoints = slowest_endpoints[:10]

        # Calculate performance trends
        performance_trends = {}
        for i in range(min(days, 30)):  # Limit to 30 days for readability
            day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_requests = [
                r for r in period_requests
                if r.timestamp.strftime("%Y-%m-%d") == day
            ]
            if day_requests:
                day_durations = [r.duration_ms for r in day_requests]
                performance_trends[day] = [
                    sum(day_durations) / len(day_durations),  # avg
                    day_durations[int(len(day_durations) * 0.95)],  # p95
                    len(day_requests)  # count
                ]

        # Cache performance
        cache_hits = len([r for r in period_requests if r.cache_hit])
        cache_performance = {
            "hit_rate": (cache_hits / len(period_requests)) * 100,
            "total_requests": len(period_requests),
            "cache_hits": cache_hits,
            "cache_misses": len(period_requests) - cache_hits
        }

        return PerformanceAnalytics(
            period_days=days,
            avg_response_time_ms=avg_response_time_ms,
            p95_response_time_ms=p95_response_time_ms,
            p99_response_time_ms=p99_response_time_ms,
            slowest_endpoints=slowest_endpoints,
            performance_trends=performance_trends,
            cache_performance=cache_performance
        )

    except Exception as e:
        logger.error(f"Error generating performance analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate performance analytics")


@router.get("/clients", response_model=List[ClientAnalytics])
async def get_client_analytics(days: int = Query(7, ge=1, le=90, description="Analysis period in days")):
    """Get analytics per client."""
    try:
        monitor = get_api_monitor()
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        # Filter requests for the period
        period_requests = [
            r for r in monitor.request_tracker.requests
            if r.timestamp >= cutoff_time and r.client_id
        ]

        # Group by client
        client_data = {}
        for request in period_requests:
            client_id = request.client_id
            if client_id not in client_data:
                client_data[client_id] = {
                    "requests": [],
                    "first_seen": request.timestamp,
                    "last_seen": request.timestamp
                }

            client_data[client_id]["requests"].append(request)
            client_data[client_id]["last_seen"] = max(
                client_data[client_id]["last_seen"],
                request.timestamp
            )

        # Generate client analytics
        client_analytics = []
        for client_id, data in client_data.items():
            requests = data["requests"]
            total_requests = len(requests)
            durations = [r.duration_ms for r in requests]
            errors = len([r for r in requests if r.status_code >= 400])

            # Get top endpoints for this client
            endpoint_counts = {}
            for request in requests:
                endpoint = f"{request.method} {request.path}"
                endpoint_counts[endpoint] = endpoint_counts.get(endpoint, 0) + 1

            top_endpoints = [
                endpoint for endpoint, count in
                sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            # Get quota utilization (mock data - would come from rate limiter)
            quota_utilization = min((total_requests / 1000) * 100, 100)  # Assume 1000 request limit

            client_analytics.append(ClientAnalytics(
                client_id=client_id,
                total_requests=total_requests,
                avg_response_time_ms=sum(durations) / len(durations) if durations else 0,
                error_rate=(errors / total_requests) * 100 if total_requests > 0 else 0,
                top_endpoints=top_endpoints,
                first_seen=data["first_seen"],
                last_seen=data["last_seen"],
                quota_utilization=quota_utilization
            ))

        # Sort by total requests
        client_analytics.sort(key=lambda x: x.total_requests, reverse=True)

        return client_analytics

    except Exception as e:
        logger.error(f"Error generating client analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate client analytics")


@router.get("/dashboard")
async def get_dashboard_data(days: int = Query(7, ge=1, le=30, description="Analysis period in days")):
    """Get comprehensive dashboard data."""
    try:
        # Get dashboard data from monitor
        monitor = get_api_monitor()
        dashboard_data = monitor.get_dashboard_data()

        # Add additional analytics
        usage_analytics = await get_usage_analytics(days)
        performance_analytics = await get_performance_analytics(days)

        return {
            "system_health": dashboard_data["system_health"],
            "real_time_metrics": dashboard_data["metrics"],
            "usage_analytics": usage_analytics.dict(),
            "performance_analytics": performance_analytics.dict(),
            "recent_alerts": dashboard_data["recent_alerts"],
            "active_integrations": {
                "shopify": dashboard_data["system_health"].get("status") != "unhealthy",
                "redis": True,  # Would check actual Redis status
                "llm_service": True  # Would check actual LLM service status
            }
        }

    except Exception as e:
        logger.error(f"Error generating dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate dashboard data")


@router.get("/reports/summary")
async def get_summary_report(days: int = Query(30, ge=1, le=90, description="Report period in days")):
    """Generate a summary report."""
    try:
        # Get analytics data
        usage_analytics = await get_usage_analytics(days)
        performance_analytics = await get_performance_analytics(days)

        # Calculate key metrics
        total_requests = usage_analytics.total_requests
        error_rate = (sum(usage_analytics.error_trends.values()) / len(usage_analytics.error_trends)) if usage_analytics.error_trends else 0
        avg_response_time = performance_analytics.avg_response_time_ms
        cache_hit_rate = performance_analytics.cache_performance.get("hit_rate", 0)

        # Determine overall health
        health_status = "healthy"
        if error_rate > 10 or avg_response_time > 2000:
            health_status = "unhealthy"
        elif error_rate > 5 or avg_response_time > 1000:
            health_status = "degraded"

        # Generate recommendations
        recommendations = []
        if error_rate > 5:
            recommendations.append("High error rate detected - investigate error patterns")
        if avg_response_time > 1000:
            recommendations.append("Slow response times - consider optimization")
        if cache_hit_rate < 50:
            recommendations.append("Low cache hit rate - review caching strategy")
        if total_requests < 100:
            recommendations.append("Low usage - consider marketing or feature improvements")

        return {
            "report_period_days": days,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "health_status": health_status,
                "total_requests": total_requests,
                "unique_users": usage_analytics.unique_users,
                "average_error_rate": round(error_rate, 2),
                "average_response_time_ms": round(avg_response_time, 2),
                "cache_hit_rate": round(cache_hit_rate, 2)
            },
            "top_metrics": {
                "busiest_endpoint": usage_analytics.top_endpoints[0] if usage_analytics.top_endpoints else None,
                "slowest_endpoint": performance_analytics.slowest_endpoints[0] if performance_analytics.slowest_endpoints else None,
                "peak_usage_hour": max(usage_analytics.usage_by_hour.items(), key=lambda x: x[1])[0] if usage_analytics.usage_by_hour else None
            },
            "recommendations": recommendations,
            "trends": {
                "error_trend": "improving" if list(usage_analytics.error_trends.values())[-5:] and list(usage_analytics.error_trends.values())[-5:][0] > list(usage_analytics.error_trends.values())[-5:][-1] else "stable",
                "usage_trend": "increasing" if len(usage_analytics.usage_by_hour) > 0 else "stable"
            }
        }

    except Exception as e:
        logger.error(f"Error generating summary report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate summary report")


@router.get("/conversations/summary")
async def get_conversation_summary(
    days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
    db: Session = Depends(get_db)
):
    """Get conversation analytics summary."""
    try:
        summary = await conversation_analytics_service.get_conversation_metrics_summary(days, db)
        return summary

    except Exception as e:
        logger.error(f"Error getting conversation summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation summary")


@router.get("/conversations/topics")
async def get_conversation_topics(
    days: int = Query(7, ge=1, le=30, description="Analysis period in days"),
    db: Session = Depends(get_db)
):
    """Get top conversation topics."""
    try:
        topics = await conversation_analytics_service.get_top_topics(days, db)
        return {"topics": topics, "period_days": days}

    except Exception as e:
        logger.error(f"Error getting conversation topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation topics")


@router.get("/conversations/resolution-trends")
async def get_resolution_trends(
    days: int = Query(30, ge=1, le=90, description="Analysis period in days"),
    db: Session = Depends(get_db)
):
    """Get conversation resolution trends over time."""
    try:
        trends = await conversation_analytics_service.get_resolution_trends(days, db)
        return {"trends": trends, "period_days": days}

    except Exception as e:
        logger.error(f"Error getting resolution trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resolution trends")