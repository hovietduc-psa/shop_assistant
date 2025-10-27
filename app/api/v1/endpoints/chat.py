"""
Chat and conversation endpoints.
"""

from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from loguru import logger
import uuid
import os
import json
import asyncio
from app.db.session import get_db
from app.schemas.chat import (
    MessageRequest,
    MessageResponse,
    AlternativeMessageResponse,
    ConversationResponse,
    ConversationHistoryResponse
)
from app.core.config import settings

router = APIRouter()

# Feature flag for LangGraph (Phase 1 implementation)
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").lower() == "true"


@router.post("/message", response_model=MessageResponse)
async def send_message(
    message: MessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant.
    Uses LangGraph if enabled, otherwise falls back to the original system.
    """
    start_time = datetime.utcnow()

    try:
        if USE_LANGGRAPH:
            # Phase 1: Use LangGraph orchestrator
            return await _process_with_langgraph(message, db, start_time)
        else:
            # Original system (fallback)
            return await _process_with_original_system(message, db, start_time)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return MessageResponse(
            success=False,
            response="I'm sorry, I encountered an error while processing your request. Please try again.",
            message="I'm sorry, I encountered an error while processing your request. Please try again.",
            conversation_id=message.conversation_id or "error",
            id=str(uuid.uuid4()),
            sender="assistant",
            timestamp=datetime.utcnow(),
            metadata={"error": str(e), "processing_time": (datetime.utcnow() - start_time).total_seconds()}
        )


@router.post("/message/stream")
async def send_message_stream(
    message: MessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to the AI assistant with streaming response.
    Uses LangGraph with streaming for real-time response updates.
    """
    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            if USE_LANGGRAPH:
                # Send initial status
                yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing LangGraph workflow...'})}\n\n"

                # Initialize LangGraph orchestrator
                from app.services.langgraph_orchestrator import LangGraphOrchestratorFactory
                orchestrator = LangGraphOrchestratorFactory.create_orchestrator(
                    phase=2,
                    enable_intelligent_routing=True
                )

                conversation_id = message.conversation_id or str(uuid.uuid4())

                # Send processing status
                yield f"data: {json.dumps({'type': 'status', 'message': 'Processing message with intelligent routing...'})}\n\n"

                # Process with LangGraph and stream intermediate steps
                result = await orchestrator.process_message(
                    user_message=message.message,
                    conversation_context={"source": "streaming_api"},
                    conversation_id=conversation_id
                )

                # Send final response
                yield f"data: {json.dumps({'type': 'response', 'content': result.get('response', ''), 'metadata': result.get('metadata', {})})}\n\n"

                # Send completion status
                yield f"data: {json.dumps({'type': 'complete', 'conversation_id': conversation_id})}\n\n"

            else:
                # Fallback to streamlined system
                yield f"data: {json.dumps({'type': 'status', 'message': 'Using streamlined system...'})}\n\n"

                from app.services.tool_dialogue_manager_streamlined import StreamlinedToolDialogueManager
                dialogue_manager = StreamlinedToolDialogueManager()
                context = await dialogue_manager.get_or_create_context(
                    message.conversation_id or str(uuid.uuid4()),
                    None
                )

                response = await dialogue_manager.process_message(
                    context,
                    message.message
                )

                yield f"data: {json.dumps({'type': 'response', 'content': response.message})}\n\n"
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred during processing'})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/plain; charset=utf-8"
        }
    )


