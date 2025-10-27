"""
Streamlined dialogue manager using essential tool calling system only.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

from app.services.tool_system.llm_integration_streamlined import StreamlinedToolCallingService


@dataclass
class StreamlinedDialogueContext:
    """Streamlined dialogue context."""
    conversation_id: str
    user_id: Optional[str] = None
    message_count: int = 0
    session_start: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    context_window: List[Dict[str, Any]] = field(default_factory=list)
    customer_profile: Dict[str, Any] = field(default_factory=dict)
    conversation_goals: List[str] = field(default_factory=list)
    resolved_topics: List[str] = field(default_factory=list)
    sentiment_history: List[str] = field(default_factory=list)
    escalation_triggers: List[str] = field(default_factory=list)
    tool_calls_history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_entities: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class StreamlinedDialogueResponse:
    """Streamlined dialogue response to user."""
    message: str
    requires_clarification: bool = False
    suggested_follow_up: List[str] = field(default_factory=list)
    tool_calls_used: List[str] = field(default_factory=list)
    confidence: float = 0.8
    should_escalate: bool = False
    escalation_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class StreamlinedToolDialogueManager:
    """Streamlined dialogue manager using essential tool calling system."""

    def __init__(self):
        self.tool_calling_service = StreamlinedToolCallingService()

        # Session timeout (30 minutes)
        self.session_timeout = timedelta(minutes=30)

    async def get_or_create_context(
        self,
        conversation_id: str,
        user_id: Optional[str] = None
    ) -> StreamlinedDialogueContext:
        """Get existing context or create new one."""
        # This would normally load from database
        context = StreamlinedDialogueContext(
            conversation_id=conversation_id,
            user_id=user_id
        )

        return context

    async def process_message(
        self,
        context: StreamlinedDialogueContext,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> StreamlinedDialogueResponse:
        """Process a user message and generate response."""
        try:
            logger.info(f"Processing message with streamlined tools: {user_message[:100]}...")

            # Update context
            context.last_activity = datetime.now()
            context.message_count += 1
            context.context_window.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat(),
                "message_number": context.message_count
            })

            # Use essential tool calling service to analyze and execute tools
            tool_result = await self.tool_calling_service.analyze_and_call_tools(
                user_message,
                conversation_context
            )

            # Store tool calls in context
            if tool_result["tool_calls"]:
                context.tool_calls_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "tool_calls": tool_result["tool_calls"],
                    "results": tool_result["tool_results"],
                    "reasoning": tool_result["reasoning"]
                })

            # Update extracted entities in context
            if "extracted_entities" in tool_result and tool_result["extracted_entities"]:
                context.extracted_entities.extend(tool_result["extracted_entities"])
                logger.info(f"Updated context with {len(tool_result['extracted_entities'])} extracted entities")

            # Simple escalation analysis
            escalation_analysis = await self._analyze_escalation_need_simple(
                context,
                user_message,
                tool_result
            )

            # Create response
            response = StreamlinedDialogueResponse(
                message=tool_result["response"],
                requires_clarification=tool_result.get("requires_clarification", False),
                suggested_follow_up=tool_result.get("suggested_follow_up", []),
                tool_calls_used=[call["tool_name"] for call in tool_result["tool_calls"]],
                confidence=0.8,
                should_escalate=escalation_analysis["should_escalate"],
                escalation_reason=escalation_analysis.get("reason"),
                metadata={
                    "tool_results": tool_result["tool_results"],
                    "reasoning": tool_result["reasoning"]
                }
            )

            # Add assistant message to context
            context.context_window.append({
                "role": "assistant",
                "content": response.message,
                "timestamp": datetime.now().isoformat(),
                "message_number": context.message_count,
                "tool_calls": tool_result["tool_calls"],
                "metadata": response.metadata
            })

            return response

        except Exception as e:
            logger.error(f"Error processing message with streamlined tools: {e}")
            return StreamlinedDialogueResponse(
                message="I'm sorry, I encountered an error while processing your request. Please try again or contact our support team for assistance.",
                confidence=0.1,
                metadata={"error": str(e)}
            )

    async def _analyze_escalation_need_simple(
        self,
        context: StreamlinedDialogueContext,
        user_message: str,
        tool_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simple escalation analysis without complex dependencies."""
        try:
            # Check for escalation triggers
            escalation_triggers = [
                "human", "agent", "person", "talk to someone", "escalate",
                "useless", "stupid", "ridiculous", "frustrated", "angry",
                "manager", "supervisor", "complaint", "unhappy"
            ]

            message_lower = user_message.lower()
            trigger_count = sum(1 for trigger in escalation_triggers if trigger in message_lower)

            # Check if tools failed
            failed_tools = [
                result for result in tool_result.get("tool_results", [])
                if not result.success
            ]

            should_escalate = (
                trigger_count >= 1 or
                len(failed_tools) > 0 or
                context.message_count > 20  # Escalate after 20 messages
            )

            reason = None
            if should_escalate:
                if trigger_count >= 1:
                    reason = f"Customer used escalation triggers"
                elif failed_tools:
                    reason = f"Essential tools failed: {[r.tool_name for r in failed_tools]}"
                elif context.message_count > 20:
                    reason = "Long conversation requiring human assistance"

            return {
                "should_escalate": should_escalate,
                "reason": reason,
                "trigger_count": trigger_count,
                "failed_tools": len(failed_tools)
            }

        except Exception as e:
            logger.error(f"Error analyzing escalation need: {e}")
            return {
                "should_escalate": False,
                "error": str(e)
            }

    def is_session_expired(self, context: StreamlinedDialogueContext) -> bool:
        """Check if the session has expired."""
        return datetime.now() - context.last_activity > self.session_timeout

    async def get_conversation_summary(self, context: StreamlinedDialogueContext) -> Dict[str, Any]:
        """Get a summary of the conversation."""
        return {
            "conversation_id": context.conversation_id,
            "message_count": context.message_count,
            "duration_minutes": (context.last_activity - context.session_start).total_seconds() / 60,
            "tool_calls_count": len(context.tool_calls_history),
            "tools_used": list(set([
                call["tool_name"]
                for history in context.tool_calls_history
                for call in history["tool_calls"]
            ])),
            "resolved_topics": context.resolved_topics,
            "escalation_triggers": context.escalation_triggers,
            "last_activity": context.last_activity.isoformat(),
            "session_start": context.session_start.isoformat()
        }