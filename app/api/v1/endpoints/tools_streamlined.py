"""
Streamlined tool calling system endpoints.
Integrates the complete essential tool calling functionality.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import uuid
from loguru import logger

from app.db.session import get_db
from app.services.tool_system.llm_integration_streamlined import StreamlinedToolCallingService
from app.services.tool_system.tools_streamlined import streamlined_tool_registry
from app.services.tool_system.executor_streamlined import StreamlinedToolExecutor
from app.services.tool_dialogue_manager_streamlined import StreamlinedToolDialogueManager
from app.core.config import settings

router = APIRouter()


class ToolCallRequest(BaseModel):
    """Request for tool calling."""
    message: str = Field(..., description="User message to process")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ToolCallResponse(BaseModel):
    """Response from tool calling."""
    success: bool = Field(..., description="Whether the operation was successful")
    response: str = Field(..., description="AI response to the user")
    tool_calls_used: List[str] = Field(default_factory=list, description="List of tools that were used")
    tool_results: List[Dict[str, Any]] = Field(default_factory=list, description="Results from tool calls")
    reasoning: Optional[str] = Field(None, description="AI reasoning for tool selection")
    requires_clarification: bool = Field(False, description="Whether clarification is needed")
    suggested_follow_up: List[str] = Field(default_factory=list, description="Suggested follow-up questions")
    confidence: float = Field(0.8, description="Confidence score")
    processing_time: float = Field(0.0, description="Processing time in seconds")
    error: Optional[str] = Field(None, description="Error message if failed")


class ToolInfo(BaseModel):
    """Information about available tools."""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    category: str = Field(..., description="Tool category")
    parameters: List[Dict[str, Any]] = Field(..., description="Tool parameters")
    rate_limit: int = Field(..., description="Rate limit per minute")


class ToolsListResponse(BaseModel):
    """Response listing all available tools."""
    tools: List[ToolInfo] = Field(..., description="List of available tools")
    total_count: int = Field(..., description="Total number of tools")
    categories: List[str] = Field(..., description="Available tool categories")


@router.post("/chat", response_model=ToolCallResponse)
async def chat_with_tools(
    request: ToolCallRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with the AI assistant using the streamlined tool calling system.

    This endpoint integrates the complete tool calling functionality:
    - LLM-powered tool selection
    - Essential tool execution (7 tools only)
    - Context-aware response generation
    - Conversation management
    """
    try:
        import time
        start_time = time.time()

        # Initialize the streamlined tool calling service
        tool_service = StreamlinedToolCallingService()

        # Process the message with tool calling
        result = await tool_service.analyze_and_call_tools(
            request.message,
            request.context or {}
        )

        processing_time = time.time() - start_time

        return ToolCallResponse(
            success=True,
            response=result["response"],
            tool_calls_used=[call["tool_name"] for call in result["tool_calls"]],
            tool_results=[
                {
                    "tool": tool_result.tool_name,
                    "success": tool_result.success,
                    "data": tool_result.data,
                    "error": tool_result.error
                }
                for tool_result in result["tool_results"]
            ],
            reasoning=result.get("reasoning"),
            requires_clarification=result.get("requires_clarification", False),
            suggested_follow_up=result.get("suggested_follow_up", []),
            confidence=result.get("confidence", 0.8),
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"Error in streamlined tool calling: {e}")
        return ToolCallResponse(
            success=False,
            response="I'm sorry, I encountered an error while processing your request. Please try again.",
            tool_calls_used=[],
            tool_results=[],
            error=str(e),
            confidence=0.1
        )


@router.post("/conversation", response_model=ToolCallResponse)
async def conversation_with_tools(
    request: ToolCallRequest,
    db: Session = Depends(get_db)
):
    """
    Full conversation with context management using streamlined tool system.

    This endpoint provides complete dialogue management with:
    - Conversation context and history
    - Streamlined tool calling
    - Session management
    - Quality assessment
    """
    try:
        import time
        start_time = time.time()

        # Initialize the streamlined dialogue manager
        dialogue_manager = StreamlinedToolDialogueManager()

        # Get or create conversation context
        context = await dialogue_manager.get_or_create_context(
            request.conversation_id or str(uuid.uuid4()),
            None  # user_id would come from authentication
        )

        # Process message with full dialogue management
        response = await dialogue_manager.process_message(
            context,
            request.message
        )

        processing_time = time.time() - start_time

        return ToolCallResponse(
            success=True,
            response=response.message,
            tool_calls_used=response.tool_calls_used,
            tool_results=[
                {
                    "tool": tool_result.tool_name,
                    "success": tool_result.success,
                    "data": tool_result.data,
                    "error": tool_result.error
                }
                for tool_result in response.metadata.get("tool_results", [])
            ],
            reasoning=response.metadata.get("reasoning"),
            requires_clarification=response.requires_clarification,
            suggested_follow_up=response.suggested_follow_up,
            confidence=response.confidence,
            processing_time=processing_time
        )

    except Exception as e:
        logger.error(f"Error in streamlined conversation: {e}")
        return ToolCallResponse(
            success=False,
            response="I'm sorry, I encountered an error while processing your request. Please try again.",
            tool_calls_used=[],
            tool_results=[],
            error=str(e),
            confidence=0.1
        )


