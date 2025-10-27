"""
LangGraph state management for Shop Assistant AI.
Defines the conversation state structure used throughout the workflow.
"""

from typing_extensions import TypedDict
from typing import List, Dict, Any, Optional
from datetime import datetime


class ConversationState(TypedDict):
    """
    Main conversation state structure for LangGraph workflow.

    This state flows through all nodes in the LangGraph workflow,
    maintaining context and intermediate results.
    """
    # Core message data
    user_message: str
    original_message: str

    # Entity extraction results
    entities: List[Dict[str, Any]]
    entity_extraction_method: str  # "llm", "regex", "fallback"

    # Tool decision results
    tool_decisions: List[Dict[str, Any]]
    tool_reasoning: str

    # Tool execution results
    tool_results: List[Dict[str, Any]]
    tool_execution_time: float

    # Final response
    response: str
    response_generation_method: str

    # Context and memory
    context_window: List[Dict[str, Any]]
    conversation_history: List[Dict[str, Any]]

    # Metadata and metrics
    confidence: float
    processing_time: float
    llm_calls_count: int

    # Quality and sentiment
    sentiment: Dict[str, Any]
    quality_score: float

    # Conversation management
    requires_clarification: bool
    suggested_follow_up: List[str]
    escalation_needed: bool
    escalation_reason: Optional[str]

    # Timestamps
    created_at: str
    updated_at: str

    # Error handling
    error: Optional[str]
    error_step: Optional[str]

    # Cache and optimization
    from_cache: bool
    cache_key: Optional[str]


class ToolCallState(TypedDict):
    """
    Structure for individual tool calls within the workflow.
    """
    tool_name: str
    parameters: Dict[str, Any]
    execution_order: int
    depends_on: List[str]  # Other tools this one depends on
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time: float


class AnalysisResult(TypedDict):
    """
    Structure for comprehensive analysis results (entity extraction + tool decisions).
    """
    entities: List[Dict[str, Any]]
    tool_calls: List[ToolCallState]
    reasoning: str
    confidence: float
    requires_clarification: bool
    suggested_follow_up: List[str]
    escalation_indicators: List[str]
    processing_method: str
    llm_response: Optional[Dict[str, Any]]


class PerformanceMetrics(TypedDict):
    """
    Performance tracking metrics for the workflow.
    """
    total_processing_time: float
    entity_extraction_time: float
    tool_decision_time: float
    tool_execution_time: float
    response_generation_time: float

    llm_calls_count: int
    llm_tokens_used: int

    tool_calls_count: int
    successful_tool_calls: int
    failed_tool_calls: int

    cache_hits: int
    cache_misses: int

    memory_usage_mb: float
    cpu_usage_percent: float


def create_initial_state(user_message: str) -> ConversationState:
    """
    Create initial conversation state for a new user message.

    Args:
        user_message: The raw user message

    Returns:
        Initial ConversationState with default values
    """
    now = datetime.now().isoformat()

    return {
        # Core message data
        "user_message": user_message,
        "original_message": user_message,

        # Entity extraction results (initialized empty)
        "entities": [],
        "entity_extraction_method": "pending",

        # Tool decision results (initialized empty)
        "tool_decisions": [],
        "tool_reasoning": "",

        # Tool execution results (initialized empty)
        "tool_results": [],
        "tool_execution_time": 0.0,

        # Final response (initialized empty)
        "response": "",
        "response_generation_method": "pending",

        # Context and memory
        "context_window": [],
        "conversation_history": [],

        # Metadata and metrics (initialized with defaults)
        "confidence": 0.0,
        "processing_time": 0.0,
        "llm_calls_count": 0,

        # Quality and sentiment (initialized empty)
        "sentiment": {},
        "quality_score": 0.0,

        # Conversation management (initialized with defaults)
        "requires_clarification": False,
        "suggested_follow_up": [],
        "escalation_needed": False,
        "escalation_reason": None,

        # Timestamps
        "created_at": now,
        "updated_at": now,

        # Error handling (initialized empty)
        "error": None,
        "error_step": None,

        # Cache and optimization
        "from_cache": False,
        "cache_key": None,
    }


def update_state_timestamp(state: ConversationState) -> ConversationState:
    """
    Update the updated_at timestamp for a state.

    Args:
        state: The conversation state to update

    Returns:
        Updated state with new timestamp
    """
    state["updated_at"] = datetime.now().isoformat()
    return state


def create_error_state(
    original_state: ConversationState,
    error: str,
    error_step: str
) -> ConversationState:
    """
    Create an error state based on an original state.

    Args:
        original_state: The state that failed
        error: The error message
        error_step: The step where the error occurred

    Returns:
        Error state with error information
    """
    return {
        **original_state,
        "error": error,
        "error_step": error_step,
        "confidence": 0.1,  # Low confidence on error
        "updated_at": datetime.now().isoformat(),
    }


def calculate_processing_metrics(state: ConversationState) -> PerformanceMetrics:
    """
    Calculate performance metrics from a completed conversation state.

    Args:
        state: The completed conversation state

    Returns:
        Performance metrics calculated from the state
    """
    return {
        "total_processing_time": state.get("processing_time", 0.0),
        "entity_extraction_time": state.get("entity_extraction_time", 0.0),
        "tool_decision_time": state.get("tool_decision_time", 0.0),
        "tool_execution_time": state.get("tool_execution_time", 0.0),
        "response_generation_time": state.get("response_generation_time", 0.0),

        "llm_calls_count": state.get("llm_calls_count", 0),
        "llm_tokens_used": state.get("llm_tokens_used", 0),

        "tool_calls_count": len(state.get("tool_results", [])),
        "successful_tool_calls": len([
            r for r in state.get("tool_results", [])
            if r.get("success", False)
        ]),
        "failed_tool_calls": len([
            r for r in state.get("tool_results", [])
            if not r.get("success", True)
        ]),

        "cache_hits": 1 if state.get("from_cache", False) else 0,
        "cache_misses": 0 if state.get("from_cache", False) else 1,

        "memory_usage_mb": 0.0,  # TODO: Implement memory tracking
        "cpu_usage_percent": 0.0,  # TODO: Implement CPU tracking
    }