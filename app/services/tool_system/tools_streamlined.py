"""
Streamlined tool definitions and schemas for the Shop Assistant AI tool call system.
Essential tools only - removed unnecessary and privacy-sensitive tools.
"""

from typing import Dict, List, Any, Optional, Union, Tuple
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class ToolType(str, Enum):
    """Tool type enumeration."""
    SEARCH = "search"
    RETRIEVAL = "retrieval"
    POLICY = "policy"
    SUPPORT = "support"


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = False
    default: Optional[Any] = None
    enum: Optional[List[str]] = None
    min_items: Optional[int] = None
    max_items: Optional[int] = None


class ToolCall(BaseModel):
    """Tool call request."""
    tool_name: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Tool execution result."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool_name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """Tool definition."""
    name: str
    description: str
    category: ToolType
    parameters: List[ToolParameter] = Field(default_factory=list)
    rate_limit_per_minute: int = 60
    requires_authentication: bool = False


class ToolRegistry:
    """Registry for managing tool definitions."""

    def __init__(self):
        self.tools = self._load_tool_definitions()

    def _load_tool_definitions(self) -> Dict[str, ToolDefinition]:
        """Load essential tool definitions only."""
        return {
            # Product Tools
            "search_products": ToolDefinition(
                name="search_products",
                description="Search for products in the Shopify store with advanced filtering",
                category=ToolType.SEARCH,
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search query for products (can include brand names, features, etc.)",
                        required=True
                    ),
                    ToolParameter(
                        name="limit",
                        type="integer",
                        description="Maximum number of results to return",
                        required=False,
                        default=10,
                        min_items=1,
                        max_items=50
                    ),
                    ToolParameter(
                        name="category",
                        type="string",
                        description="Filter by product category (electronics, clothing, home, etc.)",
                        required=False
                    ),
                    ToolParameter(
                        name="price_min",
                        type="integer",
                        description="Minimum price filter (integer without dollar sign)",
                        required=False
                    ),
                    ToolParameter(
                        name="price_max",
                        type="integer",
                        description="Maximum price filter (integer without dollar sign)",
                        required=False
                    ),
                    ToolParameter(
                        name="brand",
                        type="string",
                        description="Filter by brand name (Sony, Apple, Nike, etc.)",
                        required=False
                    ),
                    ToolParameter(
                        name="color",
                        type="string",
                        description="Filter by color",
                        required=False
                    ),
                    ToolParameter(
                        name="size",
                        type="string",
                        description="Filter by size",
                        required=False
                    )
                ],
                rate_limit_per_minute=120
            ),

            "get_product_details": ToolDefinition(
                name="get_product_details",
                description="Get detailed information about a specific product",
                category=ToolType.RETRIEVAL,
                parameters=[
                    ToolParameter(
                        name="product_id",
                        type="string",
                        description="Product ID or handle",
                        required=True
                    )
                ],
                rate_limit_per_minute=60
            ),

            # Order Tools
            "get_order_status": ToolDefinition(
                name="get_order_status",
                description="Get status and tracking information for an order",
                category=ToolType.RETRIEVAL,
                parameters=[
                    ToolParameter(
                        name="order_id",
                        type="string",
                        description="Order ID or order number",
                        required=True
                    ),
                    ToolParameter(
                        name="email",
                        type="string",
                        description="Customer email for verification",
                        required=False
                    )
                ],
                rate_limit_per_minute=30
            ),

            # Policy Tools
            "get_policy": ToolDefinition(
                name="get_policy",
                description="Get a specific policy (refund, shipping, privacy, terms)",
                category=ToolType.POLICY,
                parameters=[
                    ToolParameter(
                        name="policy_type",
                        type="string",
                        description="Type of policy to retrieve",
                        required=True,
                        enum=["refund", "return", "shipping", "privacy", "terms", "subscription", "legal"]
                    )
                ],
                rate_limit_per_minute=60
            ),

            # Store Tools
            "get_store_info": ToolDefinition(
                name="get_store_info",
                description="Get general store information",
                category=ToolType.RETRIEVAL,
                parameters=[],
                rate_limit_per_minute=60
            ),

            "get_contact_info": ToolDefinition(
                name="get_contact_info",
                description="Get store contact information and support hours",
                category=ToolType.RETRIEVAL,
                parameters=[],
                rate_limit_per_minute=30
            ),

            # Support Tools
            "get_faq": ToolDefinition(
                name="get_faq",
                description="Get frequently asked questions and answers",
                category=ToolType.SUPPORT,
                parameters=[
                    ToolParameter(
                        name="category",
                        type="string",
                        description="FAQ category",
                        required=False,
                        enum=["shipping", "returns", "payments", "products", "general"]
                    ),
                    ToolParameter(
                        name="query",
                        type="string",
                        description="Search within FAQs",
                        required=False
                    )
                ],
                rate_limit_per_minute=60
            )
        }

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self.tools.get(tool_name)

    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        """Get all tool definitions."""
        return self.tools

    def get_tools_by_category(self, category: ToolType) -> Dict[str, ToolDefinition]:
        """Get tools filtered by category."""
        return {
            name: tool for name, tool in self.tools.items()
            if tool.category == category
        }

    def validate_tool_call(self, tool_call: ToolCall) -> Tuple[bool, Optional[str]]:
        """Validate a tool call against its definition."""
        tool_def = self.get_tool(tool_call.tool_name)
        if not tool_def:
            return False, f"Tool '{tool_call.tool_name}' not found"

        # Check required parameters
        required_params = [p for p in tool_def.parameters if p.required]
        for param in required_params:
            if param.name not in tool_call.parameters:
                return False, f"Required parameter '{param.name}' missing"

        # Check parameter types and enums
        for param in tool_def.parameters:
            if param.name in tool_call.parameters:
                value = tool_call.parameters[param.name]

                # Check enum values
                if param.enum and value not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of: {param.enum}"

                # Check array limits
                if param.type == "array" and isinstance(value, list):
                    if param.min_items and len(value) < param.min_items:
                        return False, f"Parameter '{param.name}' must have at least {param.min_items} items"
                    if param.max_items and len(value) > param.max_items:
                        return False, f"Parameter '{param.name}' must have at most {param.max_items} items"

        return True, None


# Global streamlined tool registry instance
streamlined_tool_registry = ToolRegistry()