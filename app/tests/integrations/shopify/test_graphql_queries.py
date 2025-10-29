"""Tests for Shopify GraphQL query builder."""

import pytest
from typing import Dict, Any

from app.integrations.shopify.graphql_queries import (
    GraphQLQueryBuilder,
    QueryType
)


class TestGraphQLQueryBuilder:
    """Test cases for GraphQLQueryBuilder class."""

    def test_init(self):
        """Test builder initialization."""
        builder = GraphQLQueryBuilder()
        assert builder._query_parts == []
        assert builder._variables == {}
        assert builder._variable_types == {}
        assert builder._current_query_type == QueryType.QUERY
        assert builder._query_name is None
        assert builder._field_stack == []

    def test_query_method(self):
        """Test starting a query."""
        builder = GraphQLQueryBuilder()
        builder.query("TestQuery")

        assert builder._current_query_type == QueryType.QUERY
        assert builder._query_name == "TestQuery"

    def test_mutation_method(self):
        """Test starting a mutation."""
        builder = GraphQLQueryBuilder()
        builder.mutation("TestMutation")

        assert builder._current_query_type == QueryType.MUTATION
        assert builder._query_name == "TestMutation"

    def test_field_without_alias(self):
        """Test adding a field without alias."""
        builder = GraphQLQueryBuilder()
        builder.field("testField")

        assert "testField" in builder._query_parts
        assert "testField" in builder._field_stack

    def test_field_with_alias(self):
        """Test adding a field with alias."""
        builder = GraphQLQueryBuilder()
        builder.field("testField", alias="tf")

        assert "tf: testField" in builder._query_parts
        assert "tf: testField" in builder._field_stack

    def test_field_with_inline_args(self):
        """Test adding a field with inline arguments."""
        builder = GraphQLQueryBuilder()
        builder.field("testField", first=10, isActive=True)

        expected = 'testField(first: 10, isActive: true)'
        assert expected in builder._query_parts

    def test_field_with_variable_args(self):
        """Test adding a field with variable arguments."""
        builder = GraphQLQueryBuilder()
        builder.variable("first", 10, "Int!")
        builder.field("testField", first=10)

        assert "first: $first" in builder._query_parts[0]

    def test_fields_multiple(self):
        """Test adding multiple fields."""
        builder = GraphQLQueryBuilder()
        builder.fields("field1", "field2", "field3")

        assert "field1" in builder._query_parts
        assert "field2" in builder._query_parts
        assert "field3" in builder._query_parts

    def test_nested_field(self):
        """Test starting a nested field block."""
        builder = GraphQLQueryBuilder()
        builder.nested("products", first=10)

        assert "products(first: 10)" in builder._query_parts
        assert "{" in builder._query_parts

    def test_end_nested(self):
        """Test ending a nested field block."""
        builder = GraphQLQueryBuilder()
        builder.nested("products")
        builder.end_nested()

        assert "products" in builder._query_parts
        assert "}" in builder._query_parts
        assert len(builder._field_stack) == 0

    def test_with_connection(self):
        """Test adding pagination connection."""
        builder = GraphQLQueryBuilder()
        builder.with_connection(first=10, after="cursor123")

        assert "edges" in builder._query_parts
        assert "cursor" in builder._query_parts
        assert "node" in builder._query_parts
        assert "pageInfo" in builder._query_parts
        assert "hasNextPage" in builder._query_parts
        assert "hasPreviousPage" in builder._query_parts
        assert "first" in builder._variables
        assert "after" in builder._variables

    def test_variable_creation_with_type(self):
        """Test creating variables with explicit type."""
        builder = GraphQLQueryBuilder()
        builder.variable("testVar", "value", "CustomType!")

        assert builder._variables["testVar"] == "value"
        assert builder._variable_types["testVar"] == "CustomType!"

    def test_variable_type_inference(self):
        """Test automatic type inference for variables."""
        builder = GraphQLQueryBuilder()

        # Test different types
        builder.variable("intVar", 42)
        builder.variable("strVar", "test")
        builder.variable("boolVar", True)
        builder.variable("listVar", ["a", "b"])
        builder.variable("floatVar", 3.14)

        assert builder._variable_types["intVar"] == "Int!"
        assert builder._variable_types["strVar"] == "String!"
        assert builder._variable_types["boolVar"] == "Boolean!"
        assert builder._variable_types["listVar"] == "[String]!"
        assert builder._variable_types["floatVar"] == "String!"

    def test_build_simple_query(self):
        """Test building a simple query."""
        builder = GraphQLQueryBuilder()
        builder.query("TestQuery")
        builder.field("testField")

        result = builder.build()

        assert "query TestQuery" in result
        assert "testField" in result
        assert result.endswith("}")

    def test_build_mutation_with_variables(self):
        """Test building a mutation with variables."""
        builder = GraphQLQueryBuilder()
        builder.mutation("CreateProduct")
        builder.variable("input", {"title": "Test"}, "ProductInput!")
        builder.field("productCreate", input="$input")

        result = builder.build()

        assert "mutation CreateProduct($input: ProductInput!)" in result
        assert "productCreate(input: $input)" in result

    def test_get_variables(self):
        """Test getting variables dictionary."""
        builder = GraphQLQueryBuilder()
        builder.variable("var1", "value1")
        builder.variable("var2", 42)

        variables = builder.get_variables()

        assert variables == {"var1": "value1", "var2": 42}
        # Ensure it's a copy
        variables["var3"] = "new"
        assert "var3" not in builder._variables

    def test_format_value_string(self):
        """Test formatting string values."""
        builder = GraphQLQueryBuilder()
        result = builder._format_value("test")
        assert result == '"test"'

    def test_format_value_boolean(self):
        """Test formatting boolean values."""
        builder = GraphQLQueryBuilder()
        assert builder._format_value(True) == "true"
        assert builder._format_value(False) == "false"

    def test_format_value_number(self):
        """Test formatting numeric values."""
        builder = GraphQLQueryBuilder()
        assert builder._format_value(42) == "42"
        assert builder._format_value(3.14) == "3.14"

    def test_format_value_list(self):
        """Test formatting list values."""
        builder = GraphQLQueryBuilder()
        result = builder._format_value([1, "test", True])
        assert result == '[1, "test", true]'

    def test_format_value_dict(self):
        """Test formatting dictionary values."""
        builder = GraphQLQueryBuilder()
        result = builder._format_value({"key": "value", "num": 42})
        assert 'key: "value"' in result
        assert "num: 42" in result

    def test_format_value_null(self):
        """Test formatting null values."""
        builder = GraphQLQueryBuilder()
        assert builder._format_value(None) == "null"

    def test_complex_nested_structure(self):
        """Test building complex nested structure."""
        builder = GraphQLQueryBuilder()
        builder.query("GetProducts")
        builder.variable("first", 10, "Int!")

        builder.nested("products", first="$first")
        builder.nested("edges")
        builder.nested("node")
        builder.fields("id", "title", "description")
        builder.nested("images", first=5)
        builder.fields("src", "altText")
        builder.end_nested()
        builder.end_nested()
        builder.end_nested()
        builder.end_nested()

        result = builder.build()

        assert "query GetProducts($first: Int!)" in result
        assert "products(first: $first)" in result
        assert "edges" in result
        assert "node" in result
        assert "images(first: 5)" in result
        assert result.count("{") == result.count("}")


