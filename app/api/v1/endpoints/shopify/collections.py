"""
Shopify collections API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import Collection, ShopifyError
from app.core.dependencies import get_shopify_service

router = APIRouter(prefix="/shopify/collections", tags=["shopify-collections"])


class CollectionResponse(BaseModel):
    """Collection response model."""
    id: str
    title: str
    handle: str
    description: Optional[str]
    image: Optional[dict]
    updated_at: str
    sort_order: str


class CollectionListResponse(BaseModel):
    """Collection list response model."""
    collections: List[CollectionResponse]
    count: int


def _collection_to_response(collection: Collection) -> CollectionResponse:
    """Convert Collection model to CollectionResponse."""
    image = None
    if collection.image:
        # Handle both object and dict formats
        if hasattr(collection.image, 'id'):
            image = {
                "id": collection.image.id,
                "src": collection.image.src,
                "alt_text": getattr(collection.image, 'alt_text', None),
                "width": collection.image.width,
                "height": collection.image.height,
            }
        else:
            # Assume dict format
            image = {
                "id": collection.image.get('id'),
                "src": collection.image.get('src'),
                "alt_text": collection.image.get('alt_text'),
                "width": collection.image.get('width'),
                "height": collection.image.get('height'),
            }

    return CollectionResponse(
        id=collection.id,
        title=collection.title,
        handle=collection.handle,
        description=collection.description,
        image=image,
        updated_at=collection.updated_at.isoformat() if collection.updated_at else None,
        sort_order=collection.sort_order
    )


@router.get("/", response_model=CollectionListResponse)
async def get_collections(
    limit: int = Query(20, ge=1, le=50, description="Maximum number of collections"),
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get all collections from the Shopify store.

    Retrieves a list of all product collections with basic information.
    Collections are groups of products that can be used for categorization.
    """
    try:
        async with shopify:
            collections = await shopify.get_collections(limit=limit)

            collection_responses = [_collection_to_response(collection) for collection in collections]

            return CollectionListResponse(
                collections=collection_responses,
                count=len(collection_responses)
            )

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a specific collection by ID.

    Retrieves detailed information about a single collection including
    description, images, and sorting configuration.
    """
    try:
        async with shopify:
            collections = await shopify.get_collections(limit=100)  # Get all and filter
            collection = next((c for c in collections if c.id == collection_id), None)

            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")

            return _collection_to_response(collection)

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/handle/{handle}", response_model=CollectionResponse)
async def get_collection_by_handle(
    handle: str,
    shopify: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a collection by its handle (URL-friendly identifier).

    Collection handles are typically used in URLs and are human-readable
    versions of collection titles.
    """
    try:
        async with shopify:
            collections = await shopify.get_collections(limit=100)  # Get all and filter
            collection = next((c for c in collections if c.handle == handle), None)

            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")

            return _collection_to_response(collection)

    except ShopifyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")