async def _process_with_langgraph(
    message: MessageRequest,
    db: Session,
    start_time: datetime
) -> MessageResponse:
    """
    Process message using LangGraph orchestrator (Phase 2 implementation).
    """
    from app.services.langgraph_orchestrator import LangGraphOrchestratorFactory
    from app.services.conversation_analytics import conversation_analytics_service

    logger.info("Processing message with LangGraph orchestrator (Phase 2)")

    # Initialize LangGraph orchestrator with Phase 2 parallel processing and intelligent routing
    orchestrator = LangGraphOrchestratorFactory.create_orchestrator(
        phase=2,
        enable_intelligent_routing=True
    )

    # Track conversation start
    conversation_id = message.conversation_id or str(uuid.uuid4())
    try:
        await conversation_analytics_service.track_conversation_start(
            conversation_id=conversation_id,
            user_id=None,
            session_id=None,
            metadata={"source": "chat_api", "method": "langgraph"}
        )
    except Exception as e:
        logger.error(f"Failed to track conversation start: {e}")

    # Track user message
    try:
        await conversation_analytics_service.track_message(
            conversation_id=conversation_id,
            message_content=message.message,
            message_type="user",
            db=db
        )
    except Exception as e:
        logger.error(f"Failed to track user message: {e}")

    # Process with LangGraph
    result = await orchestrator.process_message(
        user_message=message.message,
        conversation_context={"method": "langgraph"},
        conversation_id=conversation_id
    )

    # Track assistant response
    try:
        metadata = result.get("metadata", {})
        await conversation_analytics_service.track_message(
            conversation_id=conversation_id,
            message_content=result.get("response", ""),
            message_type="assistant",
            processing_time=metadata.get("processing_time", 0),
            tool_calls=[
                {
                    "tool_name": tool_name,
                    "success": True,
                    "error": None
                }
                for tool_name in metadata.get("tool_calls_used", [])
            ],
            quality_score=metadata.get("confidence", 0.5),
            metadata={
                "tool_calls_used": metadata.get("tool_calls_used", []),
                "requires_clarification": metadata.get("requires_clarification", False),
                "suggested_follow_up": metadata.get("suggested_follow_up", []),
                "confidence": metadata.get("confidence", 0.5),
                "should_escalate": metadata.get("escalation_needed", False),
                "escalation_reason": metadata.get("escalation_reason"),
                "entities_extracted": metadata.get("entities_extracted", []),
                "workflow_method": "langgraph_phase1"
            },
            db=db
        )
    except Exception as e:
        logger.error(f"Failed to track assistant response: {e}")

    # Build response
    processing_time = (datetime.utcnow() - start_time).total_seconds()
    final_metadata = {
        **result.get("metadata", {}),
        "conversation_id": conversation_id,
        "processing_time": processing_time,
        "method": "langgraph"
    }

    return MessageResponse(
        success=result.get("success", False),
        response=result.get("response", "I'm sorry, I couldn't process your request."),
        message=result.get("response", "I'm sorry, I couldn't process your request."),
        conversation_id=conversation_id,
        id=str(uuid.uuid4()),
        sender="assistant",
        timestamp=datetime.utcnow(),
        metadata=final_metadata
    )