class TestPredefinedQueries:
    """Test cases for predefined query methods."""

    def test_get_products_query_basic(self):
        """Test basic products query."""
        query, variables = GraphQLQueryBuilder.get_products_query()

        assert "query GetProducts" in query
        assert "products" in query
        assert "edges" in query
        assert "node" in query
        assert "pageInfo" in query
        assert variables["first"] == 10

    def test_get_products_query_with_params(self):
        """Test products query with parameters."""
        query, variables = GraphQLQueryBuilder.get_products_query(
            first=20,
            after="cursor123",
            query="tag:featured",
            sort_key="TITLE",
            reverse=True
        )

        assert variables["first"] == 20
        assert variables["after"] == "cursor123"
        assert variables["query"] == "tag:featured"
        assert variables["sortKey"] == "TITLE"
        assert variables["reverse"] is True
        assert "$first" in query
        assert "$after" in query
        assert "$query" in query
        assert "$sortKey" in query
        assert "$reverse" in query

    def test_get_shop_info_query(self):
        """Test shop info query."""
        query, variables = GraphQLQueryBuilder.get_shop_info_query()

        assert "query GetShopInfo" in query
        assert "shop" in query
        assert "name" in query
        assert "email" in query
        assert "currencyCode" in query
        assert "myshopifyDomain" in query
        assert variables == {}

    def test_get_product_by_id_query(self):
        """Test product by ID query."""
        product_id = "gid://shopify/Product/123"
        query, variables = GraphQLQueryBuilder.get_product_by_id_query(product_id)

        assert "query GetProductById" in query
        assert "product" in query
        assert variables["id"] == product_id
        assert "$id" in query
        assert "seo" in query
        assert "images" in query
        assert "variants" in query

    def test_get_orders_query_basic(self):
        """Test basic orders query."""
        query, variables = GraphQLQueryBuilder.get_orders_query()

        assert "query GetOrders" in query
        assert "orders" in query
        assert variables["first"] == 10
        assert "sortKey" in query  # Should have default sort key
        assert "reverse" in query  # Should have default reverse

    def test_get_orders_query_with_params(self):
        """Test orders query with parameters."""
        query, variables = GraphQLQueryBuilder.get_orders_query(
            first=5,
            after="cursor456",
            query="status:open",
            sort_key="TOTAL_PRICE",
            reverse=False
        )

        assert variables["first"] == 5
        assert variables["after"] == "cursor456"
        assert variables["query"] == "status:open"
        assert "TOTAL_PRICE" in query
        assert "false" in query.lower()  # reverse=false

    def test_get_inventory_levels_query(self):
        """Test inventory levels query."""
        item_ids = ["gid://shopify/InventoryItem/1", "gid://shopify/InventoryItem/2"]
        location_ids = ["gid://shopify/Location/1"]

        query, variables = GraphQLQueryBuilder.get_inventory_levels_query(
            inventory_item_ids=item_ids,
            location_ids=location_ids
        )

        assert "query GetInventoryLevels" in query
        assert variables["inventoryItemIds"] == item_ids
        assert variables["locationIds"] == location_ids
        assert "$inventoryItemIds" in query
        assert "$locationIds" in query

    def test_get_inventory_levels_query_no_locations(self):
        """Test inventory levels query without location IDs."""
        item_ids = ["gid://shopify/InventoryItem/1"]

        query, variables = GraphQLQueryBuilder.get_inventory_levels_query(
            inventory_item_ids=item_ids
        )

        assert variables["inventoryItemIds"] == item_ids
        assert "locationIds" not in variables

    def test_search_products_query(self):
        """Test product search query."""
        query, variables = GraphQLQueryBuilder.search_products_query(
            query="title:shirt",
            first=15,
            after="cursor789"
        )

        assert "query GetProducts" in query  # Uses same query name as get_products_query
        assert variables["query"] == "title:shirt"
        assert variables["first"] == 15
        assert variables["after"] == "cursor789"

    def test_get_collections_query(self):
        """Test collections query."""
        query, variables = GraphQLQueryBuilder.get_collections_query(first=25)

        assert "query GetCollections" in query
        assert "collections" in query
        assert variables["first"] == 25
        assert "image" in query
        assert "pageInfo" in query

    def test_get_collections_query_with_after(self):
        """Test collections query with pagination."""
        query, variables = GraphQLQueryBuilder.get_collections_query(
            first=5,
            after="cursor123"
        )

        assert variables["first"] == 5
        assert variables["after"] == "cursor123"
        assert "$after" in query

    def test_get_customers_query(self):
        """Test customers query."""
        query, variables = GraphQLQueryBuilder.get_customers_query(
            first=20,
            query="orders_count:>5"
        )

        assert "query GetCustomers" in query
        assert "customers" in query
        assert variables["first"] == 20
        assert variables["query"] == "orders_count:>5"
        assert "addresses" in query

    def test_get_shop_policies_query(self):
        """Test shop policies query."""
        query, variables = GraphQLQueryBuilder.get_shop_policies_query()

        assert "query GetShopPolicies" in query
        assert "shop" in query
        assert "privacyPolicy" in query
        assert "refundPolicy" in query
        assert "termsOfService" in query
        assert "shippingPolicy" in query
        assert variables == {}

    def test_get_specific_policy_query(self):
        """Test specific policy query."""
        query, variables = GraphQLQueryBuilder.get_specific_policy_query("privacy")

        assert "query GetPrivacyPolicy" in query
        assert "privacyPolicy" in query
        assert variables == {}

    def test_get_specific_policy_query_refund(self):
        """Test specific refund policy query."""
        query, variables = GraphQLQueryBuilder.get_specific_policy_query("refund")

        assert "query GetRefundPolicy" in query
        assert "refundPolicy" in query

    def test_get_specific_policy_query_invalid_type(self):
        """Test specific policy query with invalid type (should default to refund)."""
        query, variables = GraphQLQueryBuilder.get_specific_policy_query("invalid")

        assert "query GetRefundPolicy" in query
        assert "refundPolicy" in query


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query_build(self):
        """Test building an empty query."""
        builder = GraphQLQueryBuilder()
        builder.query("EmptyQuery")

        result = builder.build()
        assert "query EmptyQuery" in result
        assert result.endswith("}")

    def test_query_without_name(self):
        """Test building a query without name."""
        builder = GraphQLQueryBuilder()
        builder.query()
        builder.field("test")

        result = builder.build()
        assert result.startswith("query {")
        assert "test" in result

    def test_mutation_without_name(self):
        """Test building a mutation without name."""
        builder = GraphQLQueryBuilder()
        builder.mutation()
        builder.field("test")

        result = builder.build()
        assert result.startswith("mutation {")
        assert "test" in result

    def test_end_nested_without_start(self):
        """Test ending nested block without starting one."""
        builder = GraphQLQueryBuilder()
        builder.end_nested()  # Should not raise error

        # Should still be able to build
        result = builder.build()
        assert result is not None

    def test_multiple_end_nested(self):
        """Test calling end_nested multiple times."""
        builder = GraphQLQueryBuilder()
        builder.nested("test")
        builder.end_nested()
        builder.end_nested()  # Extra call should not cause issues

        result = builder.build()
        assert "test" in result

    def test_variable_override(self):
        """Test overriding existing variable."""
        builder = GraphQLQueryBuilder()
        builder.variable("test", "value1")
        builder.variable("test", "value2")  # Override

        assert builder._variables["test"] == "value2"

    def test_complex_variable_types(self):
        """Test complex variable type scenarios."""
        builder = GraphQLQueryBuilder()

        # Test with nested dict
        builder.variable("complex", {"nested": {"value": "test"}})
        assert builder._variable_types["complex"] == "String!"

        # Test with mixed type list
        builder.variable("mixed", [1, "test", True])
        assert builder._variable_types["mixed"] == "[String]!"  # Default for lists

    def test_field_with_none_value(self):
        """Test field with None value."""
        builder = GraphQLQueryBuilder()
        builder.field("test", value=None)

        result = builder.build()
        assert "value: null" in result

    def test_unicode_content(self):
        """Test handling Unicode content."""
        builder = GraphQLQueryBuilder()
        builder.variable("unicode", "测试中文")
        builder.field("test", value="café")

        result = builder.build()
        assert "测试中文" in result
        assert "café" in result

    def test_very_long_query(self):
        """Test building a very long query."""
        builder = GraphQLQueryBuilder()
        builder.query("LongQuery")

        # Add many fields
        for i in range(100):
            builder.field(f"field{i}")

        result = builder.build()
        assert len(result) > 1000
        assert "field0" in result
        assert "field99" in result

    def test_deeply_nested_structure(self):
        """Test deeply nested query structure."""
        builder = GraphQLQueryBuilder()
        builder.query("DeepQuery")

        # Create 10 levels of nesting
        for i in range(10):
            builder.nested(f"level{i}")

        builder.field("deepField")

        # Close all levels
        for i in range(10):
            builder.end_nested()

        result = builder.build()
        assert "deepField" in result
        assert result.count("{") == result.count("}")
        assert result.count("{") >= 10