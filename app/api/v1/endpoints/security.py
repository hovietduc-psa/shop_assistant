"""
Security API endpoints for enterprise-grade security management.
Provides security monitoring, configuration, and threat analysis.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import logging

from app.middleware.security_middleware import get_current_user_security, require_admin_user
from app.services.enterprise_security import (
    EnterpriseSecurityManager, SecurityConfig, RateLimitRule,
    ThreatType, SecurityLevel
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

# Global security manager instance
security_manager: Optional[EnterpriseSecurityManager] = None


# Pydantic models for request/response
class SecurityDashboardResponse(BaseModel):
    """Security dashboard response model."""
    status: str
    configuration: Dict[str, Any]
    rate_limiting: Dict[str, Any]
    threat_detection: Dict[str, Any]
    performance: Dict[str, Any]


class SecurityEventResponse(BaseModel):
    """Security event response model."""
    event_id: str
    threat_type: str
    security_level: str
    source_ip: str
    endpoint: str
    timestamp: datetime
    risk_score: float
    blocked: bool
    details: Dict[str, Any]


class RateLimitRuleCreate(BaseModel):
    """Rate limit rule creation model."""
    name: str = Field(..., description="Rule name")
    requests_per_window: int = Field(..., gt=0, description="Number of requests allowed")
    window_seconds: int = Field(..., gt=0, description="Time window in seconds")
    block_duration_seconds: int = Field(300, ge=0, description="Block duration in seconds")
    scope: str = Field("ip", description="Rule scope: ip, user, endpoint, global")
    priority: int = Field(0, description="Rule priority")
    conditions: Dict[str, Any] = Field(default_factory=dict, description="Rule conditions")


class IPBlockRequest(BaseModel):
    """IP block request model."""
    ip_address: str = Field(..., description="IP address to block")
    duration_seconds: int = Field(3600, gt=0, description="Block duration in seconds")
    reason: str = Field("Security violation", description="Block reason")


class UserBlockRequest(BaseModel):
    """User block request model."""
    user_id: str = Field(..., description="User ID to block")
    duration_seconds: int = Field(3600, gt=0, description="Block duration in seconds")
    reason: str = Field("Security violation", description="Block reason")


class SecurityConfigUpdate(BaseModel):
    """Security configuration update model."""
    enabled_features: List[str] = Field(default_factory=list)
    ip_whitelist: List[str] = Field(default_factory=list)
    ip_blacklist: List[str] = Field(default_factory=list)
    threat_thresholds: Dict[str, float] = Field(default_factory=dict)


def get_security_manager() -> EnterpriseSecurityManager:
    """Get or create security manager instance."""
    global security_manager
    if security_manager is None:
        security_manager = EnterpriseSecurityManager()
    return security_manager


@router.get("/dashboard", response_model=SecurityDashboardResponse)
async def get_security_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user_security)
):
    """Get comprehensive security dashboard."""
    try:
        manager = get_security_manager()
        dashboard_data = await manager.get_security_dashboard()
        return SecurityDashboardResponse(**dashboard_data)
    except Exception as e:
        logger.error(f"Failed to get security dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security dashboard"
        )


@router.get("/stats")
async def get_security_stats(
    current_user: Dict[str, Any] = Depends(get_current_user_security)
):
    """Get detailed security statistics."""
    try:
        manager = get_security_manager()

        # Get statistics from all components
        rate_stats = await manager.rate_limiter.get_rate_limit_stats()
        threat_stats = await manager.threat_detector.get_security_stats()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "rate_limiting": rate_stats,
            "threat_detection": threat_stats,
            "summary": {
                "total_threats_24h": threat_stats.get("total_events_24h", 0),
                "blocked_events_24h": threat_stats.get("blocked_events", 0),
                "average_risk_score": threat_stats.get("average_risk_score", 0),
                "active_rate_limits": rate_stats.get("active_rate_limits", 0),
                "blocked_ips": rate_stats.get("blocked_ips", 0)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get security stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security statistics"
        )


@router.get("/events")
async def get_security_events(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    threat_type: Optional[str] = Query(None),
    security_level: Optional[str] = Query(None),
    min_risk_score: Optional[float] = Query(None, ge=0, le=1),
    hours: int = Query(24, ge=1, le=168),  # Last 24 hours by default, max 1 week
    current_user: Dict[str, Any] = Depends(get_current_user_security)
):
    """Get security events with filtering options."""
    try:
        manager = get_security_manager()

        # Calculate time filter
        since = datetime.utcnow() - timedelta(hours=hours)

        # Filter events
        events = manager.threat_detector.security_events

        # Apply filters
        filtered_events = []
        for event in events:
            # Time filter
            if event.timestamp < since:
                continue

            # Threat type filter
            if threat_type and event.threat_type.value != threat_type:
                continue

            # Security level filter
            if security_level and event.security_level.value != security_level:
                continue

            # Risk score filter
            if min_risk_score is not None and event.risk_score < min_risk_score:
                continue

            filtered_events.append(event)

        # Sort by timestamp (newest first)
        filtered_events.sort(key=lambda x: x.timestamp, reverse=True)

        # Apply pagination
        paginated_events = filtered_events[offset:offset + limit]

        # Convert to response models
        event_responses = [
            SecurityEventResponse(
                event_id=event.event_id,
                threat_type=event.threat_type.value,
                security_level=event.security_level.value,
                source_ip=event.source_ip,
                endpoint=event.endpoint,
                timestamp=event.timestamp,
                risk_score=event.risk_score,
                blocked=event.blocked,
                details=event.details
            )
            for event in paginated_events
        ]

        return {
            "events": event_responses,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(filtered_events),
                "has_more": offset + limit < len(filtered_events)
            },
            "filters": {
                "threat_type": threat_type,
                "security_level": security_level,
                "min_risk_score": min_risk_score,
                "hours": hours
            }
        }

    except Exception as e:
        logger.error(f"Failed to get security events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security events"
        )


@router.get("/rate-limits")
async def get_rate_limits(
    current_user: Dict[str, Any] = Depends(get_current_user_security)
):
    """Get current rate limiting rules and statistics."""
    try:
        manager = get_security_manager()
        stats = await manager.rate_limiter.get_rate_limit_stats()

        return {
            "statistics": stats,
            "custom_rules": [
                {
                    "name": rule.name,
                    "requests_per_window": rule.requests_per_window,
                    "window_seconds": rule.window_seconds,
                    "block_duration_seconds": rule.block_duration_seconds,
                    "scope": rule.scope,
                    "priority": rule.priority,
                    "conditions": rule.conditions
                }
                for rule in manager.rate_limiter.custom_rules.values()
            ],
            "default_rules": [
                {
                    "name": "default",
                    "requests_per_window": manager.config.default_rate_limit.requests_per_window,
                    "window_seconds": manager.config.default_rate_limit.window_seconds,
                    "scope": "ip"
                },
                {
                    "name": "authenticated",
                    "requests_per_window": manager.config.authenticated_rate_limit.requests_per_window,
                    "window_seconds": manager.config.authenticated_rate_limit.window_seconds,
                    "scope": "user"
                },
                {
                    "name": "admin",
                    "requests_per_window": manager.config.admin_rate_limit.requests_per_window,
                    "window_seconds": manager.config.admin_rate_limit.window_seconds,
                    "scope": "user"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get rate limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rate limiting information"
        )


@router.post("/rate-limits/rules")
async def create_rate_limit_rule(
    rule: RateLimitRuleCreate,
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Create a new rate limiting rule."""
    try:
        manager = get_security_manager()

        # Create rule object
        rate_limit_rule = RateLimitRule(
            name=rule.name,
            requests_per_window=rule.requests_per_window,
            window_seconds=rule.window_seconds,
            block_duration_seconds=rule.block_duration_seconds,
            scope=rule.scope,
            priority=rule.priority,
            conditions=rule.conditions
        )

        # Add rule
        await manager.rate_limiter.add_custom_rule(rate_limit_rule)

        return {
            "message": f"Rate limit rule '{rule.name}' created successfully",
            "rule": {
                "name": rule.name,
                "requests_per_window": rule.requests_per_window,
                "window_seconds": rule.window_seconds,
                "block_duration_seconds": rule.block_duration_seconds,
                "scope": rule.scope,
                "priority": rule.priority
            }
        }
    except Exception as e:
        logger.error(f"Failed to create rate limit rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rate limit rule"
        )


