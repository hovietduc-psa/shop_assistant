"""
AI service schemas.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class IntentRequest(BaseModel):
    """Intent classification request schema."""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to classify")
    context: Optional[Dict[str, Any]] = Field(default={}, description="Additional context")
    language: Optional[str] = Field(default="en", description="Language code")


class IntentAlternative(BaseModel):
    """Alternative intent schema."""
    intent: str = Field(..., description="Intent name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class IntentResponse(BaseModel):
    """Intent classification response schema."""
    intent: str = Field(..., description="Primary intent")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    alternatives: List[IntentAlternative] = Field(default=[], description="Alternative intents")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class EntityRequest(BaseModel):
    """Entity extraction request schema."""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to analyze")
    entity_types: Optional[List[str]] = Field(None, description="Specific entity types to extract")
    language: Optional[str] = Field(default="en", description="Language code")


class Entity(BaseModel):
    """Extracted entity schema."""
    text: str = Field(..., description="Entity text")
    label: str = Field(..., description="Entity type/label")
    start: int = Field(..., ge=0, description="Start position in text")
    end: int = Field(..., ge=0, description="End position in text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class EntityResponse(BaseModel):
    """Entity extraction response schema."""
    entities: List[Entity] = Field(..., description="Extracted entities")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class SentimentRequest(BaseModel):
    """Sentiment analysis request schema."""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to analyze")
    language: Optional[str] = Field(default="en", description="Language code")
    detailed: bool = Field(default=False, description="Return detailed emotion analysis")


class SentimentResponse(BaseModel):
    """Sentiment analysis response schema."""
    sentiment: str = Field(..., description="Overall sentiment (positive/negative/neutral)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    emotions: Optional[Dict[str, float]] = Field(None, description="Detailed emotion scores")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class RecommendationRequest(BaseModel):
    """Product recommendation request schema."""
    user_id: Optional[str] = Field(None, description="User ID for personalization")
    query: Optional[str] = Field(None, description="Search query")
    categories: Optional[List[str]] = Field(None, description="Product categories")
    price_range: Optional[Dict[str, float]] = Field(None, description="Price range")
    preferences: Optional[Dict[str, Any]] = Field(default={}, description="User preferences")
    limit: int = Field(default=10, ge=1, le=50, description="Number of recommendations")


class Recommendation(BaseModel):
    """Product recommendation schema."""
    product_id: str = Field(..., description="Product ID")
    name: str = Field(..., description="Product name")
    score: float = Field(..., ge=0.0, le=1.0, description="Recommendation score")
    reason: str = Field(..., description="Reason for recommendation")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class RecommendationResponse(BaseModel):
    """Recommendation response schema."""
    recommendations: List[Recommendation] = Field(..., description="Product recommendations")
    total_count: int = Field(..., description="Total recommendations available")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class TextSummarizationRequest(BaseModel):
    """Text summarization request schema."""
    text: str = Field(..., min_length=50, max_length=10000, description="Text to summarize")
    max_length: Optional[int] = Field(default=150, ge=20, le=500, description="Maximum summary length")
    style: str = Field(default="concise", description="Summary style: concise, detailed, bullet_points")
    language: Optional[str] = Field(default="en", description="Language code")


class TextSummarizationResponse(BaseModel):
    """Text summarization response schema."""
    summary: str = Field(..., description="Text summary")
    original_length: int = Field(..., description="Original text length")
    summary_length: int = Field(..., description="Summary length")
    compression_ratio: float = Field(..., description="Compression ratio")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class QualityAssessmentRequest(BaseModel):
    """Conversation quality assessment request schema."""
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    criteria: Optional[List[str]] = Field(None, description="Assessment criteria")


class QualityAssessmentResponse(BaseModel):
    """Quality assessment response schema."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    criteria_scores: Dict[str, float] = Field(..., description="Scores by criteria")
    feedback: str = Field(..., description="Qualitative feedback")
    suggestions: List[str] = Field(default=[], description="Improvement suggestions")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class EscalationAnalysisRequest(BaseModel):
    """Escalation analysis request schema."""
    conversation_id: str = Field(..., description="Conversation ID")
    messages: List[Dict[str, Any]] = Field(..., description="Conversation messages")
    user_context: Optional[Dict[str, Any]] = Field(default={}, description="User context")


class EscalationAnalysisResponse(BaseModel):
    """Escalation analysis response schema."""
    should_escalate: bool = Field(..., description="Whether escalation is recommended")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in decision")
    reason: str = Field(..., description="Reason for escalation decision")
    priority: str = Field(..., description="Escalation priority: low, medium, high, urgent")
    suggested_agent: Optional[str] = Field(None, description="Suggested agent type")
    model: str = Field(..., description="AI model used")
    processing_time: float = Field(..., description="Processing time in seconds")


class AIModelConfig(BaseModel):
    """AI model configuration schema."""
    model_config = {"populate_by_name": True}

    model: str = Field(..., description="Model name", alias="model_name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature parameter")
    max_tokens: Optional[int] = Field(None, ge=1, description="Maximum tokens")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p parameter")
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0, description="Presence penalty")
    stop: Optional[List[str]] = Field(None, description="Stop sequences")


class LLMRequest(BaseModel):
    """General LLM request schema."""
    prompt: str = Field(..., min_length=1, description="Input prompt")
    config: Optional[AIModelConfig] = Field(None, description="Model configuration")
    context: Optional[Dict[str, Any]] = Field(default={}, description="Additional context")


class LLMResponse(BaseModel):
    """General LLM response schema."""
    response: str = Field(..., description="Model response")
    model: str = Field(..., description="Model used")
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage information")
    processing_time: float = Field(..., description="Processing time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")