async def _process_with_original_system(
    message: MessageRequest,
    db: Session,
    start_time: datetime
) -> MessageResponse:
    """
    Process message using the original system (fallback).
    """
    from app.services.tool_dialogue_manager_streamlined import StreamlinedToolDialogueManager
    from app.services.memory import ConversationMemoryManager
    from app.services.quality import ConversationQualityAssessor
    from app.services.conversation_analytics import conversation_analytics_service

    logger.info("Processing message with original system")

    dialogue_manager = StreamlinedToolDialogueManager()
    memory_manager = ConversationMemoryManager()
    quality_assessor = ConversationQualityAssessor()

    # Get or create dialogue context
    conversation_id = message.conversation_id or str(uuid.uuid4())
    context = await dialogue_manager.get_or_create_context(
        conversation_id,
        None  # user_id would come from authentication
    )

    # Check if session is expired
    is_new_conversation = False
    if dialogue_manager.is_session_expired(context):
        # Create new context for expired session
        conversation_id = str(uuid.uuid4())
        context = await dialogue_manager.get_or_create_context(
            conversation_id,
            None
        )
        is_new_conversation = True

        # Track conversation start if new
        if is_new_conversation:
            try:
                await conversation_analytics_service.track_conversation_start(
                    conversation_id=conversation_id,
                    user_id=None,  # Would come from authentication
                    session_id=None,  # Would come from request
                    metadata={"source": "chat_api", "method": "original"}
                )
            except Exception as e:
                logger.error(f"Failed to track conversation start: {e}")

    # Track user message (always run)
    try:
        await conversation_analytics_service.track_message(
            conversation_id=conversation_id,
            message_content=message.message,
            message_type="user",
            db=db
        )
    except Exception as e:
        logger.error(f"Failed to track user message: {e}")

    # Process message with tool calling system (always run)
    response = await dialogue_manager.process_message(
        context, message.message
    )

    # Save conversation to memory
    try:
        await memory_manager.save_conversation(context, db)
    except Exception as e:
        logger.error(f"Failed to save conversation to memory: {e}")

    # Assess response quality
    try:
        quality_score = await quality_assessor.assess_response(
            message.message, response.message, context
        )
    except Exception as e:
        logger.error(f"Failed to assess response quality: {e}")
        quality_score = 0.5

    # Calculate processing time
    processing_time = (datetime.utcnow() - start_time).total_seconds()

    # Track assistant response (only if response was successfully generated)
    try:
        if 'response' in locals() and response:
            tool_calls_data = []
            if response.metadata and response.metadata.get("tool_results"):
                tool_calls_data = [
                    {
                        "tool_name": result.tool_name,
                        "success": result.success,
                        "error": result.error
                    }
                    for result in response.metadata["tool_results"]
                ]

            await conversation_analytics_service.track_message(
                conversation_id=conversation_id,
                message_content=response.message,
                message_type="assistant",
                processing_time=processing_time,
                tool_calls=tool_calls_data,
                quality_score=quality_score,
                metadata={
                    "tool_calls_used": response.tool_calls_used,
                    "requires_clarification": response.requires_clarification,
                    "suggested_follow_up": response.suggested_follow_up,
                    "confidence": response.confidence,
                    "should_escalate": response.should_escalate,
                    "escalation_reason": response.escalation_reason,
                    "method": "original_system"
                },
                db=db
            )
    except Exception as e:
        logger.error(f"Failed to track assistant response: {e}")

    # Prepare response metadata (only if response was successfully generated)
    metadata = {
        "model": settings.DEFAULT_LLM_MODEL,
        "processing_time": processing_time,
        "conversation_id": conversation_id,
        "method": "original_system"
    }

    # Add response-specific metadata if available
    if 'response' in locals() and response:
        metadata.update({
            "tool_calls_used": response.tool_calls_used,
            "requires_clarification": response.requires_clarification,
            "suggested_follow_up": response.suggested_follow_up,
            "confidence": response.confidence,
            "should_escalate": response.should_escalate,
            "escalation_reason": response.escalation_reason,
        })

        # Add tool call metadata
        if response.metadata and response.metadata.get("tool_results"):
            metadata.update({
                "tool_results_count": len(response.metadata["tool_results"]),
                "successful_tools": len([
                    r for r in response.metadata["tool_results"]
                    if r.success
                ]),
                "failed_tools": len([
                    r for r in response.metadata["tool_results"]
                    if not r.success
                ])
            })

        return MessageResponse(
            success=True,
            response=response.message,
            message=response.message,
            conversation_id=conversation_id,
            id=str(uuid.uuid4()),
            sender="assistant",
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
    else:
        # Return error response if no response was generated
        return MessageResponse(
            success=False,
            response="I'm sorry, I couldn't generate a response. Please try again.",
            message="I'm sorry, I couldn't generate a response. Please try again.",
            conversation_id=conversation_id,
            id=str(uuid.uuid4()),
            sender="assistant",
            timestamp=datetime.utcnow(),
            metadata=metadata
        )


async def _generate_contextual_response(
    message: str,
    intent_result: Dict[str, Any],
    entities_result: Dict[str, Any],
    sentiment_result: Dict[str, Any],
    llm_service: Any
) -> str:
    """Generate a contextual response based on NLU analysis."""
    intent = intent_result.get("intent", "general_question")
    entities = entities_result.get("entities", [])
    sentiment = sentiment_result.get("sentiment", "neutral")

    # Build contextual prompt
    system_prompt = f"""You are a helpful AI assistant for an e-commerce platform.

The user's message has been analyzed:
- Intent: {intent}
- Sentiment: {sentiment}
- Entities: {entities}

Provide a helpful, contextually appropriate response. Be conversational and natural."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    try:
        response = await llm_service.generate_response(
            messages=messages,
            temperature=0.7,
            max_tokens=300
        )

        if "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"]
        else:
            return "I'm here to help! Could you please tell me more about what you need?"

    except Exception as e:
        logger.error(f"Response generation failed: {e}")
        return _get_fallback_response(intent, entities)


def _get_fallback_response(intent: str, entities: List[Dict[str, Any]]) -> str:
    """Get fallback response based on intent."""
    intent_responses = {
        "product_inquiry": "I'd be happy to help you find information about our products. Could you tell me more about what you're looking for?",
        "pricing_inquiry": "I can help you with pricing information. Let me find the details you need.",
        "order_status": "I can help you check your order status. Please provide your order number.",
        "support_request": "I'm here to help resolve any issues you're experiencing. What seems to be the problem?",
        "general_question": "I'd be happy to answer your question. What would you like to know?",
        "account_inquiry": "I can help you with your account. What specific issue are you experiencing?",
        "complaint": "I'm sorry to hear you're having issues. I want to help make this right. Could you provide more details?",
        "praise": "Thank you so much for your kind words! I'm glad I could help you today.",
        "greeting": "Hello! I'm here to help you with anything you need. How can I assist you today?"
    }

    return intent_responses.get(intent, "I'm here to help! How can I assist you today?")



@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str
):
    """
    WebSocket endpoint for real-time chat.
    """
    await websocket.accept()

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()

            # TODO: Process message with AI
            # For now, echo back with a prefix
            response = f"AI Assistant: You said '{data}'. This is a mock response."

            # Send response back to client
            await websocket.send_text(response)

    except WebSocketDisconnect:
        # Handle client disconnect
        pass
    except Exception as e:
        # Handle other exceptions
        await websocket.close(code=1011, reason=str(e))