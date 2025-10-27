"""
Webhook management system.
"""

import asyncio
import hmac
import hashlib
import json
import time
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import httpx
from loguru import logger

from .models import (
    WebhookEvent, WebhookSubscription, WebhookDelivery,
    WebhookStatus, DeliveryStatus, WebhookStats
)


class RetryPolicy(Enum):
    """Retry policies."""
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIXED = "fixed"


@dataclass
class DeliveryResult:
    """Result of webhook delivery attempt."""
    success: bool
    status_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    should_retry: bool = False
    next_retry_delay: int = 0


class WebhookManager:
    """Manages webhook subscriptions and deliveries."""

    def __init__(self):
        """Initialize webhook manager."""
        self.subscriptions: Dict[str, WebhookSubscription] = {}
        self.deliveries: Dict[str, List[WebhookDelivery]] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.client = httpx.AsyncClient(timeout=30.0)
        self.delivery_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.max_concurrent_deliveries = 10
        self.cleanup_interval = 300  # 5 minutes

    async def start(self):
        """Start the webhook manager."""
        if self.is_running:
            return

        self.is_running = True
        asyncio.create_task(self._delivery_worker())
        asyncio.create_task(self._cleanup_worker())
        logger.info("Webhook manager started")

    async def stop(self):
        """Stop the webhook manager."""
        self.is_running = False
        await self.client.aclose()
        logger.info("Webhook manager stopped")

    async def create_subscription(self,
                                 url: str,
                                 event_types: List[str],
                                 secret: Optional[str] = None,
                                 headers: Optional[Dict[str, str]] = None,
                                 retry_policy: Optional[Dict[str, Any]] = None) -> WebhookSubscription:
        """Create a new webhook subscription."""
        import uuid

        subscription_id = f"wh_{uuid.uuid4().hex[:16]}"
        now = datetime.utcnow()

        subscription = WebhookSubscription(
            id=subscription_id,
            url=url,
            event_types=event_types,
            secret=secret,
            headers=headers or {},
            retry_policy=retry_policy or {
                "max_retries": 3,
                "retry_delay": 60,
                "backoff_multiplier": 2.0
            },
            created_at=now,
            updated_at=now
        )

        self.subscriptions[subscription_id] = subscription
        self.deliveries[subscription_id] = []

        logger.info(f"Created webhook subscription {subscription_id} for events {event_types}")
        return subscription

    async def update_subscription(self,
                                 subscription_id: str,
                                 **kwargs) -> Optional[WebhookSubscription]:
        """Update an existing webhook subscription."""
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return None

        # Update allowed fields
        for field, value in kwargs.items():
            if hasattr(subscription, field):
                setattr(subscription, field, value)

        subscription.updated_at = datetime.utcnow()
        logger.info(f"Updated webhook subscription {subscription_id}")
        return subscription

    async def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a webhook subscription."""
        if subscription_id not in self.subscriptions:
            return False

        del self.subscriptions[subscription_id]
        if subscription_id in self.deliveries:
            del self.deliveries[subscription_id]

        logger.info(f"Deleted webhook subscription {subscription_id}")
        return True

    async def trigger_event(self, event_type: str, data: Dict[str, Any], source: str = "system") -> str:
        """Trigger a webhook event."""
        import uuid

        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        event = WebhookEvent(
            id=event_id,
            event_type=event_type,
            source=source,
            timestamp=datetime.utcnow(),
            data=data
        )

        # Find matching subscriptions
        matching_subscriptions = [
            sub for sub in self.subscriptions.values()
            if sub.status == WebhookStatus.ACTIVE and event_type in sub.event_types
        ]

        # Queue deliveries
        for subscription in matching_subscriptions:
            delivery_id = f"del_{uuid.uuid4().hex[:16]}"
            delivery = WebhookDelivery(
                id=delivery_id,
                subscription_id=subscription.id,
                event_id=event_id,
                status=DeliveryStatus.PENDING,
                attempts=0,
                max_retries=subscription.retry_policy.get("max_retries", 3),
                created_at=datetime.utcnow()
            )

            self.deliveries[subscription.id].append(delivery)

            # Add to delivery queue
            await self.delivery_queue.put((subscription, event, delivery))

        # Call local event handlers
        await self._call_event_handlers(event_type, event)

        logger.info(f"Triggered event {event_type} to {len(matching_subscriptions)} subscriptions")
        return event_id

    async def register_event_handler(self, event_type: str, handler: Callable):
        """Register a local event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"Registered event handler for {event_type}")

    async def _call_event_handlers(self, event_type: str, event: WebhookEvent):
        """Call registered event handlers."""
        handlers = self.event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

    async def _delivery_worker(self):
        """Background worker for processing webhook deliveries."""
        semaphore = asyncio.Semaphore(self.max_concurrent_deliveries)

        while self.is_running:
            try:
                subscription, event, delivery = await asyncio.wait_for(
                    self.delivery_queue.get(),
                    timeout=1.0
                )

                # Process delivery with semaphore limit
                asyncio.create_task(self._process_delivery_with_semaphore(
                    semaphore, subscription, event, delivery
                ))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in delivery worker: {e}")

    async def _process_delivery_with_semaphore(self,
                                              semaphore: asyncio.Semaphore,
                                              subscription: WebhookSubscription,
                                              event: WebhookEvent,
                                              delivery: WebhookDelivery):
        """Process webhook delivery with semaphore control."""
        async with semaphore:
            await self._process_delivery(subscription, event, delivery)

    async def _process_delivery(self,
                              subscription: WebhookSubscription,
                              event: WebhookEvent,
                              delivery: WebhookDelivery):
        """Process a single webhook delivery."""
        try:
            # Prepare payload
            payload = {
                "id": event.id,
                "event": event.event_type,
                "source": event.source,
                "timestamp": event.timestamp.isoformat(),
                "data": event.data,
                "version": event.version
            }

            payload_str = json.dumps(payload, separators=(',', ':'))

            # Generate signature if secret is provided
            headers = subscription.headers.copy()
            if subscription.secret:
                signature = self._generate_signature(payload_str, subscription.secret)
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            # Make HTTP request
            result = await self._make_http_request(
                url=str(subscription.url),
                method="POST",
                payload=payload_str,
                headers=headers,
                timeout=subscription.timeout
            )

            # Update delivery record
            delivery.attempts += 1
            delivery.duration_ms = result.duration_ms
            delivery.response_status = result.status_code
            delivery.response_body = result.response_body
            delivery.delivered_at = datetime.utcnow()

            if result.success:
                delivery.status = DeliveryStatus.SUCCESS
                subscription.last_delivery = delivery.delivered_at
                subscription.delivery_count += 1
                logger.info(f"Webhook delivery successful: {delivery.id}")
            else:
                delivery.error_message = result.error_message
                if result.should_retry and delivery.attempts < delivery.max_retries:
                    delivery.status = DeliveryStatus.RETRY
                    delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=result.next_retry_delay)
                    await self._schedule_retry(subscription, event, delivery)
                else:
                    delivery.status = DeliveryStatus.FAILED
                    logger.error(f"Webhook delivery failed permanently: {delivery.id}")

        except Exception as e:
            delivery.attempts += 1
            delivery.error_message = str(e)
            delivery.status = DeliveryStatus.FAILED
            logger.error(f"Webhook delivery error: {delivery.id} - {e}")

    async def _make_http_request(self,
                               url: str,
                               method: str,
                               payload: str,
                               headers: Dict[str, str],
                               timeout: int) -> DeliveryResult:
        """Make HTTP request to webhook URL."""
        start_time = time.time()

        try:
            response = await self.client.request(
                method=method,
                url=url,
                content=payload.encode(),
                headers={
                    **headers,
                    "Content-Type": "application/json",
                    "User-Agent": "ShopAssistant-Webhooks/1.0"
                },
                timeout=timeout
            )

            duration_ms = (time.time() - start_time) * 1000

            return DeliveryResult(
                success=200 <= response.status_code < 300,
                status_code=response.status_code,
                response_body=response.text[:1000],  # Limit response body size
                duration_ms=duration_ms
            )

        except httpx.TimeoutException:
            duration_ms = (time.time() - start_time) * 1000
            return DeliveryResult(
                success=False,
                error_message="Request timeout",
                duration_ms=duration_ms,
                should_retry=True,
                next_retry_delay=60
            )

        except httpx.RequestError as e:
            duration_ms = (time.time() - start_time) * 1000
            return DeliveryResult(
                success=False,
                error_message=str(e),
                duration_ms=duration_ms,
                should_retry=True,
                next_retry_delay=60
            )

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _schedule_retry(self,
                             subscription: WebhookSubscription,
                             event: WebhookEvent,
                             delivery: WebhookDelivery):
        """Schedule a retry for failed webhook delivery."""
        retry_delay = self._calculate_retry_delay(
            delivery.attempts,
            subscription.retry_policy
        )

        await asyncio.sleep(retry_delay)
        await self.delivery_queue.put((subscription, event, delivery))

    def _calculate_retry_delay(self, attempt: int, retry_policy: Dict[str, Any]) -> int:
        """Calculate retry delay based on policy."""
        base_delay = retry_policy.get("retry_delay", 60)
        multiplier = retry_policy.get("backoff_multiplier", 2.0)
        max_delay = retry_policy.get("max_retry_delay", 3600)

        # Exponential backoff
        delay = base_delay * (multiplier ** (attempt - 1))
        return min(int(delay), max_delay)

    async def _cleanup_worker(self):
        """Background worker for cleaning up old data."""
        while self.is_running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_old_data()
            except Exception as e:
                logger.error(f"Error in cleanup worker: {e}")

    async def _cleanup_old_data(self):
        """Clean up old webhook data."""
        cutoff_time = datetime.utcnow() - timedelta(days=30)

        # Clean up old deliveries
        total_removed = 0
        for subscription_id, deliveries in self.deliveries.items():
            original_count = len(deliveries)
            self.deliveries[subscription_id] = [
                d for d in deliveries
                if d.created_at > cutoff_time
            ]
            total_removed += original_count - len(self.deliveries[subscription_id])

        if total_removed > 0:
            logger.debug(f"Cleaned up {total_removed} old webhook deliveries")

    async def get_subscription_stats(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific subscription."""
        subscription = self.subscriptions.get(subscription_id)
        if not subscription:
            return None

        deliveries = self.deliveries.get(subscription_id, [])

        if not deliveries:
            return {
                "subscription_id": subscription_id,
                "status": subscription.status.value,
                "total_deliveries": 0,
                "successful_deliveries": 0,
                "failed_deliveries": 0,
                "success_rate": 0.0
            }

        successful = len([d for d in deliveries if d.status == DeliveryStatus.SUCCESS])
        failed = len([d for d in deliveries if d.status == DeliveryStatus.FAILED])
        pending = len([d for d in deliveries if d.status == DeliveryStatus.PENDING])
        retry = len([d for d in deliveries if d.status == DeliveryStatus.RETRY])

        avg_duration = 0
        if deliveries:
            completed_deliveries = [d for d in deliveries if d.duration_ms > 0]
            if completed_deliveries:
                avg_duration = sum(d.duration_ms for d in completed_deliveries) / len(completed_deliveries)

        return {
            "subscription_id": subscription_id,
            "status": subscription.status.value,
            "total_deliveries": len(deliveries),
            "successful_deliveries": successful,
            "failed_deliveries": failed,
            "pending_deliveries": pending,
            "retry_deliveries": retry,
            "success_rate": (successful / len(deliveries)) * 100 if deliveries else 0,
            "avg_delivery_time_ms": round(avg_duration, 2),
            "last_delivery": subscription.last_delivery.isoformat() if subscription.last_delivery else None
        }

    async def get_global_stats(self) -> WebhookStats:
        """Get global webhook statistics."""
        total_subscriptions = len(self.subscriptions)
        active_subscriptions = len([
            s for s in self.subscriptions.values()
            if s.status == WebhookStatus.ACTIVE
        ])

        total_deliveries = 0
        successful_deliveries = 0
        failed_deliveries = 0
        pending_deliveries = 0
        total_duration = 0
        completed_count = 0

        for deliveries in self.deliveries.values():
            for delivery in deliveries:
                total_deliveries += 1

                if delivery.status == DeliveryStatus.SUCCESS:
                    successful_deliveries += 1
                elif delivery.status == DeliveryStatus.FAILED:
                    failed_deliveries += 1
                elif delivery.status == DeliveryStatus.PENDING:
                    pending_deliveries += 1

                if delivery.duration_ms > 0:
                    total_duration += delivery.duration_ms
                    completed_count += 1

        avg_delivery_time = total_duration / completed_count if completed_count > 0 else 0
        success_rate = (successful_deliveries / total_deliveries) * 100 if total_deliveries > 0 else 0

        return WebhookStats(
            total_subscriptions=total_subscriptions,
            active_subscriptions=active_subscriptions,
            total_deliveries=total_deliveries,
            successful_deliveries=successful_deliveries,
            failed_deliveries=failed_deliveries,
            pending_deliveries=pending_deliveries,
            avg_delivery_time_ms=round(avg_delivery_time, 2),
            success_rate=round(success_rate, 2)
        )


# Global webhook manager instance
webhook_manager = WebhookManager()


async def get_webhook_manager() -> WebhookManager:
    """Get the global webhook manager instance."""
    if not webhook_manager.is_running:
        await webhook_manager.start()
    return webhook_manager