@router.delete("/rate-limits/rules/{rule_name}")
async def delete_rate_limit_rule(
    rule_name: str,
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Delete a rate limiting rule."""
    try:
        manager = get_security_manager()

        # Check if rule exists
        if rule_name not in manager.rate_limiter.custom_rules:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rate limit rule '{rule_name}' not found"
            )

        # Remove rule
        await manager.rate_limiter.remove_custom_rule(rule_name)

        return {"message": f"Rate limit rule '{rule_name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete rate limit rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete rate limit rule"
        )


@router.post("/block/ip")
async def block_ip_address(
    block_request: IPBlockRequest,
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Block an IP address."""
    try:
        manager = get_security_manager()

        # Validate IP address
        import ipaddress
        try:
            ipaddress.ip_address(block_request.ip_address)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid IP address format"
            )

        # Block IP
        await manager.rate_limiter.block_ip(
            block_request.ip_address,
            block_request.duration_seconds,
            block_request.reason
        )

        return {
            "message": f"IP address {block_request.ip_address} blocked successfully",
            "ip_address": block_request.ip_address,
            "duration_seconds": block_request.duration_seconds,
            "reason": block_request.reason
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to block IP address: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to block IP address"
        )


@router.post("/block/user")
async def block_user(
    block_request: UserBlockRequest,
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Block a user."""
    try:
        manager = get_security_manager()

        # Block user
        await manager.rate_limiter.block_user(
            block_request.user_id,
            block_request.duration_seconds,
            block_request.reason
        )

        return {
            "message": f"User {block_request.user_id} blocked successfully",
            "user_id": block_request.user_id,
            "duration_seconds": block_request.duration_seconds,
            "reason": block_request.reason
        }
    except Exception as e:
        logger.error(f"Failed to block user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to block user"
        )


@router.get("/configuration")
async def get_security_configuration(
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Get current security configuration."""
    try:
        manager = get_security_manager()

        return {
            "enabled_features": list(manager.config.enabled_features),
            "ip_whitelist": list(manager.config.ip_whitelist),
            "ip_blacklist": list(manager.config.ip_blacklist),
            "threat_thresholds": manager.config.threat_thresholds,
            "redis_url": manager.config.redis_url,
            "default_rate_limit": {
                "requests_per_window": manager.config.default_rate_limit.requests_per_window,
                "window_seconds": manager.config.default_rate_limit.window_seconds,
                "block_duration_seconds": manager.config.default_rate_limit.block_duration_seconds
            }
        }
    except Exception as e:
        logger.error(f"Failed to get security configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security configuration"
        )


@router.put("/configuration")
async def update_security_configuration(
    config_update: SecurityConfigUpdate,
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Update security configuration."""
    try:
        manager = get_security_manager()

        # Update enabled features
        if config_update.enabled_features:
            manager.config.enabled_features = set(config_update.enabled_features)

        # Update IP whitelist
        if config_update.ip_whitelist is not None:
            manager.config.ip_whitelist = set(config_update.ip_whitelist)

        # Update IP blacklist
        if config_update.ip_blacklist is not None:
            manager.config.ip_blacklist = set(config_update.ip_blacklist)

        # Update threat thresholds
        if config_update.threat_thresholds:
            manager.config.threat_thresholds.update(config_update.threat_thresholds)

        return {
            "message": "Security configuration updated successfully",
            "configuration": {
                "enabled_features": list(manager.config.enabled_features),
                "ip_whitelist_size": len(manager.config.ip_whitelist),
                "ip_blacklist_size": len(manager.config.ip_blacklist),
                "threat_thresholds": manager.config.threat_thresholds
            }
        }
    except Exception as e:
        logger.error(f"Failed to update security configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update security configuration"
        )


@router.post("/test-attack")
async def test_security_detection(
    background_tasks: BackgroundTasks,
    attack_type: str = Query(..., description="Type of attack to simulate"),
    current_user: Dict[str, Any] = Depends(require_admin_user)
):
    """Test security detection by simulating attacks (admin only)."""
    try:
        manager = get_security_manager()

        # Validate attack type
        valid_attacks = ["sql_injection", "xss", "path_traversal", "brute_force", "ddos"]
        if attack_type not in valid_attacks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid attack type. Valid options: {valid_attacks}"
            )

        # Simulate attack in background
        background_tasks.add_task(
            simulate_attack,
            manager,
            attack_type
        )

        return {
            "message": f"Security test for {attack_type} initiated",
            "test_type": attack_type,
            "status": "running"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate security test: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate security test"
        )


async def simulate_attack(manager: EnterpriseSecurityManager, attack_type: str):
    """Simulate security attack for testing purposes."""
    try:
        from fastapi import Request
        from unittest.mock import Mock

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/test/endpoint"
        mock_request.method = "GET"
        mock_request.headers = {"User-Agent": "SecurityTestBot/1.0"}
        mock_request.query_params = {}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.100"

        # Simulate different attack types
        if attack_type == "sql_injection":
            mock_request.query_params = {"id": "1' OR '1'='1"}
            mock_request.url.path = "/api/v1/products"
        elif attack_type == "xss":
            mock_request.query_params = {"search": "<script>alert('xss')</script>"}
            mock_request.url.path = "/api/v1/search"
        elif attack_type == "path_traversal":
            mock_request.url.path = "/api/v1/files/../../../etc/passwd"
        elif attack_type == "brute_force":
            mock_request.url.path = "/api/v1/auth/login"
            # Simulate multiple attempts
            for i in range(15):
                await manager.threat_detector.analyze_request(mock_request)
        elif attack_type == "ddos":
            # Simulate rapid requests
            for i in range(120):
                await manager.threat_detector.analyze_request(mock_request)

        if attack_type != "brute_force" and attack_type != "ddos":
            # Single request for other attack types
            await manager.threat_detector.analyze_request(mock_request)

        logger.info(f"Security test simulation completed for {attack_type}")

    except Exception as e:
        logger.error(f"Security test simulation failed: {e}")


@router.get("/health")
async def security_health_check():
    """Security system health check."""
    try:
        manager = get_security_manager()

        # Check if security manager is initialized
        is_initialized = manager._initialized

        # Check Redis connectivity
        redis_connected = False
        if manager.rate_limiter.redis_client:
            try:
                await manager.rate_limiter.redis_client.ping()
                redis_connected = True
            except:
                pass

        # Check system status
        health_status = "healthy" if is_initialized and redis_connected else "degraded"

        return {
            "status": health_status,
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "security_manager": "operational" if is_initialized else "initializing",
                "rate_limiter": "operational",
                "threat_detector": "operational",
                "redis": "connected" if redis_connected else "disconnected"
            },
            "metrics": {
                "enabled_features": len(manager.config.enabled_features),
                "custom_rules": len(manager.rate_limiter.custom_rules),
                "security_events_24h": len([
                    e for e in manager.threat_detector.security_events
                    if e.timestamp > datetime.utcnow() - timedelta(hours=24)
                ])
            }
        }
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }