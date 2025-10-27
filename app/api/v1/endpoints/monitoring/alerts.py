"""
API monitoring and alerting endpoints.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from loguru import logger

from app.db.session import get_db
from app.core.config import settings


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertType(Enum):
    """Types of alerts."""
    SYSTEM = "system"
    API = "api"
    DATABASE = "database"
    REDIS = "redis"
    LLM_SERVICE = "llm_service"
    RATE_LIMIT = "rate_limit"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    type: AlertType
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    source: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    suppression_duration: Optional[int] = None  # minutes

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['type'] = self.type.value
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        if self.timestamp:
            data['timestamp'] = self.timestamp.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data


class AlertRule(BaseModel):
    """Alert rule configuration."""
    name: str
    type: AlertType
    severity: AlertSeverity
    condition: str
    threshold: float
    duration: int  # minutes
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = {}


class AlertManager:
    """Manages alerts and alert rules."""

    def __init__(self):
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_rules: Dict[str, AlertRule] = {}
        self.max_history = 10000

    def create_alert(self,
                    type: AlertType,
                    severity: AlertSeverity,
                    title: str,
                    description: str,
                    source: str,
                    metadata: Dict[str, Any] = None) -> Alert:
        """Create a new alert."""
        alert_id = f"{type.value}_{source}_{int(datetime.utcnow().timestamp())}"

        alert = Alert(
            id=alert_id,
            type=type,
            severity=severity,
            status=AlertStatus.ACTIVE,
            title=title,
            description=description,
            source=source,
            timestamp=datetime.utcnow(),
            metadata=metadata or {}
        )

        # Check for existing similar alert
        existing_key = f"{type.value}_{source}"
        if existing_key in self.active_alerts:
            existing_alert = self.active_alerts[existing_key]
            if existing_alert.status == AlertStatus.ACTIVE:
                logger.info(f"Similar alert already active: {existing_alert.id}")
                return existing_alert

        self.active_alerts[existing_key] = alert
        self.alert_history.append(alert)

        # Cleanup old history
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

        logger.warning(f"Alert created: {alert.id} - {title}")
        return alert

    def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resolve an alert."""
        # Find alert in active alerts
        for key, alert in self.active_alerts.items():
            if alert.id == alert_id and alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()
                alert.resolved_by = resolved_by

                # Move to history (already there)
                del self.active_alerts[key]

                logger.info(f"Alert resolved: {alert_id} by {resolved_by}")
                return True

        return False

    def suppress_alert(self, alert_id: str, duration_minutes: int = 60) -> bool:
        """Suppress an alert for a duration."""
        for key, alert in self.active_alerts.items():
            if alert.id == alert_id and alert.status == AlertStatus.ACTIVE:
                alert.status = AlertStatus.SUPPRESSED
                alert.suppression_duration = duration_minutes

                logger.info(f"Alert suppressed: {alert_id} for {duration_minutes} minutes")
                return True

        return False

    def get_active_alerts(self, severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by severity."""
        alerts = list(self.active_alerts.values())

        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]

        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)

    def get_alert_history(self, limit: int = 100, hours: int = 24) -> List[Alert]:
        """Get alert history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        filtered_alerts = [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff_time
        ]

        return sorted(filtered_alerts, key=lambda x: x.timestamp, reverse=True)[:limit]

    def check_system_health(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check system metrics and create alerts if needed."""
        alerts = []

        # CPU usage alert
        cpu_usage = metrics.get("cpu_usage_percent", 0)
        if cpu_usage > 90:
            alerts.append(self.create_alert(
                type=AlertType.SYSTEM,
                severity=AlertSeverity.HIGH if cpu_usage > 95 else AlertSeverity.MEDIUM,
                title="High CPU Usage",
                description=f"CPU usage is {cpu_usage}%",
                source="system_monitor",
                metadata={"cpu_usage": cpu_usage}
            ))

        # Memory usage alert
        memory_usage = metrics.get("memory_usage_percent", 0)
        if memory_usage > 85:
            alerts.append(self.create_alert(
                type=AlertType.SYSTEM,
                severity=AlertSeverity.HIGH if memory_usage > 95 else AlertSeverity.MEDIUM,
                title="High Memory Usage",
                description=f"Memory usage is {memory_usage}%",
                source="system_monitor",
                metadata={"memory_usage": memory_usage}
            ))

        # Disk usage alert
        disk_usage = metrics.get("disk_usage_percent", 0)
        if disk_usage > 80:
            alerts.append(self.create_alert(
                type=AlertType.SYSTEM,
                severity=AlertSeverity.CRITICAL if disk_usage > 95 else AlertSeverity.HIGH,
                title="High Disk Usage",
                description=f"Disk usage is {disk_usage}%",
                source="system_monitor",
                metadata={"disk_usage": disk_usage}
            ))

        return alerts

    def cleanup_old_alerts(self):
        """Clean up old resolved alerts."""
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        # Remove resolved alerts older than 7 days from history
        self.alert_history = [
            alert for alert in self.alert_history
            if not (alert.status == AlertStatus.RESOLVED and
                   alert.resolved_at and alert.resolved_at < cutoff_time)
        ]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        active_alerts = self.get_active_alerts()

        severity_counts = {}
        type_counts = {}

        for alert in active_alerts:
            severity_counts[alert.severity.value] = severity_counts.get(alert.severity.value, 0) + 1
            type_counts[alert.type.value] = type_counts.get(alert.type.value, 0) + 1

        recent_history = self.get_alert_history(hours=24)

        return {
            "active_alerts": len(active_alerts),
            "severity_breakdown": severity_counts,
            "type_breakdown": type_counts,
            "alerts_last_24h": len(recent_history),
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled])
        }


# Global alert manager
alert_manager = AlertManager()


# Create router
router = APIRouter()


@router.get("/alerts", response_model=Dict[str, Any])
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query("active", description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of alerts"),
    db: Session = Depends(get_db)
):
    """Get alerts with optional filtering."""
    try:
        # Parse severity filter
        severity_filter = None
        if severity:
            try:
                severity_filter = AlertSeverity(severity)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid severity value")

        if status == "active":
            alerts = alert_manager.get_active_alerts(severity_filter)
        else:
            alerts = alert_manager.get_alert_history(limit=limit)

        return {
            "alerts": [alert.to_dict() for alert in alerts],
            "total": len(alerts),
            "filters": {
                "severity": severity,
                "status": status,
                "limit": limit
            }
        }

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolved_by: str = "user",
    db: Session = Depends(get_db)
):
    """Resolve an alert."""
    try:
        success = alert_manager.resolve_alert(alert_id, resolved_by)

        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")

        return {
            "message": "Alert resolved successfully",
            "alert_id": alert_id,
            "resolved_by": resolved_by,
            "resolved_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/suppress")
async def suppress_alert(
    alert_id: str,
    duration_minutes: int = Query(60, ge=1, le=1440, description="Suppression duration in minutes"),
    db: Session = Depends(get_db)
):
    """Suppress an alert for a duration."""
    try:
        success = alert_manager.suppress_alert(alert_id, duration_minutes)

        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already resolved")

        return {
            "message": "Alert suppressed successfully",
            "alert_id": alert_id,
            "duration_minutes": duration_minutes,
            "suppressed_until": (datetime.utcnow() + timedelta(minutes=duration_minutes)).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error suppressing alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/statistics", response_model=Dict[str, Any])
async def get_alert_statistics(db: Session = Depends(get_db)):
    """Get alert statistics."""
    try:
        return alert_manager.get_alert_statistics()

    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/test")
async def create_test_alert(
    background_tasks: BackgroundTasks,
    type: str = Query("system", description="Alert type"),
    severity: str = Query("medium", description="Alert severity"),
    db: Session = Depends(get_db)
):
    """Create a test alert for monitoring purposes."""
    try:
        alert_type = AlertType(type)
        alert_severity = AlertSeverity(severity)

        alert = alert_manager.create_alert(
            type=alert_type,
            severity=alert_severity,
            title="Test Alert",
            description="This is a test alert created via API",
            source="api_test",
            metadata={"test": True, "created_at": datetime.utcnow().isoformat()}
        )

        # Schedule automatic resolution after 5 minutes
        background_tasks.add_task(
            lambda: asyncio.sleep(300) or alert_manager.resolve_alert(alert.id, "auto_resolve")
        )

        return {
            "message": "Test alert created successfully",
            "alert": alert.to_dict(),
            "auto_resolve_in": "5 minutes"
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating test alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_alert_manager() -> AlertManager:
    """Get the global alert manager."""
    return alert_manager