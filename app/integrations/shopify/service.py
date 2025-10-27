"""
Shopify service layer for high-level operations.

Updated to use the new parsers based on the actual Shopify schema from Makezbright Gifts store.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from decimal import Decimal

from loguru import logger

from .client import ShopifyClient
from .models import (
    Product, ProductVariant, Image, Money, InventoryLevel, Order, Customer,
    Collection, ShopifyError, ShopifyConfig, Shop, ShopPolicy, ShopPolicies,
    PrivacyPolicy, RefundPolicy, TermsOfService, ShippingPolicy,
    SubscriptionPolicy, LegalNoticePolicy, PolicyQuery, PolicyResponse,
    PolicySummary
)
from .parsers import (
    parse_product_data, parse_order_data, parse_customer_data,
    parse_collection_data, parse_shop_data, parse_policy_data,
    parse_shop_policies_response, parse_policy_response, create_policy_summary
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

    # Shop Operations

    async def get_shop_info(self) -> Shop:
        """Get shop information."""
        try:
            logger.info("Getting shop information")
            response = await self.client.get_shop_info()
            shop_data = response.get('shop', {})
            shop = parse_shop_data(shop_data)
            logger.info(f"Retrieved shop: {shop.name}")
            return shop

        except Exception as e:
            logger.error(f"Error getting shop info: {e}")
            raise ShopifyError(f"Failed to get shop info: {str(e)}")

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
                product = parse_product_data(edge["node"])
                products.append(product)

            page_info = products_data.get("pageInfo", {})
            has_more = page_info.get("hasNextPage", False)

            logger.info(f"Found {len(products)} products, has_more: {has_more}")
            return products, has_more

        except Exception as e:
            logger.error(f"Error searching products: {e}")
            raise ShopifyError(f"Failed to search products: {str(e)}")

    async def get_product_by_id(self, product_id: str) -> Product:
        """Get a product by ID."""
        try:
            logger.info(f"Getting product by ID: {product_id}")

            response = await self.client.get_product_by_id(product_id)
            product_data = response.get("data", {}).get("product", {})

            if not product_data:
                raise ShopifyError(f"Product not found: {product_id}")

            product = parse_product_data(product_data)
            logger.info(f"Retrieved product: {product.title}")
            return product

        except Exception as e:
            logger.error(f"Error getting product by ID: {e}")
            raise ShopifyError(f"Failed to get product: {str(e)}")

    async def get_products_by_ids(self, product_ids: List[str]) -> List[Product]:
        """Get multiple products by their IDs."""
        try:
            logger.info(f"Getting {len(product_ids)} products by IDs")

            products = []
            for product_id in product_ids:
                try:
                    product = await self.get_product_by_id(product_id)
                    products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to get product {product_id}: {e}")

            logger.info(f"Successfully retrieved {len(products)} products")
            return products

        except Exception as e:
            logger.error(f"Error getting products by IDs: {e}")
            raise ShopifyError(f"Failed to get products: {str(e)}")

    async def get_product_recommendations(self, product_id: str, limit: int = 10) -> List[Product]:
        """Get product recommendations for a given product."""
        try:
            logger.info(f"Getting recommendations for product: {product_id}")

            # First get the product to understand its characteristics
            product = await self.get_product_by_id(product_id)

            # Search for similar products based on product type, tags, and vendor
            similar_products = []

            # Search by product type
            if product.product_type:
                type_response = await self.client.search_products(
                    query=f"product_type:{product.product_type}",
                    first=limit + 1  # +1 to exclude the original product
                )
                type_edges = type_response.get("data", {}).get("products", {}).get("edges", [])
                for edge in type_edges:
                    if edge["node"]["id"] != product_id:  # Exclude original product
                        similar_products.append(parse_product_data(edge["node"]))

            # Search by vendor if we need more recommendations
            if len(similar_products) < limit and product.vendor:
                vendor_response = await self.client.search_products(
                    query=f"vendor:{product.vendor}",
                    first=limit - len(similar_products) + 1
                )
                vendor_edges = vendor_response.get("data", {}).get("products", {}).get("edges", [])
                for edge in vendor_edges:
                    if edge["node"]["id"] != product_id:  # Exclude original product
                        similar_product = parse_product_data(edge["node"])
                        # Avoid duplicates
                        if not any(p.id == similar_product.id for p in similar_products):
                            similar_products.append(similar_product)

            # Limit to requested number
            recommendations = similar_products[:limit]

            logger.info(f"Found {len(recommendations)} recommendations for product {product_id}")
            return recommendations

        except Exception as e:
            logger.error(f"Error getting product recommendations: {e}")
            raise ShopifyError(f"Failed to get recommendations: {str(e)}")

    # Order Operations

    async def get_order_by_id(self, order_id: str) -> Order:
        """Get an order by ID."""
        try:
            logger.info(f"Getting order by ID: {order_id}")

            response = await self.client.get_order_by_id(order_id)
            order_data = response.get("order", {})

            if not order_data:
                raise ShopifyError(f"Order not found: {order_id}")

            order = parse_order_data(order_data)
            logger.info(f"Retrieved order: {order.name}")
            return order

        except Exception as e:
            logger.error(f"Error getting order by ID: {e}")
            raise ShopifyError(f"Failed to get order: {str(e)}")

    async def get_orders_by_customer(self, customer_id: str, limit: int = 20) -> List[Order]:
        """Get orders for a specific customer."""
        try:
            logger.info(f"Getting orders for customer: {customer_id}")

            response = await self.client.get_orders_by_customer(customer_id, limit)
            orders_data = response.get("orders", [])

            orders = []
            for order_data in orders_data:
                order = parse_order_data(order_data)
                orders.append(order)

            logger.info(f"Found {len(orders)} orders for customer {customer_id}")
            return orders

        except Exception as e:
            logger.error(f"Error getting orders by customer: {e}")
            raise ShopifyError(f"Failed to get orders: {str(e)}")

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get the current status of an order."""
        try:
            logger.info(f"Getting order status: {order_id}")

            response = await self.client.get_order_by_id(order_id)
            order_data = response.get("order", {})

            order = parse_order_data(order_data)

            return {
                "order_id": order.id,
                "order_number": order.order_number,
                "name": order.name,
                "financial_status": order.financial_status,
                "fulfillment_status": order.fulfillment_status,
                "is_paid": order.is_paid,
                "is_fulfilled": order.is_fulfilled,
                "is_cancelled": order.is_cancelled,
                "total_price": order.total_price,
                "currency": order.currency,
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
                customer = parse_customer_data(customer_data)
                customers.append(customer)

            logger.info(f"Found {len(customers)} customers")
            return customers

        except Exception as e:
            logger.error(f"Error searching customers: {e}")
            raise ShopifyError(f"Failed to search customers: {str(e)}")

    async def get_customer_by_id(self, customer_id: str) -> Customer:
        """Get a customer by ID."""
        try:
            logger.info(f"Getting customer by ID: {customer_id}")

            response = await self.client.get_customer_by_id(customer_id)
            customer_data = response.get("customer", {})

            if not customer_data:
                raise ShopifyError(f"Customer not found: {customer_id}")

            customer = parse_customer_data(customer_data)
            logger.info(f"Retrieved customer: {customer.email}")
            return customer

        except Exception as e:
            logger.error(f"Error getting customer by ID: {e}")
            raise ShopifyError(f"Failed to get customer: {str(e)}")

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
                collection = parse_collection_data(edge["node"])
                collections.append(collection)

            logger.info(f"Found {len(collections)} collections")
            return collections

        except Exception as e:
            logger.error(f"Error getting collections: {e}")
            raise ShopifyError(f"Failed to get collections: {str(e)}")

    async def get_collection_by_id(self, collection_id: str) -> Collection:
        """Get a collection by ID."""
        try:
            logger.info(f"Getting collection by ID: {collection_id}")

            response = await self.client.get_collection_by_id(collection_id)
            collection_data = response.get("data", {}).get("collection", {})

            if not collection_data:
                raise ShopifyError(f"Collection not found: {collection_id}")

            collection = parse_collection_data(collection_data)
            logger.info(f"Retrieved collection: {collection.title}")
            return collection

        except Exception as e:
            logger.error(f"Error getting collection by ID: {e}")
            raise ShopifyError(f"Failed to get collection: {str(e)}")

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

    # Additional missing methods

    async def get_products_in_collection(self,
                                        collection_id: str,
                                        limit: int = 20,
                                        offset: int = 0) -> Tuple[List[Product], bool]:
        """Get products in a specific collection."""
        try:
            logger.info(f"Getting products for collection: {collection_id}")

            response = await self.client.get_collection_products(
                collection_id=collection_id,
                first=limit + offset
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
                product = parse_product_data(edge["node"])
                products.append(product)

            page_info = products_data.get("pageInfo", {})
            has_more = page_info.get("hasNextPage", False)

            logger.info(f"Found {len(products)} products in collection")
            return products, has_more

        except Exception as e:
            logger.error(f"Error getting products in collection: {e}")
            raise ShopifyError(f"Failed to get products in collection: {str(e)}")

    async def check_inventory_availability(self, variant_ids: List[str]) -> Dict[str, int]:
        """Check inventory availability for multiple variants."""
        try:
            logger.info(f"Checking inventory for {len(variant_ids)} variants")

            response = await self.client.get_inventory_levels(variant_ids)
            inventory_data = response.get("data", {}).get("nodes", [])

            inventory_levels = {}
            for node in inventory_data:
                inventory_item_id = node.get("id", "")
                inventory_levels_data = node.get("inventoryLevels", {}).get("edges", [])

                total_available = 0
                for level_edge in inventory_levels_data:
                    level = level_edge.get("node", {})
                    available = level.get("available", 0)
                    total_available += available

                inventory_levels[inventory_item_id] = total_available

            logger.info(f"Checked inventory for {len(inventory_levels)} variants")
            return inventory_levels

        except Exception as e:
            logger.error(f"Error checking inventory availability: {e}")
            raise ShopifyError(f"Failed to check inventory availability: {str(e)}")

    async def is_variant_available(self, variant_id: str) -> bool:
        """Check if a specific variant is available."""
        try:
            inventory_levels = await self.check_inventory_availability([variant_id])
            return inventory_levels.get(variant_id, 0) > 0
        except Exception as e:
            logger.error(f"Error checking variant availability: {e}")
            return False

    async def get_product_by_handle(self, handle: str) -> Product:
        """Get a product by its handle."""
        try:
            logger.info(f"Getting product by handle: {handle}")

            response = await self.client.get_product_by_handle(handle)
            product_data = response.get("data", {}).get("product", {})

            if not product_data:
                raise ShopifyError(f"Product not found with handle: {handle}")

            product = parse_product_data(product_data)
            logger.info(f"Retrieved product by handle: {product.title}")
            return product

        except Exception as e:
            logger.error(f"Error getting product by handle: {e}")
            raise ShopifyError(f"Failed to get product by handle: {str(e)}")

    async def get_pages(self) -> List[Dict[str, Any]]:
        """Get all pages from Shopify store."""
        try:
            logger.info("Getting all pages from Shopify store")

            # Use REST API to get pages
            pages_endpoint = "pages.json"
            response = await self.client._make_rest_request("GET", pages_endpoint)

            if response and 'pages' in response:
                pages = response['pages']
                logger.info(f"Retrieved {len(pages)} pages from Shopify")
                return pages
            else:
                logger.warning("No pages found in response")
                return []

        except Exception as e:
            logger.error(f"Error getting pages: {e}")
            raise ShopifyError(f"Failed to get pages: {str(e)}")

    # Policy Operations

    async def get_all_policies(self) -> ShopPolicies:
        """Get all shop policies using page-based approach."""
        try:
            logger.info("Getting all shop policies from pages")

            from .page_policies import PagePolicyService
            page_policy_service = PagePolicyService(self)
            policies = await page_policy_service.get_policies_from_pages()

            logger.info(f"Retrieved {policies.policy_count} active policies from pages")
            return policies

        except Exception as e:
            logger.error(f"Error getting all policies from pages: {e}")
            raise ShopifyError(f"Failed to get all policies: {str(e)}")

    async def get_policy(self, policy_type: str) -> Optional[ShopPolicy]:
        """Get a specific policy by type using page-based approach."""
        try:
            logger.info(f"Getting policy: {policy_type}")

            # Get all policies and find the specific one
            policies = await self.get_all_policies()

            # Map policy types to their attributes
            policy_mapping = {
                "refund": policies.refund_policy,
                "shipping": policies.shipping_policy,
                "privacy": policies.privacy_policy,
                "terms": policies.terms_of_service,
                "subscription": policies.subscription_policy,
                "legal": policies.legal_notice_policy
            }

            policy = policy_mapping.get(policy_type)

            if policy:
                logger.info(f"Retrieved policy: {policy.title}")
            else:
                logger.info(f"No policy found for type: {policy_type}")

            return policy

        except Exception as e:
            logger.error(f"Error getting policy {policy_type}: {e}")
            raise ShopifyError(f"Failed to get policy {policy_type}: {str(e)}")

    async def get_policy_summary(self, policy_type: str) -> Optional[PolicySummary]:
        """Get a summary of a specific policy."""
        try:
            policy = await self.get_policy(policy_type)
            if policy:
                return create_policy_summary(policy)
            return None
        except Exception as e:
            logger.error(f"Error getting policy summary for {policy_type}: {e}")
            return None

    async def get_all_policy_summaries(self) -> Dict[str, PolicySummary]:
        """Get summaries of all available policies."""
        try:
            logger.info("Getting all policy summaries")

            policies = await self.get_all_policies()
            summaries = {}

            for policy_name, policy in policies.active_policies.items():
                summaries[policy_name] = create_policy_summary(policy)

            logger.info(f"Created {len(summaries)} policy summaries")
            return summaries

        except Exception as e:
            logger.error(f"Error getting all policy summaries: {e}")
            return {}

    async def search_policies(self, query: PolicyQuery) -> List[PolicyResponse]:
        """Search policies based on a query using page-based approach."""
        try:
            logger.info(f"Searching policies for query: {query.query_type}")

            from .page_policies import PagePolicyService
            page_policy_service = PagePolicyService(self)
            responses = await page_policy_service.search_policies_in_pages(query)

            logger.info(f"Found {len(responses)} policy responses")
            return responses

        except Exception as e:
            logger.error(f"Error searching policies: {e}")
            raise ShopifyError(f"Failed to search policies: {str(e)}")

    async def _create_policy_response(self, policy: ShopPolicy, query: PolicyQuery) -> Optional[PolicyResponse]:
        """Create a policy response based on the query."""
        try:
            policy_content = policy.content

            # If there's a specific question, use AI to answer it
            answer_to_question = None
            confidence_score = None
            relevant_sections = []

            if query.specific_question:
                # This could be enhanced with AI to extract relevant sections and answer questions
                # For now, return the full policy content
                answer_to_question = f"Based on the {policy.title}, here's the relevant information: {policy_content[:500]}..."
                confidence_score = 0.7
                relevant_sections = [policy_content[:200] + "..."]

            return PolicyResponse(
                policy_type=policy.__class__.__name__.lower().replace('policy', ''),
                policy_content=policy_content,
                relevant_sections=relevant_sections,
                answer_to_question=answer_to_question,
                confidence_score=confidence_score,
                additional_info={
                    "policy_url": policy.url,
                    "last_updated": policy.updated_at.isoformat() if policy.updated_at else None,
                    "customer_context": query.customer_context,
                    "order_context": query.order_context,
                    "product_context": query.product_context
                }
            )

        except Exception as e:
            logger.error(f"Error creating policy response: {e}")
            return None

    async def get_refund_policy_details(self) -> Optional[RefundPolicy]:
        """Get refund policy with enhanced parsing."""
        policy = await self.get_policy("refund")
        if policy and isinstance(policy, RefundPolicy):
            return policy
        return None

    async def get_shipping_policy_details(self) -> Optional[ShippingPolicy]:
        """Get shipping policy with enhanced parsing."""
        policy = await self.get_policy("shipping")
        if policy and isinstance(policy, ShippingPolicy):
            return policy
        return None