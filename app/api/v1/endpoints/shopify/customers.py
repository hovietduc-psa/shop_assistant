"""
Shopify customers API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import Customer, ShopifyError
from app.core.dependencies import get_shopify_service

router = APIRouter(prefix="/shopify/customers", tags=["shopify-customers"])


class CustomerSearchRequest(BaseModel):
    """Customer search request model."""
    query: str = Field(..., description="Search query")
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results")


class CustomerResponse(BaseModel):
    """Customer response model."""
    id: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: str
    phone: Optional[str]
    orders_count: int
    total_spent: str
    currency: str
    state: str
    verified_email: bool
    created_at: str
    updated_at: str


def _customer_to_response(customer: Customer) -> CustomerResponse:
    """Convert Customer model to CustomerResponse."""
    return CustomerResponse(
        id=str(customer.id),
        email=customer.email,
        first_name=customer.first_name,
        last_name=customer.last_name,
        full_name=customer.full_name,
        phone=customer.phone,
        orders_count=customer.orders_count,
        total_spent=customer.total_spent,
        currency=customer.currency,
        state=customer.state,
        verified_email=customer.verified_email,
        created_at=customer.created_at.isoformat() if customer.created_at else None,
        updated_at=customer.updated_at.isoformat() if customer.updated_at else None
    )


@router.post("/search", response_model=List[CustomerResponse])
async def search_customers(
    request: CustomerSearchRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Search for customers in Shopify store.

    Supports searching by email, name, phone, and other customer attributes.
    Useful for finding customers for support and order inquiries.
    """
    try:
        async with shopify:
            customers = await shopify.search_customers(
                query=request.query,
                limit=request.limit
            )

            return [_customer_to_response(customer) for customer in customers]

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a specific customer by ID.

    Retrieves detailed customer information including order history,
    contact details, and account status.
    """
    try:
        async with shopify:
            # This would need to be implemented in ShopifyService
            # For now, search for the customer
            customers = await shopify.search_customers(
                query=f"id:{customer_id}",
                limit=1
            )

            if not customers:
                raise HTTPException(status_code=404, detail="Customer not found")

            return _customer_to_response(customers[0])

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Customer not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")