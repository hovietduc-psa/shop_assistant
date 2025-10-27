"""
Shopify orders API endpoints.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import Order, ShopifyError
from app.core.dependencies import get_shopify_service

router = APIRouter(prefix="/shopify/orders", tags=["shopify-orders"])


class OrderStatusResponse(BaseModel):
    """Order status response model."""
    order_id: str
    order_number: int
    financial_status: str
    fulfillment_status: Optional[str]
    is_paid: bool
    is_fulfilled: bool
    is_cancelled: bool
    total_price: str
    currency: str
    created_at: str
    updated_at: str
    cancelled_at: Optional[str]
    cancel_reason: Optional[str]


class OrderResponse(BaseModel):
    """Order response model."""
    id: str
    order_number: int
    email: Optional[str]
    financial_status: str
    fulfillment_status: Optional[str]
    total_price: str
    currency: str
    created_at: str
    updated_at: str
    line_items_count: int
    customer_name: Optional[str]


class CustomerOrderRequest(BaseModel):
    """Customer order request model."""
    customer_id: str = Field(..., description="Customer ID")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of orders")


def _order_to_response(order: Order) -> OrderResponse:
    """Convert Order model to OrderResponse."""
    customer_name = None
    if order.customer:
        customer_name = order.customer.full_name

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        email=order.email,
        financial_status=order.financial_status,
        fulfillment_status=order.fulfillment_status,
        total_price=str(order.total_price.amount),
        currency=order.total_price.currency_code,
        created_at=order.created_at.isoformat(),
        updated_at=order.updated_at.isoformat(),
        line_items_count=len(order.line_items),
        customer_name=customer_name
    )


@router.get("/{order_id}/status", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get detailed status information for an order.

    Provides comprehensive order status including payment, fulfillment,
    cancellation details, and timestamps.
    """
    try:
        async with shopify:
            order_status = await shopify.get_order_status(order_id)
            return OrderStatusResponse(**order_status)

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a specific order by ID.

    Retrieves basic order information including customer details,
    line items count, and status information.
    """
    try:
        async with shopify:
            # For now, we'll use get_order_status as it provides similar information
            # In a full implementation, you'd add a get_order method to ShopifyService
            order_status = await shopify.get_order_status(order_id)
            return OrderResponse(
                id=order_status["order_id"],
                order_number=order_status["order_number"],
                email=None,  # Would need to be populated from full order data
                financial_status=order_status["financial_status"],
                fulfillment_status=order_status["fulfillment_status"],
                total_price=order_status["total_price"],
                currency=order_status["currency"],
                created_at=order_status["created_at"],
                updated_at=order_status["updated_at"],
                line_items_count=0,  # Would need to be populated from full order data
                customer_name=None
            )

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/customer", response_model=List[OrderResponse])
async def get_customer_orders(
    request: CustomerOrderRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get orders for a specific customer.

    Retrieves all orders associated with a customer ID, sorted by creation date.
    Useful for customer order history and support interactions.
    """
    try:
        async with shopify:
            orders = await shopify.get_customer_orders(
                customer_id=request.customer_id,
                limit=request.limit
            )

            return [_order_to_response(order) for order in orders]

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/number/{order_number}", response_model=OrderResponse)
async def get_order_by_number(
    order_number: int,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get an order by its order number.

    Order numbers are human-readable identifiers that customers typically see
    in their confirmation emails and order history.
    """
    try:
        async with shopify:
            # Search for order by number using GraphQL query
            # This would need to be implemented in ShopifyService
            query = f"order_number:{order_number}"

            # For now, return a placeholder response
            # In a full implementation, you'd add search by order number
            raise HTTPException(
                status_code=501,
                detail="Search by order number not yet implemented"
            )

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Order not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")