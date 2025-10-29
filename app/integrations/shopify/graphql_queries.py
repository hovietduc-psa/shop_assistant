"""
GraphQL query builder for Shopify API.

Enhanced version with improved type system and additional query methods.
"""

from typing import List, Optional, Dict, Any, Union
from enum import Enum


class QueryType(Enum):
    """GraphQL query types."""
    QUERY = "query"
    MUTATION = "mutation"


class GraphQLQueryBuilder:
    """Builder for creating GraphQL queries for Shopify API."""

    def __init__(self):
        self._query_parts: List[str] = []
        self._variables: Dict[str, Any] = {}
        self._variable_types: Dict[str, str] = {}  # Track variable types separately
        self._current_query_type = QueryType.QUERY
        self._query_name: Optional[str] = None
        self._field_stack: List[str] = []

    def query(self, name: str = None) -> 'GraphQLQueryBuilder':
        """Start a new query."""
        self._current_query_type = QueryType.QUERY
        self._query_name = name
        return self

    def mutation(self, name: str = None) -> 'GraphQLQueryBuilder':
        """Start a new mutation."""
        self._current_query_type = QueryType.MUTATION
        self._query_name = name
        return self

    def field(self, name: str, alias: str = None, **kwargs) -> 'GraphQLQueryBuilder':
        """Add a field to the current query."""
        if alias:
            field_str = f"{alias}: {name}"
        else:
            field_str = name

        # Add arguments
        if kwargs:
            args = []
            for key, value in kwargs.items():
                if key in self._variables:
                    # Use variable reference
                    args.append(f"{key}: ${key}")
                else:
                    # Inline value
                    formatted_value = self._format_value(value)
                    args.append(f"{key}: {formatted_value}")
            field_str += f"({', '.join(args)})"

        self._query_parts.append(field_str)
        self._field_stack.append(field_str)
        return self

    def fields(self, *field_names: str) -> 'GraphQLQueryBuilder':
        """Add multiple fields to the current query."""
        for field_name in field_names:
            self.field(field_name)
        return self

    def nested(self, name: str, alias: str = None, **kwargs) -> 'GraphQLQueryBuilder':
        """Start a nested field block."""
        self.field(name, alias, **kwargs)
        self._query_parts.append("{")
        return self

    def end_nested(self) -> 'GraphQLQueryBuilder':
        """End a nested field block."""
        self._query_parts.append("}")
        if self._field_stack:
            self._field_stack.pop()
        return self

    def with_connection(self, first: int = 10, after: str = None) -> 'GraphQLQueryBuilder':
        """Add pagination connection."""
        # Only add variables if they don't already exist
        if first and "first" not in self._variables:
            self.variable("first", first, "Int!")
        if after and "after" not in self._variables:
            self.variable("after", after, "String")

        return self.nested("edges").fields(
            "cursor",
            "node"
        ).end_nested().field("pageInfo").fields(
            "hasNextPage",
            "hasPreviousPage"
        )

    def variable(self, name: str, value: Any, type_hint: str = None) -> 'GraphQLQueryBuilder':
        """Add a variable to the query."""
        self._variables[name] = value
        if type_hint:
            self._variable_types[name] = type_hint
        else:
            # Default type based on value
            if isinstance(value, int):
                self._variable_types[name] = "Int!"
            elif isinstance(value, str):
                self._variable_types[name] = "String!"
            elif isinstance(value, bool):
                self._variable_types[name] = "Boolean!"
            elif isinstance(value, list):
                self._variable_types[name] = "[String]!"
            else:
                self._variable_types[name] = "String!"
        return self

    def build(self) -> str:
        """Build the final GraphQL query string."""
        query_str = ""

        # Add query/mutation declaration
        if self._current_query_type == QueryType.QUERY:
            query_str += "query"
        else:
            query_str += "mutation"

        if self._query_name:
            query_str += f" {self._query_name}"

        # Add variable declarations with types
        if self._variables:
            var_declarations = []
            for name in self._variables.keys():
                var_type = self._variable_types.get(name, "String!")
                var_declarations.append(f"${name}: {var_type}")
            query_str += f"({', '.join(var_declarations)})"

        query_str += " {"

        # Add query parts
        query_str += "\n    ".join(self._query_parts)

        query_str += "\n}"

        return query_str

    def get_variables(self) -> Dict[str, Any]:
        """Get the variables dictionary for this query."""
        return self._variables.copy()

    def _format_value(self, value: Any) -> str:
        """Format a value for GraphQL query."""
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, list):
            formatted_items = [self._format_value(item) for item in value]
            return f"[{', '.join(formatted_items)}]"
        elif isinstance(value, dict):
            formatted_items = [f"{k}: {self._format_value(v)}" for k, v in value.items()]
            return f"{{{', '.join(formatted_items)}}}"
        elif value is None:
            return "null"
        else:
            return f'"{str(value)}"'

    @classmethod
    def get_products_query(cls,
                          first: int = 10,
                          after: Optional[str] = None,
                          query: Optional[str] = None,
                          sort_key: Optional[str] = None,
                          reverse: bool = False) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching products with proper Shopify GraphQL schema."""
        builder = cls()

        builder.query("GetProducts")
        builder.variable("first", first, "Int!")
        if after:
            builder.variable("after", after, "String")
        if query:
            builder.variable("query", query, "String")
        if sort_key:
            builder.variable("sortKey", sort_key, "ProductSortKeys")
            builder.variable("reverse", reverse, "Boolean")

        # Build products query parameters
        query_params = {
            "first": "$first"
        }
        if after:
            query_params["after"] = "$after"
        if query:
            query_params["query"] = "$query"
        if sort_key:
            query_params["sortKey"] = "$sortKey"
            query_params["reverse"] = "$reverse"

        # Use proper Shopify GraphQL structure with correct field selection
        builder.nested("products", **query_params)

        # Add proper connection structure with nested node fields including ALL necessary data
        node_fields = builder.nested("edges").fields("cursor").nested("node")
        node_fields.fields(
            "id", "title", "handle", "description", "descriptionHtml", "productType", "vendor",
            "status", "tags", "createdAt", "updatedAt", "publishedAt"
        )
        # Add images for LLM context
        node_fields.nested("images", first=5)
        node_fields.nested("edges")
        node_fields.nested("node")
        node_fields.fields("id", "src", "altText", "width", "height")
        node_fields.end_nested()  # node
        node_fields.end_nested()  # edges
        node_fields.end_nested()  # images
        # Add variants for pricing and inventory
        node_fields.nested("variants", first=10)
        node_fields.nested("edges")
        node_fields.nested("node")
        node_fields.fields("id", "title", "sku", "price", "compareAtPrice", "availableForSale",
                         "inventoryQuantity", "taxable")
        node_fields.end_nested()  # node
        node_fields.end_nested()  # edges
        node_fields.end_nested()  # variants
        # Add options for product variations
        node_fields.nested("options")
        node_fields.fields("id", "name", "values")
        node_fields.end_nested()  # options
        node_fields.end_nested()  # node
        node_fields.end_nested()  # edges

        # Add pageInfo with correct field names
        builder.nested("pageInfo").fields(
            "hasNextPage", "hasPreviousPage"
        ).end_nested()

        builder.end_nested()  # products

        return builder.build(), builder.get_variables()

    @classmethod
    def get_shop_info_query(cls) -> tuple[str, Dict[str, Any]]:
        """Get a query for shop information with basic verified fields."""
        builder = cls()
        builder.query("GetShopInfo")

        builder.nested("shop")
        builder.fields(
            "id", "name", "email", "currencyCode", "myshopifyDomain"
        )
        builder.end_nested()  # shop

        return builder.build(), builder.get_variables()

    @classmethod
    def get_product_by_id_query(cls, product_id: str) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching a specific product by ID."""
        builder = cls()

        builder.query("GetProductById")
        builder.variable("id", product_id, "ID!")

        builder.nested("product", id="$id")
        builder.fields(
            "id", "title", "handle", "description", "descriptionHtml",
            "productType", "vendor", "status", "tags", "createdAt",
            "updatedAt", "publishedAt"
        )

        # Add SEO fields
        builder.nested("seo")
        builder.fields("title", "description")
        builder.end_nested()

        # Add images with basic fields
        builder.nested("images", first=20)
        builder.nested("edges")
        builder.nested("node")
        builder.fields("id", "src", "altText", "width", "height")
        builder.end_nested()  # node
        builder.end_nested()  # edges
        builder.end_nested()  # images

        # Add variants with basic info including inventory
        builder.nested("variants", first=100)
        builder.nested("edges")
        builder.nested("node")
        builder.fields(
            "id", "title", "sku", "price", "compareAtPrice",
            "taxable", "availableForSale", "createdAt", "updatedAt",
            "inventoryQuantity"
        )
        builder.end_nested()  # node
        builder.end_nested()  # edges
        builder.end_nested()  # variants

        # Add options
        builder.nested("options")
        builder.fields("id", "name", "values")
        builder.end_nested()  # options

        builder.end_nested()  # product

        return builder.build(), builder.get_variables()

    @classmethod
    def get_orders_query(cls,
                        first: int = 10,
                        after: Optional[str] = None,
                        query: Optional[str] = None,
                        sort_key: str = "UPDATED_AT",
                        reverse: bool = True) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching orders."""
        builder = cls()

        builder.query("GetOrders")
        builder.variable("first", first)
        if after:
            builder.variable("after", after)
        if query:
            builder.variable("query", query)

        builder.nested("orders",
                      first="$first",
                      after="$after" if after else None,
                      query="$query" if query else None)

        # Add proper edges structure
        builder.nested("edges")
        builder.nested("node")
        builder.fields(
            "id", "name", "email", "phone", "displayFinancialStatus",
            "displayFulfillmentStatus", "currencyCode",
            "createdAt", "updatedAt", "processedAt", "cancelledAt"
        )

        # Add price sets with proper sub-fields
        builder.nested("totalPriceSet")
        builder.nested("shopMoney")
        builder.fields("amount", "currencyCode")
        builder.end_nested()
        builder.end_nested()

        builder.nested("subtotalPriceSet")
        builder.nested("shopMoney")
        builder.fields("amount", "currencyCode")
        builder.end_nested()
        builder.end_nested()

        builder.nested("totalTaxSet")
        builder.nested("shopMoney")
        builder.fields("amount", "currencyCode")
        builder.end_nested()
        builder.end_nested()

        builder.nested("totalShippingPriceSet")
        builder.nested("shopMoney")
        builder.fields("amount", "currencyCode")
        builder.end_nested()
        builder.end_nested()

        builder.nested("totalDiscountsSet")
        builder.nested("shopMoney")
        builder.fields("amount", "currencyCode")
        builder.end_nested()
        builder.end_nested()

        # Add customer info
        builder.nested("customer")
        builder.fields(
            "id", "email", "firstName", "lastName", "phone",
            "numberOfOrders", "state", "verifiedEmail", "taxExempt",
            "createdAt", "updatedAt"
        )
        builder.end_nested()  # customer

        # Add line items
        builder.nested("lineItems", first=50)
        builder.nested("edges")
        builder.nested("node")
        builder.fields(
            "id", "quantity", "title", "sku", "vendor", "taxable",
            "requiresShipping", "totalDiscount"
        )
        builder.nested("product")
        builder.fields("id", "title", "vendor")
        builder.end_nested()  # product
        builder.nested("variant")
        builder.fields("id", "title", "sku", "price")
        builder.end_nested()  # variant
        builder.end_nested()  # node
        builder.end_nested()  # edges
        builder.end_nested()  # lineItems

        builder.end_nested()  # node
        builder.end_nested()  # edges

        # Add pageInfo with correct fields
        builder.nested("pageInfo")
        builder.fields(
            "hasNextPage", "hasPreviousPage"
        )
        builder.end_nested()  # pageInfo

        builder.end_nested()  # orders

        return builder.build(), builder.get_variables()

    @classmethod
    def get_inventory_levels_query(cls,
                                  inventory_item_ids: List[str],
                                  location_ids: Optional[List[str]] = None) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching inventory levels."""
        builder = cls()

        builder.query("GetInventoryLevels")
        builder.variable("inventoryItemIds", inventory_item_ids)
        if location_ids:
            builder.variable("locationIds", location_ids)

        builder.nested("nodes", ids="$inventoryItemIds")
        builder.fields("id", "tracked")
        builder.nested("inventoryLevels",
                      first=50,
                      locationIds="$locationIds" if location_ids else None)
        builder.with_connection(first=50)
        builder.nested("node")
        builder.fields("id", "available", "locationId", "updatedAt")
        builder.end_nested()  # node
        builder.end_nested()  # inventoryLevels
        builder.end_nested()  # nodes

        return builder.build(), builder.get_variables()

    @classmethod
    def search_products_query(cls,
                             query: str,
                             first: int = 10,
                             after: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        """Get a query for searching products."""
        return cls.get_products_query(
            first=first,
            after=after,
            query=query,
            sort_key=None  # Remove default sort_key to avoid validation errors
        )

    @classmethod
    def get_collections_query(cls,
                             first: int = 10,
                             after: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching collections."""
        builder = cls()

        builder.query("GetCollections")
        builder.variable("first", first, "Int!")

        # Build collections query with proper connection structure
        query_params = {"first": "$first"}
        if after:
            builder.variable("after", after, "String")
            query_params["after"] = "$after"

        builder.nested("collections", **query_params)

        # Add edges with node structure
        builder.nested("edges")
        builder.nested("node")
        builder.fields(
            "id", "title", "handle", "description", "descriptionHtml",
            "updatedAt", "sortOrder"
        )

        # Add collection image
        builder.nested("image")
        builder.fields("id", "src", "altText", "width", "height")
        builder.end_nested()  # image

        builder.end_nested()  # node
        builder.end_nested()  # edges

        # Add pageInfo with correct fields
        builder.nested("pageInfo")
        builder.fields("hasNextPage", "hasPreviousPage")
        builder.end_nested()  # pageInfo

        builder.end_nested()  # collections

        return builder.build(), builder.get_variables()

    @classmethod
    def get_customers_query(cls,
                            first: int = 10,
                            after: Optional[str] = None,
                            query: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching customers."""
        builder = cls()

        builder.query("GetCustomers")
        builder.variable("first", first, "Int!")
        if after:
            builder.variable("after", after, "String")
        if query:
            builder.variable("query", query, "String")

        builder.nested("customers",
                      first="$first",
                      after="$after" if after else None,
                      query="$query" if query else None)

        builder.with_connection(first=first, after=after)

        builder.nested("node")
        builder.fields(
            "id", "email", "firstName", "lastName", "phone",
            "ordersCount", "state", "verifiedEmail", "taxExempt",
            "totalSpent", "createdAt", "updatedAt", "tags"
        )

        # Add addresses
        builder.nested("addresses", first=10)
        builder.with_connection(first=10)
        builder.nested("node")
        builder.fields(
            "id", "firstName", "lastName", "address1", "address2",
            "city", "province", "country", "zip", "countryCode",
            "provinceCode", "default"
        )
        builder.end_nested()  # node
        builder.end_nested()  # addresses

        builder.end_nested()  # node
        builder.end_nested()  # customers connection

        return builder.build(), builder.get_variables()

    @classmethod
    def get_shop_policies_query(cls) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching all shop policies."""
        builder = cls()
        builder.query("GetShopPolicies")

        builder.nested("shop")

        # Privacy Policy
        builder.nested("privacyPolicy")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # privacyPolicy

        # Refund Policy
        builder.nested("refundPolicy")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # refundPolicy

        # Terms of Service
        builder.nested("termsOfService")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # termsOfService

        # Shipping Policy
        builder.nested("shippingPolicy")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # shippingPolicy

        # Subscription Policy
        builder.nested("subscriptionPolicy")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # subscriptionPolicy

        # Legal Notice / Imprint
        builder.nested("legalNotice")
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # legalNotice

        builder.end_nested()  # shop

        return builder.build(), builder.get_variables()

    @classmethod
    def get_specific_policy_query(cls, policy_type: str) -> tuple[str, Dict[str, Any]]:
        """Get a query for fetching a specific policy type."""
        builder = cls()
        builder.query(f"Get{policy_type.title()}Policy")

        builder.nested("shop")

        # Map policy types to GraphQL fields
        policy_fields = {
            "privacy": "privacyPolicy",
            "refund": "refundPolicy",
            "terms": "termsOfService",
            "shipping": "shippingPolicy",
            "subscription": "subscriptionPolicy",
            "legal": "legalNotice"
        }

        field_name = policy_fields.get(policy_type.lower(), "refundPolicy")

        builder.nested(field_name)
        builder.fields("id", "title", "body", "url", "createdAt", "updatedAt")
        builder.end_nested()  # specific policy

        builder.end_nested()  # shop

        return builder.build(), builder.get_variables()