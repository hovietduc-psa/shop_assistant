"""
Tests for Shopify service integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import Product, ProductVariant, Money, Image
from app.integrations.shopify.exceptions import (
    ShopifyError,
    ShopifyNotFoundError,
    ShopifyRateLimitError
)


@pytest.fixture
def mock_shopify_client():
    """Create a mock Shopify client."""
    client = AsyncMock()
    return client


@pytest.fixture
def shopify_service(mock_shopify_client):
    """Create Shopify service with mocked client."""
    service = ShopifyService()
    service.client = mock_shopify_client
    return service


@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "id": "gid://shopify/Product/123456789",
        "title": "Test Product",
        "handle": "test-product",
        "description": "A test product",
        "productType": "Test Type",
        "vendor": "Test Vendor",
        "status": "ACTIVE",
        "tags": ["test", "sample"],
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "publishedAt": "2024-01-01T00:00:00Z",
        "images": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/ProductImage/987654321",
                        "src": "https://example.com/image.jpg",
                        "altText": "Test Image",
                        "width": 800,
                        "height": 600,
                        "position": 1
                    }
                }
            ]
        },
        "variants": {
            "edges": [
                {
                    "node": {
                        "id": "gid://shopify/ProductVariant/555555555",
                        "title": "Small",
                        "sku": "TEST-SMALL",
                        "price": {
                            "amount": "19.99",
                            "currencyCode": "USD"
                        },
                        "inventoryQuantity": 10,
                        "availableForSale": True,
                        "createdAt": "2024-01-01T00:00:00Z",
                        "updatedAt": "2024-01-01T00:00:00Z"
                    }
                }
            ]
        },
        "options": [
            {
                "id": "gid://shopify/ProductOption/111111111",
                "name": "Size",
                "values": ["Small", "Medium", "Large"]
            }
        ]
    }


@pytest.mark.asyncio
async def test_search_products_success(shopify_service, mock_shopify_client, sample_product_data):
    """Test successful product search."""
    # Mock the client response
    mock_response = {
        "data": {
            "products": {
                "edges": [
                    {"node": sample_product_data}
                ],
                "pageInfo": {
                    "hasNextPage": False
                }
            }
        }
    }
    mock_shopify_client.search_products.return_value = mock_response

    # Execute the search
    products, has_more = await shopify_service.search_products(
        query="test",
        limit=10
    )

    # Verify results
    assert len(products) == 1
    assert has_more == False
    assert products[0].title == "Test Product"
    assert products[0].handle == "test-product"

    # Verify client was called correctly
    mock_shopify_client.search_products.assert_called_once_with(
        query="test",
        first=10,
        after=None
    )


@pytest.mark.asyncio
async def test_get_product_by_id_success(shopify_service, mock_shopify_client, sample_product_data):
    """Test successful product retrieval by ID."""
    # Mock the client response
    mock_response = {
        "data": {
            "product": sample_product_data
        }
    }
    mock_shopify_client.get_product_by_id.return_value = mock_response

    # Execute the retrieval
    product = await shopify_service.get_product_by_id("gid://shopify/Product/123456789")

    # Verify results
    assert product.title == "Test Product"
    assert product.id == "gid://shopify/Product/123456789"
    assert len(product.variants) == 1
    assert len(product.images) == 1

    # Verify client was called correctly
    mock_shopify_client.get_product_by_id.assert_called_once_with(
        "gid://shopify/Product/123456789"
    )


@pytest.mark.asyncio
async def test_get_product_by_id_not_found(shopify_service, mock_shopify_client):
    """Test product retrieval when product is not found."""
    # Mock the client response for not found
    mock_response = {
        "data": {
            "product": None
        }
    }
    mock_shopify_client.get_product_by_id.return_value = mock_response

    # Execute and verify exception
    with pytest.raises(ShopifyNotFoundError, match="Product not found"):
        await shopify_service.get_product_by_id("gid://shopify/Product/invalid")


@pytest.mark.asyncio
async def test_search_products_rate_limit_error(shopify_service, mock_shopify_client):
    """Test handling of rate limit errors during product search."""
    # Mock rate limit error
    mock_shopify_client.search_products.side_effect = ShopifyRateLimitError(
        "Rate limit exceeded",
        retry_after=30
    )

    # Execute and verify exception
    with pytest.raises(ShopifyRateLimitError, match="Rate limit exceeded"):
        await shopify_service.search_products(query="test")


@pytest.mark.asyncio
async def test_get_product_recommendations_success(shopify_service, mock_shopify_client, sample_product_data):
    """Test successful product recommendations."""
    # Mock product retrieval for original product
    mock_original_response = {
        "data": {
            "product": sample_product_data
        }
    }
    mock_shopify_client.get_product_by_id.return_value = mock_original_response

    # Mock search results for similar products
    mock_search_response = {
        "data": {
            "products": {
                "edges": [
                    {"node": sample_product_data}
                ],
                "pageInfo": {
                    "hasNextPage": False
                }
            }
        }
    }
    mock_shopify_client.search_products.return_value = mock_search_response

    # Execute the recommendations
    recommendations = await shopify_service.get_product_recommendations(
        product_id="gid://shopify/Product/123456789",
        limit=5
    )

    # Verify results
    assert len(recommendations) == 1
    assert recommendations[0].title == "Test Product"


@pytest.mark.asyncio
async def test_check_inventory_availability(shopify_service, mock_shopify_client):
    """Test inventory availability checking."""
    # Mock inventory response
    mock_response = {
        "data": {
            "nodes": [
                {
                    "id": "gid://shopify/InventoryItem/111111111",
                    "tracked": True,
                    "inventoryLevels": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/InventoryLevel/222222222",
                                    "available": 15,
                                    "locationId": "gid://shopify/Location/333333333",
                                    "updatedAt": "2024-01-01T00:00:00Z"
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    mock_shopify_client.get_inventory_levels.return_value = mock_response

    # Execute the check
    inventory_levels = await shopify_service.check_inventory_availability(
        variant_ids=["gid://shopify/ProductVariant/111111111"]
    )

    # Verify results
    assert len(inventory_levels) == 1
    assert inventory_levels["gid://shopify/InventoryItem/111111111"] == 15


@pytest.mark.asyncio
async def test_compare_products_success(shopify_service, mock_shopify_client, sample_product_data):
    """Test successful product comparison."""
    # Mock the client response for each product
    mock_shopify_client.get_product_by_id.return_value = {
        "data": {
            "product": sample_product_data
        }
    }

    # Execute the comparison
    products = await shopify_service.compare_products(
        product_ids=[
            "gid://shopify/Product/123456789",
            "gid://shopify/Product/987654321"
        ]
    )

    # Verify results
    assert len(products) == 2
    assert all(p.title == "Test Product" for p in products)

    # Verify client was called correctly
    assert mock_shopify_client.get_product_by_id.call_count == 2


@pytest.mark.asyncio
async def test_is_variant_available_true(shopify_service, mock_shopify_client):
    """Test variant availability check when available."""
    # Mock inventory response with available items
    mock_response = {
        "data": {
            "nodes": [
                {
                    "id": "gid://shopify/InventoryItem/111111111",
                    "inventoryLevels": {
                        "edges": [
                            {
                                "node": {
                                    "available": 5
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    mock_shopify_client.get_inventory_levels.return_value = mock_response

    # Execute the check
    is_available = await shopify_service.is_variant_available(
        variant_id="gid://shopify/ProductVariant/111111111"
    )

    # Verify result
    assert is_available == True


@pytest.mark.asyncio
async def test_is_variant_available_false(shopify_service, mock_shopify_client):
    """Test variant availability check when not available."""
    # Mock inventory response with no available items
    mock_response = {
        "data": {
            "nodes": [
                {
                    "id": "gid://shopify/InventoryItem/111111111",
                    "inventoryLevels": {
                        "edges": [
                            {
                                "node": {
                                    "available": 0
                                }
                            }
                        ]
                    }
                }
            ]
        }
    }
    mock_shopify_client.get_inventory_levels.return_value = mock_response

    # Execute the check
    is_available = await shopify_service.is_variant_available(
        variant_id="gid://shopify/ProductVariant/111111111"
    )

    # Verify result
    assert is_available == False


@pytest.mark.asyncio
async def test_health_check_success(shopify_service, mock_shopify_client):
    """Test successful health check."""
    # Mock successful health check
    mock_shopify_client.health_check.return_value = True

    # Execute the health check
    is_healthy = await shopify_service.health_check()

    # Verify result
    assert is_healthy == True


@pytest.mark.asyncio
async def test_health_check_failure(shopify_service, mock_shopify_client):
    """Test failed health check."""
    # Mock failed health check
    mock_shopify_client.health_check.return_value = False

    # Execute the health check
    is_healthy = await shopify_service.health_check()

    # Verify result
    assert is_healthy == False


@pytest.mark.asyncio
async def test_context_manager(shopify_service, mock_shopify_client):
    """Test that ShopifyService works as a context manager."""
    # Mock the client context manager
    async_context = AsyncMock()
    async_context.__aenter__ = AsyncMock(return_value=mock_shopify_client)
    async_context.__aexit__ = AsyncMock(return_value=None)

    shopify_service.client = async_context

    # Use as context manager
    async with shopify_service as service:
        # Mock a successful operation
        mock_shopify_client.search_products.return_value = {
            "data": {
                "products": {
                    "edges": [],
                    "pageInfo": {"hasNextPage": False}
                }
            }
        }

        products, _ = await service.search_products(query="test")
        assert products == []

    # Verify context manager methods were called
    async_context.__aenter__.assert_called_once()
    async_context.__aexit__.assert_called_once()