"""
Shopify webhook handlers for real-time data synchronization.
"""

import json
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
from enum import Enum

from loguru import logger

from .client import ShopifyClient
from .models import WebhookEvent, ShopifyError


class WebhookTopic(Enum):
    """Shopify webhook topics."""
    # Product webhooks
    PRODUCT_CREATE = "products/create"
    PRODUCT_UPDATE = "products/update"
    PRODUCT_DELETE = "products/delete"

    # Order webhooks
    ORDER_CREATE = "orders/create"
    ORDER_UPDATED = "orders/updated"
    ORDER_CANCELLED = "orders/cancelled"
    ORDER_FULFILLED = "orders/fulfilled"
    ORDERS_CREATE = "orders/create"  # Alternative naming
    ORDERS_UPDATED = "orders/updated"
    ORDERS_CANCELLED = "orders/cancelled"
    ORDERS_FULFILLED = "orders/fulfilled"

    # Customer webhooks
    CUSTOMER_CREATE = "customers/create"
    CUSTOMER_UPDATE = "customers/update"
    CUSTOMER_DELETE = "customers/delete"
    CUSTOMERS_CREATE = "customers/create"
    CUSTOMERS_UPDATE = "customers/update"
    CUSTOMERS_DELETE = "customers/delete"

    # Inventory webhooks
    INVENTORY_LEVELS_UPDATE = "inventory_levels/update"
    INVENTORY_LEVELS_CONNECT = "inventory_levels/connect"
    INVENTORY_LEVELS_DISCONNECT = "inventory_levels/disconnect"

    # Collection webhooks
    COLLECTION_CREATE = "collections/create"
    COLLECTION_UPDATE = "collections/update"
    COLLECTION_DELETE = "collections/delete"
    COLLECTIONS_CREATE = "collections/create"
    COLLECTIONS_UPDATE = "collections/update"
    COLLECTIONS_DELETE = "collections/delete"

    # Shop webhooks
    SHOP_UPDATE = "shop/update"
    APP_UNINSTALLED = "app/uninstalled"