@router.get("/tools", response_model=ToolsListResponse)
async def list_available_tools():
    """
    List all available essential tools in the streamlined system.

    Returns information about the 7 essential tools that are available:
    - search_products: Search for products
    - get_product_details: Get detailed product information
    - get_order_status: Check order status
    - get_policy: Get policy information
    - get_store_info: Get store information
    - get_contact_info: Get contact details
    - get_faq: Get FAQ information
    """
    try:
        tools = streamlined_tool_registry.get_all_tools()
        tool_list = []
        categories = set()

        for tool_name, tool_def in tools.items():
            categories.add(tool_def.category)

            tool_info = ToolInfo(
                name=tool_name,
                description=tool_def.description,
                category=tool_def.category,
                parameters=[
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required,
                        "default": param.default
                    }
                    for param in tool_def.parameters
                ],
                rate_limit=tool_def.rate_limit_per_minute
            )
            tool_list.append(tool_info)

        return ToolsListResponse(
            tools=tool_list,
            total_count=len(tool_list),
            categories=list(categories)
        )

    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        raise HTTPException(status_code=500, detail="Failed to list tools")


@router.post("/execute/{tool_name}")
async def execute_single_tool(
    tool_name: str,
    parameters: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Execute a single tool directly with specified parameters.

    This endpoint allows direct tool execution for testing and debugging.
    """
    try:
        # Validate tool exists
        if tool_name not in streamlined_tool_registry.get_all_tools():
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        # Create tool call
        from app.services.tool_system.tools_streamlined import ToolCall
        tool_call = ToolCall(tool_name=tool_name, parameters=parameters)

        # Execute tool
        executor = StreamlinedToolExecutor()
        result = await executor.execute_tool(tool_call)

        return {
            "success": result.success,
            "tool_name": tool_name,
            "parameters": parameters,
            "data": result.data,
            "error": result.error,
            "metadata": result.metadata
        }

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return {
            "success": False,
            "tool_name": tool_name,
            "parameters": parameters,
            "error": str(e),
            "data": None
        }


@router.get("/status")
async def get_tool_system_status():
    """
    Get the status of the streamlined tool calling system.

    Returns system health information and configuration.
    """
    try:
        # Test tool registry
        tools = streamlined_tool_registry.get_all_tools()

        # Test LLM service
        llm_status = "unknown"
        try:
            from app.services.llm import LLMService
            llm_service = LLMService()
            llm_status = "available"
        except Exception as e:
            llm_status = f"error: {str(e)}"

        # Test Shopify integration
        shopify_status = "unknown"
        try:
            from app.integrations.shopify.service import ShopifyService
            from app.integrations.shopify.models import ShopifyConfig
            from app.core.config import settings

            config = ShopifyConfig(
                shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
                access_token=settings.SHOPIFY_ACCESS_TOKEN,
                api_version=settings.SHOPIFY_API_VERSION,
                webhook_secret=settings.SHOPIFY_WEBHOOK_SECRET,
                app_secret=settings.SHOPIFY_APP_SECRET
            )
            shopify_service = ShopifyService(config)
            shopify_status = "configured"
        except Exception as e:
            shopify_status = f"error: {str(e)}"

        return {
            "status": "operational",
            "system": "streamlined_tool_calling",
            "version": "1.0.0",
            "tools_loaded": len(tools),
            "tool_categories": list(set(tool.category for tool in tools.values())),
            "llm_service": {
                "status": llm_status,
                "model": settings.DEFAULT_LLM_MODEL
            },
            "shopify_integration": {
                "status": shopify_status,
                "store": settings.SHOPIFY_SHOP_DOMAIN
            },
            "features": [
                "LLM-powered tool selection",
                "Essential tools only (7 tools)",
                "Shopify integration",
                "Conversation management",
                "Rate limiting",
                "Error handling"
            ]
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")