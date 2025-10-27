"""
Shopify service layer for high-level operations.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal

from loguru import logger

from .client import ShopifyClient
from .models import (
    Product, ProductVariant, Image, Money, InventoryLevel, Order, Customer,
    Collection, ShopifyError, ShopifyConfig, Shop
)
from .parsers import (
    parse_product_data, parse_order_data, parse_customer_data,
    parse_collection_data, parse_shop_data
)


class ShopifyService:
    """High-level service for Shopify operations."""

    def __init__(self, config: Optional[ShopifyConfig] = None):
        """Initialize the Shopify service."""
        self.client = ShopifyClient(config)

    async def __aenter__(self):
        """Async context manager entry."""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self):
        """Close the underlying client."""
        await self.client.close()

    # Product Operations

    async def search_products(self,
                             query: str,
                             limit: int = 20,
                             offset: int = 0,
                             sort_by: str = "RELEVANCE",
                             reverse: bool = False) -> Tuple[List[Product], bool]:
        """
        Search for products based on query.

        Args:
            query: Search query string
            limit: Maximum number of results
            offset: Pagination offset
            sort_by: Sort field (TITLE, PRICE, CREATED_AT, etc.)
            reverse: Sort in descending order

        Returns:
            Tuple of (products list, has_more_pages)
        """
        try:
            logger.info(f"Searching products with query: {query}, limit: {limit}")

            # Convert offset to GraphQL cursor
            after = None
            if offset > 0:
                # For simplicity, we'll fetch from the beginning and skip
                # In production, you'd want to use proper cursor pagination
                pass

            response = await self.client.search_products(
                query=query,
                first=limit + offset,  # Fetch extra to handle offset
                after=after
            )

            products_data = response.get("data", {}).get("products", {})
            edges = products_data.get("edges", [])

            # Apply offset
            if offset > 0:
                edges = edges[offset:]

            # Limit results
            edges = edges[:limit]

            products = []
            for edge in edges:
                product = self._parse_product(edge["node"])
                products.append(product)

            page_info = products_data.get("pageInfo", {})
            has_more = page_info.get("hasNextPage", False)

            logger.info(f"Found {len(products)} products, has_more: {has_more}")
            return products, has_more

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            raise ShopifyError(f"Failed to search products: {str(e)}")

    async def get_product_by_id(self, product_id: str) -> Product:
        """Get a specific product by ID."""
        try:
            logger.info(f"Getting product by ID: {product_id}")
            response = await self.client.get_product_by_id(product_id)

            product_data = response.get("data", {}).get("product")
            if not product_data:
                raise ShopifyError(f"Product not found: {product_id}")

            product = self._parse_product(product_data)
            logger.info(f"Successfully retrieved product: {product.title}")
            return product

        except Exception as e:
            logger.error(f"Error getting product by ID: {e}")
            raise ShopifyError(f"Failed to get product: {str(e)}")

    async def get_product_by_handle(self, handle: str) -> Product:
        """Get a product by its handle (URL-friendly identifier)."""
        try:
            logger.info(f"Getting product by handle: {handle}")
            response = await self.client.get_product_by_handle(handle)

            product_data = response.get("data", {}).get("product")
            if not product_data:
                raise ShopifyError(f"Product not found with handle: {handle}")

            product = self._parse_product(product_data)
            logger.info(f"Successfully retrieved product: {product.title}")
            return product

        except Exception as e:
            logger.error(f"Error getting product by handle: {e}")
            raise ShopifyError(f"Failed to get product: {str(e)}")

    async def get_products_in_collection(self,
                                        collection_id: str,
                                        limit: int = 20,
                                        offset: int = 0,
                                        sort_by: str = "TITLE") -> Tuple[List[Product], bool]:
        """Get products in a specific collection."""
        try:
            logger.info(f"Getting products for collection: {collection_id}")

            response = await self.client.get_collection_products(
                collection_id=collection_id,
                first=limit + offset,
                sort_key=sort_by
            )

            products_data = response.get("data", {}).get("products", {})
            edges = products_data.get("edges", [])

            # Apply offset
            if offset > 0:
                edges = edges[offset:]

            # Limit results
            edges = edges[:limit]

            products = []
            for edge in edges:
                product = self._parse_product(edge["node"])
                products.append(product)

            page_info = products_data.get("pageInfo", {})
            has_more = page_info.get("hasNextPage", False)

            logger.info(f"Found {len(products)} products in collection")
            return products, has_more

        except Exception as e:
            logger.error(f"Error getting collection products: {e}")
            raise ShopifyError(f"Failed to get collection products: {str(e)}")

    async def get_product_recommendations(self,
                                        product_id: str,
                                        limit: int = 5) -> List[Product]:
        """
        Get product recommendations based on a given product.
        This uses product type, tags, and vendor to find similar products.
        """
        try:
            logger.info(f"Getting recommendations for product: {product_id}")

            # First get the original product to understand its attributes
            original_product = await self.get_product_by_id(product_id)

            # Build search query based on product attributes
            search_terms = []

            # Search by product type
            if original_product.product_type:
                search_terms.append(f"product_type:{original_product.product_type}")

            # Search by vendor
            if original_product.vendor:
                search_terms.append(f"vendor:{original_product.vendor}")

            # Search by tags (limit to a few relevant ones)
            if original_product.tags:
                # Use first 2-3 tags for similarity
                relevant_tags = original_product.tags[:3]
                for tag in relevant_tags:
                    search_terms.append(f"tag:{tag}")

            search_query = " OR ".join(search_terms)

            # Search for similar products
            products, _ = await self.search_products(
                query=search_query,
                limit=limit + 5  # Get more results to filter
            )

            # Filter out the original product and limit to requested number
            recommendations = [
                p for p in products if p.id != product_id
            ][:limit]

            logger.info(f"Found {len(recommendations)} recommendations")
            return recommendations

        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            raise ShopifyError(f"Failed to get recommendations: {str(e)}")

    # Inventory Operations

    async def check_inventory_availability(self,
                                          variant_ids: List[str]) -> Dict[str, int]:
        """Check inventory availability for multiple product variants."""
        try:
            logger.info(f"Checking inventory for {len(variant_ids)} variants")

            response = await self.client.get_inventory_levels(
                inventory_item_ids=variant_ids
            )

            nodes = response.get("data", {}).get("nodes", [])
            inventory_levels = {}

            for node in nodes:
                inventory_levels[node["id"]] = node["tracked"]

                # Get inventory levels for this item
                levels_data = node.get("inventoryLevels", {}).get("edges", [])
                total_available = 0

                for level_edge in levels_data:
                    total_available += level_edge["node"]["available"]

                inventory_levels[node["id"]] = total_available

            logger.info(f"Retrieved inventory levels for {len(inventory_levels)} variants")
            return inventory_levels

        except Exception as e:
            logger.error(f"Error checking inventory: {e}")
            raise ShopifyError(f"Failed to check inventory: {str(e)}")

    async def is_variant_available(self, variant_id: str) -> bool:
        """Check if a specific variant is available."""
        try:
            inventory_levels = await self.check_inventory_availability([variant_id])
            return inventory_levels.get(variant_id, 0) > 0
        except Exception as e:
            logger.error(f"Error checking variant availability: {e}")
            return False

    # Order Operations

    async def get_customer_orders(self,
                                 customer_id: str,
                                 limit: int = 10) -> List[Order]:
        """Get orders for a specific customer."""
        try:
            logger.info(f"Getting orders for customer: {customer_id}")

            response = await self.client.get_orders_by_customer(customer_id, limit)

            orders_data = response.get("orders", [])
            orders = []

            for order_data in orders_data:
                order = self._parse_order(order_data)
                orders.append(order)

            logger.info(f"Found {len(orders)} orders for customer")
            return orders

        except Exception as e:
            logger.error(f"Error getting customer orders: {e}")
            raise ShopifyError(f"Failed to get customer orders: {str(e)}")

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get detailed status information for an order."""
        try:
            logger.info(f"Getting order status: {order_id}")

            response = await self.client.get_order_by_id(order_id)
            order_data = response.get("order", {})

            order = self._parse_order(order_data)

            return {
                "order_id": order.id,
                "order_number": order.order_number,
                "financial_status": order.financial_status,
                "fulfillment_status": order.fulfillment_status,
                "is_paid": order.is_paid,
                "is_fulfilled": order.is_fulfilled,
                "is_cancelled": order.is_cancelled,
                "total_price": str(order.total_price.amount),
                "currency": order.total_price.currency_code,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                "cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
                "cancel_reason": order.cancel_reason
            }

        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            raise ShopifyError(f"Failed to get order status: {str(e)}")

    # Customer Operations

    async def search_customers(self,
                              query: str,
                              limit: int = 10) -> List[Customer]:
        """Search for customers."""
        try:
            logger.info(f"Searching customers with query: {query}")

            response = await self.client.search_customers(query, limit)

            customers_data = response.get("customers", [])
            customers = []

            for customer_data in customers_data:
                customer = self._parse_customer(customer_data)
                customers.append(customer)

            logger.info(f"Found {len(customers)} customers")
            return customers

        except Exception as e:
            logger.error(f"Error searching customers: {e}")
            raise ShopifyError(f"Failed to search customers: {str(e)}")

    # Collection Operations

    async def get_collections(self, limit: int = 20) -> List[Collection]:
        """Get product collections."""
        try:
            logger.info(f"Getting collections, limit: {limit}")

            response = await self.client.get_collections(first=limit)

            collections_data = response.get("data", {}).get("collections", {})
            edges = collections_data.get("edges", [])

            collections = []
            for edge in edges:
                collection = self._parse_collection(edge["node"])
                collections.append(collection)

            logger.info(f"Found {len(collections)} collections")
            return collections

        except Exception as e:
            logger.error(f"Error getting collections: {e}")
            raise ShopifyError(f"Failed to get collections: {str(e)}")

    # Comparison Operations

    async def compare_products(self, product_ids: List[str]) -> List[Product]:
        """Compare multiple products by fetching their details."""
        try:
            logger.info(f"Comparing {len(product_ids)} products")

            products = []
            for product_id in product_ids:
                try:
                    product = await self.get_product_by_id(product_id)
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to get product {product_id} for comparison: {e}")

            logger.info(f"Successfully retrieved {len(products)} products for comparison")
            return products

        except Exception as e:
            logger.error(f"Error comparing products: {e}")
            raise ShopifyError(f"Failed to compare products: {str(e)}")

    # Health Check

    async def health_check(self) -> bool:
        """Check if the Shopify service is healthy."""
        try:
            return await self.client.health_check()
        except Exception as e:
            logger.error(f"Shopify service health check failed: {e}")
            return False

    # Shop Operations

    async def get_shop_info(self) -> Shop:
        """Get shop information."""
        try:
            logger.info("Getting shop information")
            response = await self.client.get_shop()
            shop_data = response.get('shop', {})
            shop = parse_shop_data(shop_data)
            logger.info(f"Retrieved shop: {shop.name}")
            return shop

        except Exception as e:
            logger.error(f"Error getting shop info: {e}")
            raise ShopifyError(f"Failed to get shop info: {str(e)}")

    # Helper Methods (Using new parsers)

    def _parse_product(self, product_data: Dict[str, Any]) -> Product:
        """Parse product data using the new parser."""
        return parse_product_data(product_data)

    def _parse_order(self, order_data: Dict[str, Any]) -> Order:
        """Parse order data using the new parser."""
        return parse_order_data(order_data)

    def _parse_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Parse customer data using the new parser."""
        return parse_customer_data(customer_data)

    def _parse_collection(self, collection_data: Dict[str, Any]) -> Collection:
        """Parse collection data using the new parser."""
        return parse_collection_data(collection_data)

    def _parse_order(self, order_data: Dict[str, Any]) -> Order:
        """Parse order data from Shopify API response."""
        # Parse line items
        line_items = []
        for item_data in order_data.get("lineItems", []):
            price_data = item_data.get("price", "")
            total_discount_data = item_data.get("totalDiscount", "")

            line_item = LineItem(
                id=item_data.get("id", ""),
                product_id=item_data.get("productId", ""),
                variant_id=item_data.get("variantId", ""),
                title=item_data.get("title", ""),
                quantity=item_data.get("quantity", 0),
                price=Money(
                    amount=Decimal(price_data),
                    currency_code=order_data.get("currencyCode", "USD")
                ),
                total_discount=Money(
                    amount=Decimal(total_discount_data),
                    currency_code=order_data.get("currencyCode", "USD")
                ),
                sku=item_data.get("sku"),
                vendor=item_data.get("vendor"),
                product_title=item_data.get("productTitle"),
                variant_title=item_data.get("variantTitle"),
                taxable=item_data.get("taxable", True),
                requires_shipping=item_data.get("requiresShipping", True)
            )
            line_items.append(line_item)

        # Parse customer
        customer_data = order_data.get("customer")
        customer = None
        if customer_data:
            customer = self._parse_customer(customer_data)

        return Order(
            id=order_data.get("id", ""),
            order_number=order_data.get("orderNumber", 0),
            email=order_data.get("email"),
            phone=order_data.get("phone"),
            financial_status=order_data.get("financialStatus", ""),
            fulfillment_status=order_data.get("fulfillmentStatus"),
            currency_code=order_data.get("currencyCode", ""),
            total_price=Money(
                amount=Decimal(order_data.get("totalPrice", "0")),
                currency_code=order_data.get("currencyCode", "USD")
            ),
            subtotal_price=Money(
                amount=Decimal(order_data.get("subtotalPrice", "0")),
                currency_code=order_data.get("currencyCode", "USD")
            ),
            total_tax=Money(
                amount=Decimal(order_data.get("totalTax", "0")),
                currency_code=order_data.get("currencyCode", "USD")
            ),
            total_shipping_price=Money(
                amount=Decimal(order_data.get("totalShippingPrice", "0")),
                currency_code=order_data.get("currencyCode", "USD")
            ),
            total_discounts=Money(
                amount=Decimal(order_data.get("totalDiscounts", "0")),
                currency_code=order_data.get("currencyCode", "USD")
            ),
            line_items=line_items,
            shipping_lines=[],  # Would need to parse if needed
            customer=customer,
            created_at=datetime.fromisoformat(order_data.get("createdAt", "").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(order_data.get("updatedAt", "").replace("Z", "+00:00")),
            processed_at=datetime.fromisoformat(order_data.get("processedAt", "").replace("Z", "+00:00")) if order_data.get("processedAt") else None,
            cancelled_at=datetime.fromisoformat(order_data.get("cancelledAt", "").replace("Z", "+00:00")) if order_data.get("cancelledAt") else None,
            cancel_reason=order_data.get("cancelReason")
        )

    def _parse_customer(self, customer_data: Dict[str, Any]) -> Customer:
        """Parse customer data from Shopify API response."""
        # Parse addresses
        addresses = []
        for addr_data in customer_data.get("addresses", []):
            address = CustomerAddress(
                id=addr_data.get("id", ""),
                first_name=addr_data.get("firstName"),
                last_name=addr_data.get("lastName"),
                address1=addr_data.get("address1"),
                address2=addr_data.get("address2"),
                city=addr_data.get("city"),
                province=addr_data.get("province"),
                country=addr_data.get("country"),
                zip=addr_data.get("zip"),
                phone=addr_data.get("phone"),
                province_code=addr_data.get("provinceCode"),
                country_code=addr_data.get("countryCode"),
                country_name=addr_data.get("countryName"),
                default=addr_data.get("default", False)
            )
            addresses.append(address)

        total_spent_data = customer_data.get("totalSpent", {})
        return Customer(
            id=customer_data.get("id", ""),
            email=customer_data.get("email"),
            first_name=customer_data.get("firstName"),
            last_name=customer_data.get("lastName"),
            phone=customer_data.get("phone"),
            addresses=addresses,
            orders_count=customer_data.get("ordersCount", 0),
            total_spent=Money(
                amount=Decimal(total_spent_data.get("amount", "0")),
                currency_code=total_spent_data.get("currencyCode", "USD")
            ),
            state=customer_data.get("state", ""),
            verified_email=customer_data.get("verifiedEmail", False),
            tax_exempt=customer_data.get("taxExempt", False),
            tags=customer_data.get("tags", []),
            created_at=datetime.fromisoformat(customer_data.get("createdAt", "").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(customer_data.get("updatedAt", "").replace("Z", "+00:00"))
        )

    def _parse_collection(self, collection_data: Dict[str, Any]) -> Collection:
        """Parse collection data from Shopify API response."""
        # Parse image
        image = None
        image_data = collection_data.get("image")
        if image_data:
            image = Image(
                id=image_data.get("id", ""),
                src=image_data.get("src", ""),
                alt_text=image_data.get("altText"),
                width=image_data.get("width"),
                height=image_data.get("height")
            )

        return Collection(
            id=collection_data.get("id", ""),
            title=collection_data.get("title", ""),
            handle=collection_data.get("handle", ""),
            description=collection_data.get("description"),
            description_html=collection_data.get("descriptionHtml"),
            image=image,
            published_at=datetime.fromisoformat(collection_data.get("publishedAt", "").replace("Z", "+00:00")) if collection_data.get("publishedAt") else None,
            updated_at=datetime.fromisoformat(collection_data.get("updatedAt", "").replace("Z", "+00:00")),
            sort_order=collection_data.get("sortOrder", "MANUAL")
        )