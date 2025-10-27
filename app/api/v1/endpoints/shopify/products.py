"""
Shopify products API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import Product, ShopifyError
from app.core.dependencies import get_shopify_service

router = APIRouter(prefix="/shopify/products", tags=["shopify-products"])


class ProductSearchRequest(BaseModel):
    """Product search request model."""
    query: str = Field(..., description="Search query")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Pagination offset")
    sort_by: str = Field("RELEVANCE", description="Sort field")
    reverse: bool = Field(False, description="Sort in descending order")


class ProductResponse(BaseModel):
    """Product response model."""
    id: str
    title: str
    handle: str
    description: Optional[str] = None
    product_type: str
    vendor: str
    status: str
    tags: List[str]
    price_range: dict
    in_stock: bool
    primary_image: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProductSearchResponse(BaseModel):
    """Product search response model."""
    products: List[ProductResponse]
    total_count: int
    has_more: bool
    limit: int
    offset: int


class ProductRecommendationsRequest(BaseModel):
    """Product recommendations request model."""
    product_id: str = Field(..., description="Product ID to get recommendations for")
    limit: int = Field(5, ge=1, le=20, description="Number of recommendations")


class ProductComparisonRequest(BaseModel):
    """Product comparison request model."""
    product_ids: List[str] = Field(..., min_items=2, max_items=10, description="Product IDs to compare")


class InventoryCheckRequest(BaseModel):
    """Inventory check request model."""
    variant_ids: List[str] = Field(..., min_items=1, max_items=100, description="Variant IDs to check")


class InventoryCheckResponse(BaseModel):
    """Inventory check response model."""
    inventory_levels: dict


def _product_to_response(product: Product) -> ProductResponse:
    """Convert Product model to ProductResponse."""
    primary_image = None
    if product.primary_image:
        primary_image = {
            "id": product.primary_image.id,
            "src": product.primary_image.src,
            "alt_text": product.primary_image.alt_text,
            "width": product.primary_image.width,
            "height": product.primary_image.height,
        }

    min_price, max_price = product.price_range

    return ProductResponse(
        id=product.id,
        title=product.title,
        handle=product.handle,
        description=product.description,
        product_type=product.product_type or "",
        vendor=product.vendor,
        status=product.status,
        tags=product.tags.split(",") if isinstance(product.tags, str) else (product.tags or []),
        price_range={
            "min": str(min_price),
            "max": str(max_price),
            "currency": product.variants[0].price.currency_code if product.variants else "USD"
        },
        in_stock=product.in_stock,
        primary_image=primary_image,
        created_at=product.created_at.isoformat() if product.created_at else None,
        updated_at=product.updated_at.isoformat() if product.updated_at else None,
    )


@router.post("/search", response_model=ProductSearchResponse)
async def search_products(
    request: ProductSearchRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Search for products in Shopify store.

    This endpoint allows searching products with various filters and sorting options.
    Supports full-text search across product titles, descriptions, tags, and more.
    """
    try:
        async with shopify:
            products, has_more = await shopify.search_products(
                query=request.query,
                limit=request.limit,
                offset=request.offset,
                sort_by=request.sort_by,
                reverse=request.reverse
            )

            product_responses = [_product_to_response(product) for product in products]

            return ProductSearchResponse(
                products=product_responses,
                total_count=len(product_responses),  # Shopify doesn't provide total count in GraphQL
                has_more=has_more,
                limit=request.limit,
                offset=request.offset
            )

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a specific product by ID.

    Retrieves detailed information about a single product including all variants,
    images, pricing, and inventory information.
    """
    try:
        async with shopify:
            product = await shopify.get_product_by_id(product_id)
            return _product_to_response(product)

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/handle/{handle}", response_model=ProductResponse)
async def get_product_by_handle(
    handle: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a product by its handle (URL-friendly identifier).

    Handles are typically used in URLs and are human-readable versions of product titles.
    """
    try:
        async with shopify:
            product = await shopify.get_product_by_handle(handle)
            return _product_to_response(product)

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/recommendations", response_model=List[ProductResponse])
async def get_product_recommendations(
    request: ProductRecommendationsRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get product recommendations based on a given product.

    Uses product attributes like type, vendor, and tags to find similar products
    that customers might also be interested in.
    """
    try:
        async with shopify:
            recommendations = await shopify.get_product_recommendations(
                product_id=request.product_id,
                limit=request.limit
            )

            return [_product_to_response(product) for product in recommendations]

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Product not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/compare", response_model=List[ProductResponse])
async def compare_products(
    request: ProductComparisonRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Compare multiple products side by side.

    Retrieves detailed information for multiple products to enable comparison
    of features, pricing, specifications, and other attributes.
    """
    try:
        async with shopify:
            products = await shopify.compare_products(request.product_ids)

            if not products:
                raise HTTPException(status_code=404, detail="No products found for comparison")

            return [_product_to_response(product) for product in products]

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/inventory/check", response_model=InventoryCheckResponse)
async def check_inventory(
    request: InventoryCheckRequest,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Check inventory availability for multiple product variants.

    Returns current inventory levels for the specified variant IDs.
    Useful for checking stock availability before adding items to cart.
    """
    try:
        async with shopify:
            inventory_levels = await shopify.check_inventory_availability(request.variant_ids)

            return InventoryCheckResponse(
                inventory_levels=inventory_levels
            )

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/collections/{collection_id}", response_model=ProductSearchResponse)
async def get_collection_products(
    collection_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("TITLE", description="Sort field"),
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get products in a specific collection.

    Retrieves products that belong to a particular collection, with optional sorting
    and pagination support.
    """
    try:
        async with shopify:
            products, has_more = await shopify.get_products_in_collection(
                collection_id=collection_id,
                limit=limit,
                offset=offset,
                sort_by=sort_by
            )

            product_responses = [_product_to_response(product) for product in products]

            return ProductSearchResponse(
                products=product_responses,
                total_count=len(product_responses),
                has_more=has_more,
                limit=limit,
                offset=offset
            )

    except ShopifyError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Collection not found")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/variant/{variant_id}/available")
async def check_variant_availability(
    variant_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Check if a specific product variant is available.

    Simple endpoint to quickly check if a variant is in stock and available for purchase.
    """
    try:
        async with shopify:
            is_available = await shopify.is_variant_available(variant_id)

            return {
                "variant_id": variant_id,
                "available": is_available
            }

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")