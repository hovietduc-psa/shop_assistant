"""
Tool system package for Shop Assistant AI.

This package provides a tool calling architecture that allows the AI assistant
to use specific tools to interact with the Shopify store and provide better customer support.
"""

from .tools_streamlined import streamlined_tool_registry, ToolDefinition, ToolCall, ToolResult, ToolType
from .executor_streamlined import StreamlinedToolExecutor
from .llm_integration_streamlined import StreamlinedToolCallingService

__all__ = [
    "streamlined_tool_registry",
    "ToolDefinition",
    "ToolCall",
    "ToolResult",
    "ToolType",
    "StreamlinedToolExecutor",
    "StreamlinedToolCallingService"
]