class WebhookHandler:
    """Handler for processing Shopify webhooks."""

    def __init__(self, client: ShopifyClient):
        """Initialize the webhook handler."""
        self.client = client
        self._handlers: Dict[WebhookTopic, List[Callable]] = {}
        self._default_handlers: List[Callable] = []

    def register_handler(self, topic: WebhookTopic, handler: Callable):
        """Register a handler for a specific webhook topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        logger.info(f"Registered handler for topic: {topic.value}")

    def register_default_handler(self, handler: Callable):
        """Register a default handler for all webhooks."""
        self._default_handlers.append(handler)
        logger.info("Registered default webhook handler")

    async def process_webhook(self, headers: Dict[str, str], body: str) -> bool:
        """
        Process an incoming webhook from Shopify.

        Args:
            headers: HTTP headers from the webhook request
            body: Raw webhook body

        Returns:
            True if webhook was processed successfully, False otherwise
        """
        try:
            # Verify webhook authenticity
            if not await self.client.verify_webhook(headers, body):
                logger.error("Webhook verification failed")
                return False

            # Parse the webhook event
            event = await self.client.parse_webhook_event(headers, body)
            if not event:
                logger.error("Failed to parse webhook event")
                return False

            logger.info(f"Processing webhook: {event.topic} for shop: {event.shop_domain}")

            # Get handlers for this topic
            topic_handlers = []
            try:
                topic_enum = WebhookTopic(event.topic)
                topic_handlers = self._handlers.get(topic_enum, [])
            except ValueError:
                logger.warning(f"Unknown webhook topic: {event.topic}")

            # Call topic-specific handlers
            success = True
            for handler in topic_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in webhook handler: {e}")
                    success = False

            # Call default handlers
            for handler in self._default_handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error in default webhook handler: {e}")
                    success = False

            logger.info(f"Webhook processed: {event.topic}, success: {success}")
            return success

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False


class ShopifyWebhookProcessor:
    """High-level webhook processor with common handlers."""

    def __init__(self, webhook_handler: WebhookHandler):
        """Initialize the webhook processor."""
        self.webhook_handler = webhook_handler
        self._setup_default_handlers()

    def _setup_default_handlers(self):
        """Setup default webhook handlers."""
        # Register handlers for different webhook types
        self.webhook_handler.register_handler(WebhookTopic.PRODUCT_CREATE, self._handle_product_create)
        self.webhook_handler.register_handler(WebhookTopic.PRODUCT_UPDATE, self._handle_product_update)
        self.webhook_handler.register_handler(WebhookTopic.PRODUCT_DELETE, self._handle_product_delete)

        self.webhook_handler.register_handler(WebhookTopic.ORDER_CREATE, self._handle_order_create)
        self.webhook_handler.register_handler(WebhookTopic.ORDER_UPDATED, self._handle_order_update)
        self.webhook_handler.register_handler(WebhookTopic.ORDER_CANCELLED, self._handle_order_cancelled)
        self.webhook_handler.register_handler(WebhookTopic.ORDER_FULFILLED, self._handle_order_fulfilled)

        self.webhook_handler.register_handler(WebhookTopic.CUSTOMER_CREATE, self._handle_customer_create)
        self.webhook_handler.register_handler(WebhookTopic.CUSTOMER_UPDATE, self._handle_customer_update)
        self.webhook_handler.register_handler(WebhookTopic.CUSTOMER_DELETE, self._handle_customer_delete)

        self.webhook_handler.register_handler(WebhookTopic.INVENTORY_LEVELS_UPDATE, self._handle_inventory_update)
        self.webhook_handler.register_handler(WebhookTopic.APP_UNINSTALLED, self._handle_app_uninstalled)

    async def _handle_product_create(self, event: WebhookEvent):
        """Handle product creation webhook."""
        logger.info(f"Product created: {event.payload.get('id')}")

        # Here you would typically:
        # 1. Add the product to your local database/cache
        # 2. Update search indexes
        # 3. Send notifications if needed
        # 4. Update product recommendations

        product_id = event.payload.get("id")
        product_title = event.payload.get("title", "Unknown")

        # Example: Store in Redis cache
        await self._cache_product_data(product_id, event.payload)

        # Example: Update search index
        await self._update_search_index(product_id, event.payload, "create")

        logger.info(f"Processed product creation: {product_title}")

    async def _handle_product_update(self, event: WebhookEvent):
        """Handle product update webhook."""
        logger.info(f"Product updated: {event.payload.get('id')}")

        product_id = event.payload.get("id")
        product_title = event.payload.get("title", "Unknown")

        # Update cached data
        await self._cache_product_data(product_id, event.payload)

        # Update search index
        await self._update_search_index(product_id, event.payload, "update")

        # Check for price changes, inventory updates, etc.
        await self._check_product_changes(product_id, event.payload)

        logger.info(f"Processed product update: {product_title}")

    async def _handle_product_delete(self, event: WebhookEvent):
        """Handle product deletion webhook."""
        logger.info(f"Product deleted: {event.payload.get('id')}")

        product_id = event.payload.get("id")

        # Remove from cache
        await self._remove_product_from_cache(product_id)

        # Remove from search index
        await self._update_search_index(product_id, event.payload, "delete")

        logger.info(f"Processed product deletion: {product_id}")

    async def _handle_order_create(self, event: WebhookEvent):
        """Handle order creation webhook."""
        logger.info(f"Order created: {event.payload.get('id')}")

        order_id = event.payload.get("id")
        order_number = event.payload.get("order_number")
        customer_email = event.payload.get("email")

        # Process order analytics
        await self._process_order_analytics(event.payload)

        # Update customer data
        if customer_email:
            await self._update_customer_order_data(customer_email, event.payload)

        # Check for inventory impacts
        await self._update_inventory_from_order(event.payload)

        logger.info(f"Processed order creation: #{order_number}")

    async def _handle_order_update(self, event: WebhookEvent):
        """Handle order update webhook."""
        logger.info(f"Order updated: {event.payload.get('id')}")

        order_id = event.payload.get("id")
        financial_status = event.payload.get("financial_status")
        fulfillment_status = event.payload.get("fulfillment_status")

        # Process status changes
        await self._process_order_status_change(event.payload)

        # Update analytics
        await self._update_order_analytics(event.payload)

        logger.info(f"Processed order update: {order_id}, financial: {financial_status}, fulfillment: {fulfillment_status}")

    async def _handle_order_cancelled(self, event: WebhookEvent):
        """Handle order cancellation webhook."""
        logger.info(f"Order cancelled: {event.payload.get('id')}")

        order_id = event.payload.get("id")
        cancel_reason = event.payload.get("cancel_reason")

        # Restore inventory if needed
        await self._restore_inventory_from_cancellation(event.payload)

        # Update analytics
        await self._process_cancellation_analytics(event.payload)

        logger.info(f"Processed order cancellation: {order_id}, reason: {cancel_reason}")

    async def _handle_order_fulfilled(self, event: WebhookEvent):
        """Handle order fulfillment webhook."""
        logger.info(f"Order fulfilled: {event.payload.get('id')}")

        order_id = event.payload.get("id")

        # Process fulfillment analytics
        await self._process_fulfillment_analytics(event.payload)

        # Update customer satisfaction metrics
        await self._update_fulfillment_metrics(event.payload)

        logger.info(f"Processed order fulfillment: {order_id}")

    async def _handle_customer_create(self, event: WebhookEvent):
        """Handle customer creation webhook."""
        logger.info(f"Customer created: {event.payload.get('id')}")

        customer_id = event.payload.get("id")
        customer_email = event.payload.get("email")

        # Add to customer database
        await self._add_customer_to_database(event.payload)

        # Update customer analytics
        await self._process_customer_analytics(event.payload, "create")

        logger.info(f"Processed customer creation: {customer_email}")

    async def _handle_customer_update(self, event: WebhookEvent):
        """Handle customer update webhook."""
        logger.info(f"Customer updated: {event.payload.get('id')}")

        customer_id = event.payload.get("id")
        customer_email = event.payload.get("email")

        # Update customer database
        await self._update_customer_in_database(event.payload)

        # Update analytics
        await self._process_customer_analytics(event.payload, "update")

        logger.info(f"Processed customer update: {customer_email}")

    async def _handle_customer_delete(self, event: WebhookEvent):
        """Handle customer deletion webhook."""
        logger.info(f"Customer deleted: {event.payload.get('id')}")

        customer_id = event.payload.get("id")

        # Mark customer as deleted (soft delete)
        await self._soft_delete_customer(customer_id)

        # Update analytics
        await self._process_customer_analytics(event.payload, "delete")

        logger.info(f"Processed customer deletion: {customer_id}")

    async def _handle_inventory_update(self, event: WebhookEvent):
        """Handle inventory level update webhook."""
        logger.info(f"Inventory updated for item: {event.payload.get('inventory_item_id')}")

        inventory_item_id = event.payload.get("inventory_item_id")
        location_id = event.payload.get("location_id")
        available = event.payload.get("available", 0)

        # Update inventory cache
        await self._update_inventory_cache(inventory_item_id, location_id, available)

        # Check for low stock alerts
        await self._check_low_stock_alerts(inventory_item_id, available)

        # Update product availability
        await self._update_product_availability(inventory_item_id, available)

        logger.info(f"Processed inventory update: item={inventory_item_id}, available={available}")

    async def _handle_app_uninstalled(self, event: WebhookEvent):
        """Handle app uninstallation webhook."""
        logger.warning(f"App uninstalled from shop: {event.shop_domain}")

        # Clean up shop-specific data
        await self._cleanup_shop_data(event.shop_domain)

        # Disable webhooks for this shop
        await self._disable_shop_webhooks(event.shop_domain)

        # Send notification about app uninstallation
        await self._notify_app_uninstallation(event.shop_domain)

        logger.warning(f"Processed app uninstallation: {event.shop_domain}")

    # Helper methods for webhook processing

    async def _cache_product_data(self, product_id: str, product_data: Dict[str, Any]):
        """Cache product data in Redis."""
        try:
            # This would typically use your Redis service
            logger.debug(f"Caching product data for: {product_id}")
            # await redis_client.setex(f"product:{product_id}", 3600, json.dumps(product_data))
        except Exception as e:
            logger.error(f"Error caching product data: {e}")

    async def _remove_product_from_cache(self, product_id: str):
        """Remove product data from cache."""
        try:
            logger.debug(f"Removing product from cache: {product_id}")
            # await redis_client.delete(f"product:{product_id}")
        except Exception as e:
            logger.error(f"Error removing product from cache: {e}")

    async def _update_search_index(self, product_id: str, product_data: Dict[str, Any], action: str):
        """Update search index for product."""
        try:
            logger.debug(f"Updating search index for product {product_id}: {action}")
            # This would integrate with your search service (Elasticsearch, etc.)
        except Exception as e:
            logger.error(f"Error updating search index: {e}")

    async def _check_product_changes(self, product_id: str, product_data: Dict[str, Any]):
        """Check for important product changes."""
        try:
            # Check for price changes, out of stock, etc.
            logger.debug(f"Checking product changes for: {product_id}")
            # Implement change detection logic
        except Exception as e:
            logger.error(f"Error checking product changes: {e}")

    async def _process_order_analytics(self, order_data: Dict[str, Any]):
        """Process order analytics."""
        try:
            logger.debug(f"Processing order analytics: {order_data.get('id')}")
            # Update analytics database
        except Exception as e:
            logger.error(f"Error processing order analytics: {e}")

    async def _update_customer_order_data(self, customer_email: str, order_data: Dict[str, Any]):
        """Update customer order data."""
        try:
            logger.debug(f"Updating order data for customer: {customer_email}")
            # Update customer records
        except Exception as e:
            logger.error(f"Error updating customer order data: {e}")

    async def _update_inventory_from_order(self, order_data: Dict[str, Any]):
        """Update inventory based on order."""
        try:
            logger.debug(f"Updating inventory from order: {order_data.get('id')}")
            # Process inventory adjustments
        except Exception as e:
            logger.error(f"Error updating inventory from order: {e}")

    async def _process_order_status_change(self, order_data: Dict[str, Any]):
        """Process order status change."""
        try:
            logger.debug(f"Processing status change for order: {order_data.get('id')}")
            # Handle status change logic
        except Exception as e:
            logger.error(f"Error processing order status change: {e}")

    async def _update_order_analytics(self, order_data: Dict[str, Any]):
        """Update order analytics."""
        try:
            logger.debug(f"Updating analytics for order: {order_data.get('id')}")
            # Update analytics
        except Exception as e:
            logger.error(f"Error updating order analytics: {e}")

    async def _restore_inventory_from_cancellation(self, order_data: Dict[str, Any]):
        """Restore inventory from cancelled order."""
        try:
            logger.debug(f"Restoring inventory for cancelled order: {order_data.get('id')}")
            # Restore inventory levels
        except Exception as e:
            logger.error(f"Error restoring inventory: {e}")

    async def _process_cancellation_analytics(self, order_data: Dict[str, Any]):
        """Process cancellation analytics."""
        try:
            logger.debug(f"Processing cancellation analytics: {order_data.get('id')}")
            # Update cancellation metrics
        except Exception as e:
            logger.error(f"Error processing cancellation analytics: {e}")

    async def _process_fulfillment_analytics(self, order_data: Dict[str, Any]):
        """Process fulfillment analytics."""
        try:
            logger.debug(f"Processing fulfillment analytics: {order_data.get('id')}")
            # Update fulfillment metrics
        except Exception as e:
            logger.error(f"Error processing fulfillment analytics: {e}")

    async def _update_fulfillment_metrics(self, order_data: Dict[str, Any]):
        """Update fulfillment metrics."""
        try:
            logger.debug(f"Updating fulfillment metrics: {order_data.get('id')}")
            # Update metrics
        except Exception as e:
            logger.error(f"Error updating fulfillment metrics: {e}")

    async def _add_customer_to_database(self, customer_data: Dict[str, Any]):
        """Add customer to database."""
        try:
            logger.debug(f"Adding customer to database: {customer_data.get('email')}")
            # Add to database
        except Exception as e:
            logger.error(f"Error adding customer to database: {e}")

    async def _update_customer_in_database(self, customer_data: Dict[str, Any]):
        """Update customer in database."""
        try:
            logger.debug(f"Updating customer in database: {customer_data.get('email')}")
            # Update database
        except Exception as e:
            logger.error(f"Error updating customer in database: {e}")

    async def _soft_delete_customer(self, customer_id: str):
        """Soft delete customer."""
        try:
            logger.debug(f"Soft deleting customer: {customer_id}")
            # Mark as deleted
        except Exception as e:
            logger.error(f"Error soft deleting customer: {e}")

    async def _process_customer_analytics(self, customer_data: Dict[str, Any], action: str):
        """Process customer analytics."""
        try:
            logger.debug(f"Processing customer analytics {action}: {customer_data.get('email')}")
            # Update analytics
        except Exception as e:
            logger.error(f"Error processing customer analytics: {e}")

    async def _update_inventory_cache(self, inventory_item_id: str, location_id: str, available: int):
        """Update inventory cache."""
        try:
            logger.debug(f"Updating inventory cache: {inventory_item_id} = {available}")
            # Update cache
        except Exception as e:
            logger.error(f"Error updating inventory cache: {e}")

    async def _check_low_stock_alerts(self, inventory_item_id: str, available: int):
        """Check for low stock alerts."""
        try:
            if available <= 5:  # Low stock threshold
                logger.warning(f"Low stock alert: {inventory_item_id} has {available} items")
                # Send alert notification
        except Exception as e:
            logger.error(f"Error checking low stock alerts: {e}")

    async def _update_product_availability(self, inventory_item_id: str, available: int):
        """Update product availability status."""
        try:
            logger.debug(f"Updating product availability: {inventory_item_id} = {available}")
            # Update product status
        except Exception as e:
            logger.error(f"Error updating product availability: {e}")

    async def _cleanup_shop_data(self, shop_domain: str):
        """Clean up shop-specific data."""
        try:
            logger.warning(f"Cleaning up data for shop: {shop_domain}")
            # Clean up database records
        except Exception as e:
            logger.error(f"Error cleaning up shop data: {e}")

    async def _disable_shop_webhooks(self, shop_domain: str):
        """Disable webhooks for shop."""
        try:
            logger.warning(f"Disabling webhooks for shop: {shop_domain}")
            # Disable webhooks
        except Exception as e:
            logger.error(f"Error disabling shop webhooks: {e}")

    async def _notify_app_uninstallation(self, shop_domain: str):
        """Notify about app uninstallation."""
        try:
            logger.warning(f"Notifying about app uninstallation: {shop_domain}")
            # Send notification
        except Exception as e:
            logger.error(f"Error sending uninstallation notification: {e}")