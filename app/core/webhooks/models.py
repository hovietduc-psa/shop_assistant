"""
Webhook data models.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class WebhookStatus(Enum):
    """Webhook status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    FAILED = "failed"


class DeliveryStatus(Enum):
    """Webhook delivery status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    TIMEOUT = "timeout"


class WebhookEvent(BaseModel):
    """Webhook event data."""
    id: str
    event_type: str
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    version: str = "1.0"
    signature: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookSubscription(BaseModel):
    """Webhook subscription configuration."""
    id: str
    url: HttpUrl
    event_types: List[str]
    secret: Optional[str] = None
    status: WebhookStatus = WebhookStatus.ACTIVE
    headers: Dict[str, str] = Field(default_factory=dict)
    retry_policy: Dict[str, Any] = Field(default_factory=lambda: {
        "max_retries": 3,
        "retry_delay": 60,
        "backoff_multiplier": 2.0
    })
    timeout: int = 30
    created_at: datetime
    updated_at: datetime
    last_delivery: Optional[datetime] = None
    delivery_count: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookDelivery(BaseModel):
    """Webhook delivery attempt."""
    id: str
    subscription_id: str
    event_id: str
    status: DeliveryStatus
    attempts: int
    max_retries: int
    created_at: datetime
    delivered_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class WebhookStats(BaseModel):
    """Webhook statistics."""
    total_subscriptions: int
    active_subscriptions: int
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    pending_deliveries: int
    avg_delivery_time_ms: float
    success_rate: float