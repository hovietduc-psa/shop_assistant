"""
Shopify API client for making GraphQL and REST API calls.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx
from loguru import logger

from app.core.config import settings
from .models import ShopifyConfig, ShopifyError, Product, Order, Customer, Collection, WebhookEvent
from .graphql_queries import GraphQLQueryBuilder
from .exceptions import (
    shopify_error_from_response,
    shopify_graphql_error_from_response,
    ShopifyRateLimitError,
    ShopifyTimeoutError,
    ShopifyConnectionError
)


class ShopifyClient:
    """Client for interacting with Shopify's GraphQL and REST APIs."""

    def __init__(self, config: Optional[ShopifyConfig] = None):
        """Initialize the Shopify client."""
        self.config = config or ShopifyConfig(
            shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
            access_token=settings.SHOPIFY_ACCESS_TOKEN,
            api_version=settings.SHOPIFY_API_VERSION,
            webhook_secret=settings.SHOPIFY_WEBHOOK_SECRET,
            app_secret=settings.SHOPIFY_APP_SECRET
        )

        # Validate configuration
        if not self.config.shop_domain:
            raise ShopifyError("Shop domain is required")
        if not self.config.access_token:
            raise ShopifyError("Access token is required")

        # Base URLs
        # Handle domain that already includes .myshopify.com
        if self.config.shop_domain.endswith('.myshopify.com'):
            self.graphql_url = f"https://{self.config.shop_domain}/admin/api/{self.config.api_version}/graphql.json"
        else:
            self.graphql_url = f"https://{self.config.shop_domain}.myshopify.com/admin/api/{self.config.api_version}/graphql.json"
        # Handle domain that already includes .myshopify.com
        if self.config.shop_domain.endswith('.myshopify.com'):
            self.rest_url = f"https://{self.config.shop_domain}/admin/api/{self.config.api_version}"
        else:
            self.rest_url = f"https://{self.config.shop_domain}.myshopify.com/admin/api/{self.config.api_version}"

        # HTTP client configuration
        self.client = httpx.AsyncClient(
            base_url=self.rest_url,
            headers={
                "X-Shopify-Access-Token": self.config.access_token,
                "Content-Type": "application/json",
                "User-Agent": f"ShopAssistant-AI/1.0"
            },
            timeout=30.0
        )

        # Rate limiting
        self.rate_limit_remaining = 40
        self.rate_limit_reset = int(time.time()) + 1
        self.last_request_time = 0

        logger.info(f"Initialized Shopify client for domain: {self.config.shop_domain}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _check_rate_limit(self):
        """Check and handle rate limiting."""
        current_time = int(time.time())

        # If we've hit the rate limit, wait until reset
        if self.rate_limit_remaining <= 1 and current_time < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - current_time + 1
            logger.warning(f"Rate limit reached, waiting {wait_time} seconds")
            raise ShopifyRateLimitError(
                f"Rate limit exceeded. Retry after {wait_time} seconds.",
                retry_after=wait_time
            )

        # Ensure we don't make requests too quickly (Shopify allows 2 requests per second)
        time_since_last = current_time - self.last_request_time
        if time_since_last < 0.5:  # 500ms between requests = 2 requests per second
            await asyncio.sleep(0.5 - time_since_last)

        self.last_request_time = int(time.time())

    def _update_rate_limit(self, headers: Dict[str, str]):
        """Update rate limit information from response headers."""
        try:
            # Shopify REST API rate limit header
            if "X-Shopify-Shop-Api-Call-Limit" in headers:
                call_limit = headers["X-Shopify-Shop-Api-Call-Limit"]
                current, max_limit = map(int, call_limit.split("/"))
                self.rate_limit_remaining = max_limit - current

            # Shopify GraphQL API rate limit header
            elif "X-Shopify-Shop-Api-Call-Limit" in headers:
                call_limit = headers["X-Shopify-Shop-Api-Call-Limit"]
                if "/" in call_limit:
                    current, max_limit = map(int, call_limit.split("/"))
                    self.rate_limit_remaining = max_limit - current
                else:
                    # GraphQL uses a different format
                    self.rate_limit_remaining = int(call_limit)

            # Reset time header (both REST and GraphQL)
            if "X-Rate-Limit-Reset" in headers:
                self.rate_limit_reset = int(headers["X-Rate-Limit-Reset"])

            # Log when rate limit is getting low
            if self.rate_limit_remaining <= 5:
                logger.warning(f"Rate limit running low: {self.rate_limit_remaining} requests remaining")

        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse rate limit headers: {e}")
            # Reset to safe defaults
            self.rate_limit_remaining = 2
            self.rate_limit_reset = int(time.time()) + 30

    async def _make_graphql_request(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GraphQL request to Shopify."""
        await self._check_rate_limit()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            logger.debug(f"Making GraphQL request to {self.graphql_url}")
            response = await self.client.post(
                self.graphql_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            self._update_rate_limit(dict(response.headers))

            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    logger.error(f"GraphQL errors: {data['errors']}")
                    raise shopify_graphql_error_from_response(data["errors"])
                return data
            else:
                error_text = response.text
                logger.error(f"GraphQL request failed: {response.status_code} - {error_text}")
                raise shopify_error_from_response(
                    response.status_code,
                    {"response": error_text}
                )

        except httpx.TimeoutException as e:
            logger.error(f"Timeout during GraphQL request: {e}")
            raise ShopifyTimeoutError(f"Request timeout: {str(e)}")
        except httpx.ConnectError as e:
            logger.error(f"Connection error during GraphQL request: {e}")
            raise ShopifyConnectionError(f"Connection failed: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Network error during GraphQL request: {e}")
            raise ShopifyError(f"Network error: {str(e)}")

    async def _make_rest_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a REST API request to Shopify."""
        await self._check_rate_limit()

        url = f"{self.rest_url}/{endpoint.lstrip('/')}"

        try:
            logger.debug(f"Making {method} request to {url}")
            response = await self.client.request(method, url, json=data)

            self._update_rate_limit(dict(response.headers))

            if response.status_code in [200, 201, 204]:
                if response.status_code == 204:
                    return {}
                return response.json()
            else:
                error_text = response.text
                logger.error(f"REST request failed: {response.status_code} - {error_text}")

                # Try to parse JSON for better error handling
                try:
                    error_data = response.json()
                except:
                    error_data = {"response": error_text}

                raise shopify_error_from_response(response.status_code, error_data)

        except httpx.TimeoutException as e:
            logger.error(f"Timeout during REST request: {e}")
            raise ShopifyTimeoutError(f"Request timeout: {str(e)}")
        except httpx.ConnectError as e:
            logger.error(f"Connection error during REST request: {e}")
            raise ShopifyConnectionError(f"Connection failed: {str(e)}")
        except httpx.RequestError as e:
            logger.error(f"Network error during REST request: {e}")
            raise ShopifyError(f"Network error: {str(e)}")

    # Product Methods

    async def get_products(self,
                          first: int = 10,
                          after: Optional[str] = None,
                          query: Optional[str] = None,
                          sort_key: Optional[str] = None,
                          reverse: bool = False) -> Dict[str, Any]:
        """Get products from Shopify."""
        graphql_query, variables = GraphQLQueryBuilder.get_products_query(
            first=first,
            after=after,
            query=query,
            sort_key=sort_key,
            reverse=reverse
        )

        return await self._make_graphql_request(graphql_query, variables)

    async def get_product_by_id(self, product_id: str) -> Dict[str, Any]:
        """Get a specific product by ID."""
        graphql_query, variables = GraphQLQueryBuilder.get_product_by_id_query(product_id)
        return await self._make_graphql_request(graphql_query, variables)

    async def get_product_by_handle(self, handle: str) -> Dict[str, Any]:
        """Get a product by its handle."""
        query = f"handle:{handle}"
        products_data = await self.get_products(first=1, query=query)

        edges = products_data.get("data", {}).get("products", {}).get("edges", [])
        if not edges:
            raise ShopifyError(f"Product not found with handle: {handle}")

        return {"data": {"product": edges[0]["node"]}}

    async def search_products(self, query: str, first: int = 10, after: Optional[str] = None) -> Dict[str, Any]:
        """Search for products."""
        graphql_query, variables = GraphQLQueryBuilder.search_products_query(
            query=query,
            first=first,
            after=after
        )
        return await self._make_graphql_request(graphql_query, variables)

    # Order Methods

    async def get_orders(self,
                        first: int = 10,
                        after: Optional[str] = None,
                        query: Optional[str] = None,
                        sort_key: str = "UPDATED_AT",
                        reverse: bool = True) -> Dict[str, Any]:
        """Get orders from Shopify."""
        graphql_query, variables = GraphQLQueryBuilder.get_orders_query(
            first=first,
            after=after,
            query=query,
            sort_key=sort_key,
            reverse=reverse
        )
        return await self._make_graphql_request(graphql_query, variables)

    async def get_order_by_id(self, order_id: str) -> Dict[str, Any]:
        """Get a specific order by ID."""
        return await self._make_rest_request("GET", f"orders/{order_id}.json")

    async def get_orders_by_customer(self, customer_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get orders for a specific customer."""
        query = f"customer_id:{customer_id}"
        return await self.get_orders(first=limit, query=query)

    # Inventory Methods

    async def get_inventory_levels(self,
                                  inventory_item_ids: List[str],
                                  location_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get inventory levels for specific items."""
        graphql_query, variables = GraphQLQueryBuilder.get_inventory_levels_query(
            inventory_item_ids=inventory_item_ids,
            location_ids=location_ids
        )
        return await self._make_graphql_request(graphql_query, variables)

    async def get_locations(self) -> Dict[str, Any]:
        """Get all store locations."""
        return await self._make_rest_request("GET", "locations.json")

    # Customer Methods

    async def get_customers(self,
                           first: int = 10,
                           after: Optional[str] = None,
                           query: Optional[str] = None) -> Dict[str, Any]:
        """Get customers from Shopify."""
        endpoint = f"customers.json?limit={first}"
        if after:
            endpoint += f"&page_info={after}"
        if query:
            endpoint += f"&query={query}"

        return await self._make_rest_request("GET", endpoint)

    async def get_customer_by_id(self, customer_id: str) -> Dict[str, Any]:
        """Get a specific customer by ID."""
        return await self._make_rest_request("GET", f"customers/{customer_id}.json")

    async def search_customers(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for customers."""
        return await self.get_customers(first=limit, query=query)

    # Collection Methods

    async def get_collections(self, first: int = 10, after: Optional[str] = None) -> Dict[str, Any]:
        """Get collections from Shopify."""
        graphql_query, variables = GraphQLQueryBuilder.get_collections_query(
            first=first,
            after=after
        )
        return await self._make_graphql_request(graphql_query, variables)

    async def get_collection_by_id(self, collection_id: str) -> Dict[str, Any]:
        """Get a specific collection by ID."""
        return await self._make_rest_request("GET", f"collections/{collection_id}.json")

    async def get_collection_products(self,
                                     collection_id: str,
                                     first: int = 10,
                                     after: Optional[str] = None,
                                     sort_key: Optional[str] = None,
                                     reverse: bool = False) -> Dict[str, Any]:
        """Get products in a specific collection."""
        query = f"collection_id:{collection_id}"
        return await self.get_products(
            first=first,
            after=after,
            query=query,
            sort_key=sort_key,
            reverse=reverse
        )

    # Shop Information

    async def get_shop_info(self) -> Dict[str, Any]:
        """Get general shop information."""
        return await self._make_rest_request("GET", "shop.json")

    # Webhook Methods

    async def verify_webhook(self, headers: Dict[str, str], body: str) -> bool:
        """Verify a webhook request from Shopify."""
        if not self.config.webhook_secret:
            logger.warning("No webhook secret configured")
            return False

        shopify_hmac = headers.get("X-Shopify-Hmac-Sha256")
        if not shopify_hmac:
            logger.warning("Missing Shopify HMAC header")
            return False

        import hmac
        import hashlib

        calculated_hmac = hmac.new(
            self.config.webhook_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(calculated_hmac, shopify_hmac)

    async def parse_webhook_event(self, headers: Dict[str, str], body: str) -> Optional[WebhookEvent]:
        """Parse a webhook event from Shopify."""
        if not await self.verify_webhook(headers, body):
            raise ShopifyError("Invalid webhook signature")

        try:
            data = json.loads(body)

            return WebhookEvent(
                id=headers.get("X-Shopify-Webhook-Id", ""),
                created_at=datetime.utcnow(),
                topic=headers.get("X-Shopify-Topic", ""),
                shop_domain=headers.get("X-Shopify-Shop-Domain", ""),
                api_version=headers.get("X-Shopify-Api-Version", ""),
                payload=data
            )
        except json.JSONDecodeError as e:
            raise ShopifyError(f"Invalid webhook JSON: {e}")

    # Health Check

    async def health_check(self) -> bool:
        """Check if the Shopify API is accessible."""
        try:
            await self.get_shop_info()
            return True
        except Exception as e:
            logger.error(f"Shopify health check failed: {e}")
            return False