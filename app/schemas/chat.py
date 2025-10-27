"""
Chat and conversation schemas.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MessageRequest(BaseModel):
    """Message request schema."""
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Message content")
    sender: str = Field(default="user", description="Message sender")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class MessageResponse(BaseModel):
    """Message response schema."""
    success: bool = Field(True, description="Whether the request was successful")
    response: str = Field(..., description="Assistant's response message")
    message: str = Field(..., description="Message content (alias for response)")
    conversation_id: str = Field(..., description="Conversation ID")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Response metadata")
    id: str = Field(..., description="Message ID")
    sender: str = Field("assistant", description="Message sender")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")

    class Config:
        from_attributes = True


class AlternativeMessageResponse(BaseModel):
    """Alternative message response schema for backward compatibility."""
    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="Message content")
    sender: str = Field(..., description="Message sender")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Message metadata")

    class Config:
        from_attributes = True


class ConversationBase(BaseModel):
    """Base conversation schema."""
    title: Optional[str] = Field(None, max_length=200, description="Conversation title")
    user_id: str = Field(..., description="User ID")
    status: str = Field(default="active", description="Conversation status")


class ConversationCreate(ConversationBase):
    """Conversation creation schema."""
    pass


class ConversationUpdate(BaseModel):
    """Conversation update schema."""
    title: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = None


class ConversationResponse(BaseModel):
    """Conversation response schema."""
    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    user_id: str = Field(..., description="User ID")
    status: str = Field(..., description="Conversation status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_message: Optional[str] = Field(None, description="Last message content")
    last_message_time: Optional[datetime] = Field(None, description="Last message timestamp")
    message_count: int = Field(default=0, description="Total message count")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Conversation metadata")

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    """Base message schema."""
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., min_length=1, max_length=2000, description="Message content")
    sender: str = Field(..., description="Message sender")
    sender_type: str = Field(default="user", description="Sender type: user, assistant, system")


class MessageHistory(BaseModel):
    """Message history item schema."""
    id: str = Field(..., description="Message ID")
    message: str = Field(..., description="Message content")
    sender: str = Field(..., description="Message sender")
    sender_type: str = Field(..., description="Sender type")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Message metadata")

    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    """Conversation history response schema."""
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[MessageHistory] = Field(..., description="List of messages")
    total_count: int = Field(..., description="Total number of messages")
    has_more: bool = Field(default=False, description="Whether there are more messages")
    next_offset: Optional[int] = Field(None, description="Next offset for pagination")


class ConversationListResponse(BaseModel):
    """Conversation list response schema."""
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total_count: int = Field(..., description="Total number of conversations")
    has_more: bool = Field(default=False, description="Whether there are more conversations")
    next_offset: Optional[int] = Field(None, description="Next offset for pagination")


class ChatSession(BaseModel):
    """Chat session schema."""
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    conversation_id: Optional[str] = Field(None, description="Current conversation ID")
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    is_active: bool = Field(default=True, description="Session active status")

    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    """WebSocket message schema."""
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")


class ChatAnalytics(BaseModel):
    """Chat analytics schema."""
    total_conversations: int = Field(..., description="Total conversations")
    total_messages: int = Field(..., description="Total messages")
    average_messages_per_conversation: float = Field(..., description="Average messages per conversation")
    active_conversations: int = Field(..., description="Active conversations")
    resolution_rate: float = Field(..., description="Conversation resolution rate")
    average_response_time: float = Field(..., description="Average response time in seconds")


class ConversationSummary(BaseModel):
    """Conversation summary schema."""
    conversation_id: str = Field(..., description="Conversation ID")
    summary: str = Field(..., description="Conversation summary")
    key_topics: List[str] = Field(..., description="Key topics discussed")
    sentiment: str = Field(..., description="Overall sentiment")
    resolution_status: str = Field(..., description="Resolution status")
    created_at: datetime = Field(..., description="Summary creation timestamp")

    class Config:
        from_attributes = True