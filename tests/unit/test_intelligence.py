"""
Unit tests for AI Intelligence components.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from app.core.intelligence import (
    EscalationEngine, EscalationRequest, EscalationLevel,
    QualityAssessor, QualityAssessmentRequest, QualityScore,
    SentimentAnalyzer, SentimentScore, FrustrationDetector, FrustrationLevel,
    CoachingEngine, CoachingRequest, PerformanceFeedback
)


@pytest.mark.unit
class TestEscalationEngine:
    """Test suite for Escalation Engine."""

    @pytest.fixture
    def escalation_engine(self, mock_llm_manager, mock_prompt_manager):
        """Create escalation engine for testing."""
        return EscalationEngine(mock_llm_manager, mock_prompt_manager)

    @pytest.fixture
    def sample_escalation_request(self, test_conversation):
        """Create sample escalation request."""
        return EscalationRequest(
            conversation_id=test_conversation["id"],
            messages=test_conversation["messages"],
            customer_id=test_conversation["customer_id"],
            context=test_conversation["metadata"]
        )

    async def test_escalation_analysis_no_escalation_needed(
        self,
        escalation_engine,
        sample_escalation_request,
        mock_llm_manager
    ):
        """Test escalation analysis when no escalation is needed."""
        # Mock LLM response for no escalation
        mock_llm_manager.generate_response.return_value = json.dumps({
            "should_escalate": False,
            "confidence": 0.9,
            "reasoning": "Customer inquiry is routine and can be handled by AI",
            "urgency_score": 2.0,
            "triggers": []
        })

        result = await escalation_engine.analyze_escalation(sample_escalation_request)

        assert result is not None
        assert result.decision.should_escalate is False
        assert result.decision.confidence >= 0.8
        assert result.decision.urgency_score < 5.0

    async def test_escalation_analysis_customer_frustration(
        self,
        escalation_engine,
        sample_escalation_request,
        mock_llm_manager
    ):
        """Test escalation analysis due to customer frustration."""
        # Mock LLM response for escalation due to frustration
        mock_llm_manager.generate_response.return_value = json.dumps({
            "should_escalate": True,
            "confidence": 0.85,
            "reasoning": "Customer shows clear signs of frustration with repeated issues",
            "urgency_score": 8.5,
            "triggers": [
                {
                    "type": "customer_frustration",
                    "reason": "frustration",
                    "description": "Customer expressed frustration multiple times",
                    "evidence": ["I'm getting tired of this", "This is ridiculous"]
                }
            ],
            "suggested_actions": ["Immediate supervisor intervention", "Offer compensation"]
        })

        result = await escalation_engine.analyze_escalation(sample_escalation_request)

        assert result.decision.should_escalate is True
        assert result.decision.urgency_score >= 8.0
        assert len(result.decision.triggers) > 0
        assert "customer_frustration" in [t.type for t in result.decision.triggers]

    async def test_escalation_analysis_technical_limitation(
        self,
        escalation_engine,
        sample_escalation_request,
        mock_llm_manager
    ):
        """Test escalation analysis due to technical limitations."""
        mock_llm_manager.generate_response.return_value = json.dumps({
            "should_escalate": True,
            "confidence": 0.9,
            "reasoning": "AI lacks capability to handle complex technical integration",
            "urgency_score": 7.0,
            "triggers": [
                {
                    "type": "technical_limitation",
                    "reason": "technical_limitation",
                    "description": "Complex API integration request beyond AI capabilities",
                    "evidence": ["Need custom API integration", "Requires database schema changes"]
                }
            ],
            "recommended_agent_type": "technical_support"
        })

        result = await escalation_engine.analyze_escalation(sample_escalation_request)

        assert result.decision.should_escalate is True
        assert result.decision.recommended_agent_type == "technical_support"

    async def test_escalation_with_high_confidence(
        self,
        escalation_engine,
        sample_escalation_request,
        mock_llm_manager
    ):
        """Test escalation decision with high confidence."""
        mock_llm_manager.generate_response.return_value = json.dumps({
            "should_escalate": True,
            "confidence": 0.95,
            "reasoning": "Clear policy violation requiring human intervention",
            "urgency_score": 9.5,
            "triggers": [
                {
                    "type": "policy_violation",
                    "reason": "policy_violation",
                    "description": "Customer requesting actions that violate company policy",
                    "evidence": ["Request for unauthorized discount", "Attempt to exploit system"]
                }
            ],
            "priority": "critical"
        })

        result = await escalation_engine.analyze_escalation(sample_escalation_request)

        assert result.decision.confidence >= 0.9
        assert result.decision.priority == EscalationLevel.CRITICAL

    async def test_escalation_parsing_error_handling(
        self,
        escalation_engine,
        sample_escalation_request,
        mock_llm_manager
    ):
        """Test handling of LLM response parsing errors."""
        # Mock invalid JSON response
        mock_llm_manager.generate_response.return_value = "Invalid JSON response"

        result = await escalation_engine.analyze_escalation(sample_escalation_request)

        # Should handle parsing error gracefully
        assert result is not None
        assert result.decision.should_escalate is False  # Default to no escalation on error


@pytest.mark.unit
class TestQualityAssessor:
    """Test suite for Quality Assessor."""

    @pytest.fixture
    def quality_assessor(self, mock_llm_manager, mock_prompt_manager):
        """Create quality assessor for testing."""
        return QualityAssessor(mock_llm_manager, mock_prompt_manager)

    @pytest.fixture
    def sample_quality_request(self, test_conversation):
        """Create sample quality assessment request."""
        return QualityAssessmentRequest(
            conversation_id=test_conversation["id"],
            messages=test_conversation["messages"],
            agent_id=test_conversation["agent_id"],
            customer_id=test_conversation["customer_id"]
        )

    async def test_quality_assessment_excellent_score(
        self,
        quality_assessor,
        sample_quality_request,
        mock_llm_manager
    ):
        """Test quality assessment resulting in excellent score."""
        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 9.2,
            "confidence": 0.88,
            "strengths": [
                "Excellent empathy and active listening",
                "Clear and concise communication",
                "Effective problem resolution",
                "Professional tone throughout"
            ],
            "weaknesses": [
                "Could improve response time slightly"
            ],
            "metrics": [
                {
                    "category": "communication",
                    "score": 9.5,
                    "confidence": 0.9,
                    "evidence": ["Clear explanations", "Empathetic responses"]
                },
                {
                    "category": "problem_solving",
                    "score": 9.0,
                    "confidence": 0.85,
                    "evidence": ["Quick issue identification", "Effective solution"]
                }
            ],
            "summary": "Excellent overall performance with minor areas for improvement",
            "actionable_insights": ["Focus on reducing response time by 10%"]
        })

        result = await quality_assessor.assess_conversation_quality(sample_quality_request)

        assert result.numeric_score >= 9.0
        assert result.overall_score == QualityScore.EXCELLENT
        assert len(result.strengths) > len(result.weaknesses)
        assert result.confidence >= 0.8

    async def test_quality_assessment_poor_score(
        self,
        quality_assessor,
        sample_quality_request,
        mock_llm_manager
    ):
        """Test quality assessment resulting in poor score."""
        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 2.8,
            "confidence": 0.92,
            "strengths": [],
            "weaknesses": [
                "Lack of empathy in responses",
                "Poor problem identification",
                "Inadequate product knowledge",
                "Unprofessional tone",
                "Excessive response time"
            ],
            "metrics": [
                {
                    "category": "communication",
                    "score": 2.5,
                    "confidence": 0.9,
                    "evidence": ["Abrupt responses", "Lack of empathy"]
                },
                {
                    "category": "product_knowledge",
                    "score": 2.0,
                    "confidence": 0.95,
                    "evidence": ["Incorrect product information", "Unable to answer questions"]
                }
            ],
            "summary": "Significant improvement needed across all quality dimensions",
            "actionable_insights": [
                "Immediate coaching required",
                "Product knowledge refresher training",
                "Communication skills workshop"
            ]
        })

        result = await quality_assessor.assess_conversation_quality(sample_quality_request)

        assert result.numeric_score <= 3.0
        assert result.overall_score == QualityScore.POOR
        assert len(result.weaknesses) > len(result.strengths)

    async def test_quality_assessment_with_context(
        self,
        quality_assessor,
        sample_quality_request,
        mock_llm_manager
    ):
        """Test quality assessment with additional context."""
        # Add context to the request
        sample_quality_request.context = {
            "customer_tier": "premium",
            "previous_interactions": 3,
            "issue_complexity": "high",
            "language": "en"
        }

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 7.8,
            "confidence": 0.85,
            "strengths": ["Handled complex issue well", "Good premium customer service"],
            "weaknesses": ["Response time could be improved for premium tier"],
            "metrics": [],
            "summary": "Good performance with room for premium service improvements",
            "actionable_insights": ["Focus on premium service standards"]
        })

        result = await quality_assessor.assess_conversation_quality(sample_quality_request)

        assert result is not None
        # Verify context was considered in assessment
        assert "premium" in result.summary

    async def test_quality_assessment_empty_conversation(
        self,
        quality_assessor,
        mock_llm_manager
    ):
        """Test quality assessment with minimal conversation data."""
        minimal_request = QualityAssessmentRequest(
            conversation_id="minimal_conv",
            messages=[{"role": "customer", "content": "Hi"}],
            agent_id="agent_001"
        )

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 5.0,
            "confidence": 0.5,
            "strengths": [],
            "weaknesses": ["Insufficient conversation data for assessment"],
            "metrics": [],
            "summary": "Limited data available for quality assessment",
            "actionable_insights": ["Need more conversation data"]
        })

        result = await quality_assessor.assess_conversation_quality(minimal_request)

        assert result is not None
        assert result.confidence <= 0.6  # Low confidence due to limited data


@pytest.mark.unit
class TestSentimentAnalyzer:
    """Test suite for Sentiment Analyzer."""

    @pytest.fixture
    def sentiment_analyzer(self, mock_llm_manager, mock_prompt_manager):
        """Create sentiment analyzer for testing."""
        return SentimentAnalyzer(mock_llm_manager, mock_prompt_manager)

    async def test_positive_sentiment_analysis(
        self,
        sentiment_analyzer,
        mock_llm_manager
    ):
        """Test analysis of positive sentiment messages."""
        positive_messages = [
            {"role": "customer", "content": "This is amazing! Thank you so much!"},
            {"role": "customer", "content": "Excellent service, very happy with the help!"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_sentiment": "very_positive",
            "sentiment_score": 0.85,
            "confidence": 0.9,
            "key_phrases": ["amazing", "thank you", "excellent service", "very happy"],
            "emotional_indicators": ["gratitude", "satisfaction", "excitement"]
        })

        result = await sentiment_analyzer.analyze_sentiment(positive_messages)

        assert result.overall_sentiment == SentimentScore.VERY_POSITIVE
        assert result.sentiment_score >= 0.7
        assert result.confidence >= 0.8
        assert len(result.key_phrases) > 0
        assert len(result.emotional_indicators) > 0

    async def test_negative_sentiment_analysis(
        self,
        sentiment_analyzer,
        mock_llm_manager
    ):
        """Test analysis of negative sentiment messages."""
        negative_messages = [
            {"role": "customer", "content": "This is terrible! I'm very frustrated with this service."},
            {"role": "customer", "content": "Worst experience ever, nobody is helping me!"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_sentiment": "very_negative",
            "sentiment_score": -0.9,
            "confidence": 0.95,
            "key_phrases": ["terrible", "frustrated", "worst experience", "nobody helping"],
            "emotional_indicators": ["anger", "frustration", "disappointment"]
        })

        result = await sentiment_analyzer.analyze_sentiment(negative_messages)

        assert result.overall_sentiment == SentimentScore.VERY_NEGATIVE
        assert result.sentiment_score <= -0.7
        assert result.confidence >= 0.9

    async def test_neutral_sentiment_analysis(
        self,
        sentiment_analyzer,
        mock_llm_manager
    ):
        """Test analysis of neutral sentiment messages."""
        neutral_messages = [
            {"role": "customer", "content": "I need to check my order status."},
            {"role": "customer", "content": "What are your business hours?"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_sentiment": "neutral",
            "sentiment_score": 0.1,
            "confidence": 0.8,
            "key_phrases": ["order status", "business hours"],
            "emotional_indicators": ["information_seeking"]
        })

        result = await sentiment_analyzer.analyze_sentiment(neutral_messages)

        assert result.overall_sentiment == SentimentScore.NEUTRAL
        assert -0.3 <= result.sentiment_score <= 0.3

    async def test_sentiment_trend_analysis(
        self,
        sentiment_analyzer,
        mock_llm_manager
    ):
        """Test sentiment analysis across conversation timeline."""
        conversation_messages = [
            {"role": "customer", "content": "I'm having an issue with my order."},  # Neutral
            {"role": "agent", "content": "I'd be happy to help you with that."},
            {"role": "customer", "content": "Well, this is taking too long and I'm getting frustrated!"},  # Negative
            {"role": "agent", "content": "I understand your frustration and I'm working to resolve this quickly."},
            {"role": "customer", "content": "Thank you! That's much better, I appreciate the help."}  # Positive
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_sentiment": "positive",
            "sentiment_score": 0.3,
            "confidence": 0.85,
            "key_phrases": ["frustrated", "thank you", "appreciate the help"],
            "emotional_indicators": ["frustration", "gratitude", "relief"],
            "sentiment_trend": "improving"
        })

        result = await sentiment_analyzer.analyze_sentiment(conversation_messages)

        assert result.overall_sentiment == SentimentScore.POSITIVE
        # Should capture the trend from negative to positive


@pytest.mark.unit
class TestFrustrationDetector:
    """Test suite for Frustration Detector."""

    @pytest.fixture
    def frustration_detector(self, mock_llm_manager, mock_prompt_manager):
        """Create frustration detector for testing."""
        return FrustrationDetector(mock_llm_manager, mock_prompt_manager)

    async def test_no_frustration_detection(
        self,
        frustration_detector,
        mock_llm_manager
    ):
        """Test when no frustration is detected."""
        calm_messages = [
            {"role": "customer", "content": "Hi, I have a question about your products."},
            {"role": "customer", "content": "Thank you for the information!"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "frustration_level": "none",
            "confidence": 0.92,
            "indicators": [],
            "escalation_risk": 0.1,
            "recommended_actions": []
        })

        result = await frustration_detector.detect_frustration(calm_messages)

        assert result.frustration_level == FrustrationLevel.NONE
        assert result.escalation_risk <= 0.2
        assert len(result.indicators) == 0

    async def test_mild_frustration_detection(
        self,
        frustration_detector,
        mock_llm_manager
    ):
        """Test detection of mild frustration."""
        mild_frustration_messages = [
            {"role": "customer", "content": "I've been waiting for a while now."},
            {"role": "customer", "content": "Is there anyone available to help me?"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "frustration_level": "low",
            "confidence": 0.78,
            "indicators": ["waiting_time_complaint", "repeated_inquiries"],
            "escalation_risk": 0.3,
            "recommended_actions": ["Provide status update", "Ensure prompt responses"]
        })

        result = await frustration_detector.detect_frustration(mild_frustration_messages)

        assert result.frustration_level == FrustrationLevel.LOW
        assert 0.2 <= result.escalation_risk <= 0.4
        assert len(result.indicators) > 0

    async def test_severe_frustration_detection(
        self,
        frustration_detector,
        mock_llm_manager
    ):
        """Test detection of severe frustration."""
        severe_frustration_messages = [
            {"role": "customer", "content": "This is absolutely ridiculous! I've been waiting forever!"},
            {"role": "customer", "content": "Nobody is helping me and this is a waste of my time!"},
            {"role": "customer", "content": "I want to speak to a manager right now!"}
        ]

        mock_llm_manager.generate_response.return_value = json.dumps({
            "frustration_level": "severe",
            "confidence": 0.95,
            "indicators": [
                "angry_language",
                "threats_to_leave",
                "demands_supervisor",
                "repeated_complaints"
            ],
            "escalation_risk": 0.9,
            "recommended_actions": [
                "Immediate escalation to human agent",
                "Offer apology and compensation",
                "Prioritize resolution"
            ]
        })

        result = await frustration_detector.detect_frustration(severe_frustration_messages)

        assert result.frustration_level == FrustrationLevel.SEVERE
        assert result.escalation_risk >= 0.8
        assert len(result.indicators) >= 3


@pytest.mark.unit
class TestCoachingEngine:
    """Test suite for Coaching Engine."""

    @pytest.fixture
    def coaching_engine(self, mock_llm_manager, mock_prompt_manager):
        """Create coaching engine for testing."""
        return CoachingEngine(mock_llm_manager, mock_prompt_manager)

    @pytest.fixture
    def sample_coaching_request(self):
        """Create sample coaching request."""
        return CoachingRequest(
            agent_id="agent_001",
            conversation_ids=["conv_001", "conv_002", "conv_003"],
            feedback_type="automated",
            time_period_days=7
        )

    async def test_coaching_insights_generation(
        self,
        coaching_engine,
        sample_coaching_request,
        mock_llm_manager
    ):
        """Test generation of coaching insights."""
        # Mock LLM response for skill analysis
        mock_llm_manager.generate_response.return_value = json.dumps({
            "current_level": 3.2,
            "target_level": 4.5,
            "priority": "High",
            "feedback": "Good communication skills but needs improvement in product knowledge",
            "action_items": ["Complete product training module", "Shadow senior agents"],
            "resources": ["Product knowledge base", "Training videos"],
            "timeline": "2 weeks"
        })

        result = await coaching_engine.generate_coaching_insights(sample_coaching_request)

        assert result is not None
        assert result.agent_id == "agent_001"
        assert len(result.insights) > 0
        assert result.overall_rating >= 1.0 and result.overall_rating <= 5.0
        assert len(result.strengths) > 0 or len(result.areas_for_improvement) > 0

    async def test_coaching_with_focus_areas(
        self,
        coaching_engine,
        mock_llm_manager
    ):
        """Test coaching with specific focus areas."""
        focused_request = CoachingRequest(
            agent_id="agent_002",
            conversation_ids=["conv_004"],
            focus_areas=["product_knowledge", "efficiency"]
        )

        mock_llm_manager.generate_response.return_value = json.dumps({
            "current_level": 2.8,
            "target_level": 4.0,
            "priority": "Medium",
            "feedback": "Needs improvement in product knowledge and response efficiency",
            "action_items": ["Study product catalogs", "Practice quick responses"],
            "resources": ["Product guides", "Efficiency training"],
            "timeline": "3 weeks"
        })

        result = await coaching_engine.generate_coaching_insights(focused_request)

        # Verify that focus areas were addressed
        focus_categories = [insight.skill_category for insight in result.insights]
        assert "product_knowledge" in focus_categories
        assert "efficiency" in focus_categories

    async def test_feedback_trend_analysis(
        self,
        coaching_engine,
        mock_llm_manager
    ):
        """Test analysis of feedback trends over time."""
        mock_llm_manager.generate_response.return_value = json.dumps({
            "total_feedback": 25,
            "average_rating": 4.1,
            "rating_trend": "improving",
            "key_strengths": ["Communication", "Problem solving"],
            "improvement_areas": ["Product knowledge", "Follow-up procedures"],
            "coaching_recommendations": [
                "Continue current communication training",
                "Focus on product knowledge enhancement"
            ],
            "performance_comparison": {
                "team_average": 3.9,
                "top_performer": 4.6
            }
        })

        result = await coaching_engine.analyze_feedback_trends("agent_001", 30)

        assert result.agent_id == "agent_001"
        assert result.analysis_period == "Last 30 days"
        assert result.rating_trend == "improving"
        assert result.average_rating > 3.5