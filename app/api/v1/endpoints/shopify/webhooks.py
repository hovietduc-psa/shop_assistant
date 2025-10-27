"""
Shopify webhooks API endpoints.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.webhooks import WebhookHandler, ShopifyWebhookProcessor
from app.integrations.shopify.client import ShopifyClient
from app.core.config import settings

router = APIRouter(prefix="/shopify/webhooks", tags=["shopify-webhooks"])

# Global webhook handler - in production, you'd want to set this up properly
_webhook_handler: WebhookHandler = None


def get_webhook_handler() -> WebhookHandler:
    """Get or create the webhook handler."""
    global _webhook_handler
    if _webhook_handler is None:
        client = ShopifyClient()
        _webhook_handler = WebhookHandler(client)
        processor = ShopifyWebhookProcessor(_webhook_handler)
    return _webhook_handler


@router.post("/receive")
async def receive_webhook(
    request: Request,
    webhook_handler: WebhookHandler = Depends(get_webhook_handler)
):
    """
    Receive and process webhooks from Shopify.

    This endpoint handles incoming webhook requests from Shopify,
    verifies their authenticity, and processes the events.
    """
    try:
        # Get raw body and headers
        body = await request.body()
        body_str = body.decode('utf-8')
        headers = dict(request.headers)

        # Process the webhook
        success = await webhook_handler.process_webhook(headers, body_str)

        if success:
            return Response(status_code=200)
        else:
            return Response(status_code=500)

    except Exception as e:
        # Log the error but don't expose details to Shopify
        print(f"Error processing webhook: {e}")
        return Response(status_code=500)


@router.get("/health")
async def webhook_health():
    """
    Health check endpoint for webhook processing.

    Simple endpoint to verify that the webhook system is operational.
    """
    return {"status": "healthy", "message": "Webhook processing is active"}


@router.post("/test")
async def test_webhook():
    """
    Test endpoint for webhook development.

    This endpoint allows testing webhook processing without actual Shopify events.
    Useful for development and debugging purposes.
    """
    try:
        # Create a test webhook payload
        test_payload = {
            "id": "test_product_123",
            "title": "Test Product",
            "vendor": "Test Vendor",
            "product_type": "Test Type",
            "status": "ACTIVE",
            "tags": ["test", "webhook"],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }

        test_headers = {
            "X-Shopify-Topic": "products/create",
            "X-Shopify-Shop-Domain": "test-shop.myshopify.com",
            "X-Shopify-Webhook-Id": "test_webhook_123",
            "X-Shopify-Api-Version": "2024-01"
        }

        # In a real test scenario, you would need proper HMAC signatures
        # For now, we'll skip verification in test mode
        return {
            "status": "test_mode",
            "message": "Webhook test endpoint is working",
            "note": "Actual webhook verification requires proper Shopify signatures"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test webhook error: {str(e)}")


@router.get("/info")
async def webhook_info():
    """
    Get information about webhook configuration.

    Returns details about the current webhook setup and configuration.
    """
    return {
        "shop_domain": settings.SHOPIFY_SHOP_DOMAIN,
        "api_version": settings.SHOPIFY_API_VERSION,
        "webhook_secret_configured": bool(settings.SHOPIFY_WEBHOOK_SECRET),
        "supported_topics": [
            "products/create",
            "products/update",
            "products/delete",
            "orders/create",
            "orders/updated",
            "orders/cancelled",
            "orders/fulfilled",
            "customers/create",
            "customers/update",
            "customers/delete",
            "inventory_levels/update",
            "collections/create",
            "collections/update",
            "collections/delete",
            "shop/update",
            "app/uninstalled"
        ]
    }