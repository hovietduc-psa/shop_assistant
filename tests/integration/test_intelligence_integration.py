"""
Integration tests for AI Intelligence components working together.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
import asyncio

from app.core.intelligence.integration import (
    ConversationIntelligenceManager, IntelligenceTrigger
)
from app.core.intelligence import (
    EscalationEngine, QualityAssessor, SentimentAnalyzer,
    CoachingEngine, SupervisorReviewEngine, QAAutomationEngine
)


@pytest.mark.integration
class TestConversationIntelligenceManager:
    """Test suite for Conversation Intelligence Manager integration."""

    @pytest.fixture
    async def intelligence_manager(self, mock_llm_manager, mock_prompt_manager):
        """Create intelligence manager for testing."""
        manager = ConversationIntelligenceManager(mock_llm_manager, mock_prompt_manager)
        await manager.initialize()
        yield manager
        await manager.shutdown()

    @pytest.fixture
    def sample_conversation_flow(self):
        """Create a sample conversation flow for testing."""
        return [
            {
                "id": "msg_001",
                "role": "customer",
                "content": "Hi, I need help with my recent order. It hasn't arrived yet.",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"message_type": "inquiry"}
            },
            {
                "id": "msg_002",
                "role": "agent",
                "content": "I'd be happy to help you track your order. Could you please provide your order number?",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"message_type": "response"}
            },
            {
                "id": "msg_003",
                "role": "customer",
                "content": "The order number is ORD-12345. I'm getting really frustrated because this was supposed to be delivered yesterday!",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"message_type": "frustration"}
            },
            {
                "id": "msg_004",
                "role": "agent",
                "content": "I understand your frustration and I apologize for the delay. Let me check the status of order ORD-12345 right away.",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {"message_type": "empathy_response"}
            }
        ]

    async def test_full_conversation_analysis_flow(
        self,
        intelligence_manager,
        sample_conversation_flow,
        mock_llm_manager
    ):
        """Test complete conversation analysis from start to finish."""
        conversation_id = "integration_test_001"
        agent_id = "agent_integration_001"
        customer_id = "cust_integration_001"

        # Setup mock responses for different analysis types
        def mock_llm_responses(prompt, **kwargs):
            if "escalation" in prompt.lower():
                return json.dumps({
                    "should_escalate": True,
                    "confidence": 0.85,
                    "reasoning": "Customer frustration detected, requires human intervention",
                    "urgency_score": 7.5,
                    "triggers": [
                        {
                            "type": "customer_frustration",
                            "reason": "frustration",
                            "description": "Customer expressed frustration about delivery delay",
                            "severity": "high"
                        }
                    ]
                })
            elif "sentiment" in prompt.lower():
                return json.dumps({
                    "overall_sentiment": "negative",
                    "sentiment_score": -0.6,
                    "confidence": 0.9,
                    "key_phrases": ["frustrated", "delayed", "supposed to be delivered"],
                    "emotional_indicators": ["frustration", "disappointment"]
                })
            elif "frustration" in prompt.lower():
                return json.dumps({
                    "frustration_level": "high",
                    "confidence": 0.88,
                    "indicators": ["frustrated", "delay_mention", "expectation_not_met"],
                    "escalation_risk": 0.8,
                    "recommended_actions": ["Immediate attention", "Apology and resolution"]
                })
            else:
                return json.dumps({"analysis": "completed"})

        mock_llm_manager.generate_response.side_effect = mock_llm_responses

        # Process each message in the conversation
        for i, message in enumerate(sample_conversation_flow):
            context = {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "customer_id": customer_id,
                "message_index": i
            }

            # Trigger appropriate intelligence analysis based on message type
            if i == 0:  # First customer message
                trigger = IntelligenceTrigger.MESSAGE_RECEIVED
            elif i == 2:  # Frustration message
                trigger = IntelligenceTrigger.FRUSTRATION_DETECTED
            else:
                trigger = IntelligenceTrigger.MESSAGE_RECEIVED

            result = await intelligence_manager.process_message_event(
                conversation_id,
                message,
                trigger,
                context
            )

            assert result["conversation_id"] == conversation_id
            assert result["queued_for_analysis"] is True

        # Process conversation end
        conversation_data = {
            "conversation_id": conversation_id,
            "messages": sample_conversation_flow,
            "agent_id": agent_id,
            "customer_id": customer_id,
            "context": {"total_messages": len(sample_conversation_flow)}
        }

        end_results = await intelligence_manager.process_conversation_ended(
            conversation_id,
            conversation_data
        )

        # Verify comprehensive analysis was performed
        assert "quality" in end_results
        assert "sentiment" in end_results
        assert "frustration" in end_results
        assert "qa_alerts" in end_results

        # Verify escalation was triggered due to frustration
        should_escalate, escalation_response = await intelligence_manager.check_escalation_needed(
            conversation_id,
            conversation_data
        )

        assert should_escalate is True
        assert escalation_response.decision.confidence >= 0.8

    async def test_real_time_sentiment_and_frustration_detection(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test real-time sentiment and frustration detection during conversation."""
        conversation_id = "sentiment_test_001"

        # Setup mock responses
        mock_llm_manager.generate_response.side_effect = [
            # First sentiment analysis (neutral)
            json.dumps({
                "overall_sentiment": "neutral",
                "sentiment_score": 0.1,
                "confidence": 0.8,
                "key_phrases": ["question", "help"],
                "emotional_indicators": ["information_seeking"]
            }),
            # Frustration detection
            json.dumps({
                "frustration_level": "medium",
                "confidence": 0.75,
                "indicators": ["waiting", "impatient"],
                "escalation_risk": 0.5,
                "recommended_actions": ["Provide status update"]
            }),
            # Second sentiment analysis (negative)
            json.dumps({
                "overall_sentiment": "negative",
                "sentiment_score": -0.7,
                "confidence": 0.9,
                "key_phrases": ["frustrated", "waiting too long"],
                "emotional_indicators": ["frustration", "impatience"]
            })
        ]

        # Message 1: Neutral inquiry
        message1 = {
            "id": "msg_001",
            "role": "customer",
            "content": "Hi, I have a question about my order status.",
            "timestamp": datetime.utcnow().isoformat()
        }

        result1 = await intelligence_manager.process_message_event(
            conversation_id,
            message1,
            IntelligenceTrigger.MESSAGE_RECEIVED,
            {"agent_id": "agent_001"}
        )

        assert result1["conversation_id"] == conversation_id

        # Message 2: Growing frustration
        message2 = {
            "id": "msg_002",
            "role": "customer",
            "content": "I've been waiting for a while now, is anyone going to help me?",
            "timestamp": datetime.utcnow().isoformat()
        }

        result2 = await intelligence_manager.process_message_event(
            conversation_id,
            message2,
            IntelligenceTrigger.SENTIMENT_NEGATIVE,
            {"agent_id": "agent_001"}
        )

        assert result2["conversation_id"] == conversation_id

        # Check that frustration alert was created
        conversation_state = intelligence_manager.active_analyses.get(conversation_id, {})
        alerts = conversation_state.get("alerts", [])

        frustration_alerts = [a for a in alerts if a.get("type") == "frustration"]
        assert len(frustration_alerts) > 0
        assert frustration_alerts[0]["level"] == "medium"

    async def test_quality_threshold_breach_handling(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test handling of quality threshold breaches."""
        conversation_id = "quality_test_001"

        # Mock low quality assessment
        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 3.2,
            "confidence": 0.85,
            "strengths": [],
            "weaknesses": [
                "Poor communication skills",
                "Lack of product knowledge",
                "Unprofessional tone"
            ],
            "metrics": [
                {
                    "category": "communication",
                    "score": 2.5,
                    "confidence": 0.9,
                    "evidence": ["Abrupt responses", "Lack of empathy"]
                }
            ],
            "summary": "Significant quality issues requiring immediate attention",
            "actionable_insights": ["Immediate coaching required", "Additional training needed"]
        })

        # Trigger quality assessment
        await intelligence_manager.process_message_event(
            conversation_id,
            {
                "id": "msg_001",
                "role": "agent",
                "content": "I don't know. Check the website.",
                "timestamp": datetime.utcnow().isoformat()
            },
            IntelligenceTrigger.QUALITY_THRESHOLD_BREACH,
            {"agent_id": "agent_001", "quality_score": 2.5}
        )

        # Verify quality alert was created
        conversation_state = intelligence_manager.active_analyses.get(conversation_id, {})
        alerts = conversation_state.get("alerts", [])

        quality_alerts = [a for a in alerts if a.get("type") == "quality_threshold_breach"]
        assert len(quality_alerts) > 0
        assert quality_alerts[0]["requires_review"] is True

    async def test_coaching_data_accumulation(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test accumulation of coaching data across conversations."""
        agent_id = "agent_coaching_001"

        # Create multiple conversations for the same agent
        conversations = [
            {
                "conversation_id": f"conv_00{i}",
                "messages": [
                    {"role": "customer", "content": f"Question {i}"},
                    {"role": "agent", "content": f"Answer {i}"}
                ],
                "agent_id": agent_id,
                "customer_id": f"cust_00{i}"
            }
            for i in range(1, 4)  # 3 conversations
        ]

        # Mock quality assessments for each conversation
        mock_llm_manager.generate_response.return_value = json.dumps({
            "overall_score": 7.5,
            "confidence": 0.8,
            "strengths": ["Good communication"],
            "weaknesses": ["Could improve product knowledge"],
            "metrics": [],
            "summary": "Good performance with minor improvements needed",
            "actionable_insights": ["Product training recommended"]
        })

        # Process each conversation
        for conv_data in conversations:
            await intelligence_manager.process_conversation_ended(
                conv_data["conversation_id"],
                conv_data
            )

        # Verify coaching data was accumulated
        assert hasattr(intelligence_manager, '_coaching_data')
        assert agent_id in intelligence_manager._coaching_data
        assert len(intelligence_manager._coaching_data[agent_id]) == 3

        # Generate batch coaching feedback
        coaching_feedback = await intelligence_manager.generate_agent_coaching_batch(agent_id)

        assert coaching_feedback is not None
        assert coaching_feedback.agent_id == agent_id
        assert len(coaching_feedback.insights) > 0

    async def test_background_analysis_queue_processing(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test that background analysis queue processes requests correctly."""
        conversation_id = "queue_test_001"

        # Mock quick analysis responses
        mock_llm_manager.generate_response.return_value = json.dumps({
            "analysis_complete": True,
            "processing_time": 0.5
        })

        # Queue multiple analysis requests
        for i in range(5):
            message = {
                "id": f"msg_00{i}",
                "role": "customer",
                "content": f"Test message {i}",
                "timestamp": datetime.utcnow().isoformat()
            }

            await intelligence_manager.process_message_event(
                conversation_id,
                message,
                IntelligenceTrigger.MESSAGE_RECEIVED,
                {"message_index": i}
            )

        # Give background task time to process
        await asyncio.sleep(0.1)

        # Verify that conversation state was updated
        conversation_state = intelligence_manager.active_analyses.get(conversation_id)
        assert conversation_state is not None
        assert len(conversation_state["messages"]) == 5

    async def test_intelligence_system_error_recovery(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test error recovery in intelligence systems."""
        conversation_id = "error_test_001"

        # Make LLM manager raise an exception initially
        mock_llm_manager.generate_response.side_effect = [
            Exception("Temporary API failure"),
            json.dumps({
                "should_escalate": False,
                "confidence": 0.9,
                "reasoning": "API recovered, no escalation needed",
                "urgency_score": 2.0,
                "triggers": []
            })
        ]

        # Process message that should trigger analysis
        message = {
            "id": "msg_001",
            "role": "customer",
            "content": "I need help with something simple.",
            "timestamp": datetime.utcnow().isoformat()
        }

        # System should handle the error gracefully
        result = await intelligence_manager.process_message_event(
            conversation_id,
            message,
            IntelligenceTrigger.MESSAGE_RECEIVED,
            {"agent_id": "agent_001"}
        )

        # Should still return success despite the error
        assert result["conversation_id"] == conversation_id
        assert "error" not in result

        # Verify conversation state is still maintained
        conversation_state = intelligence_manager.active_analyses.get(conversation_id)
        assert conversation_state is not None
        assert len(conversation_state["messages"]) == 1

    async def test_learning_cycle_integration(
        self,
        intelligence_manager,
        mock_llm_manager
    ):
        """Test integration of learning cycle with intelligence systems."""
        # Mock learning cycle responses
        mock_llm_manager.generate_response.return_value = json.dumps({
            "insights": [
                {
                    "type": "escalation_pattern",
                    "description": "Frustration indicators need adjustment",
                    "confidence": 0.85,
                    "impact": 7.5,
                    "effort": 4.0
                }
            ],
            "recommendations": ["Update frustration detection thresholds"]
        })

        # Run learning cycle
        learning_results = await intelligence_manager.run_learning_cycle()

        assert learning_results is not None
        assert "iterations" in learning_results
        assert "insights_generated" in learning_results
        assert "improvements_applied" in learning_results

        # Verify learning doesn't break normal operations
        conversation_id = "learning_test_001"
        message = {
            "id": "msg_001",
            "role": "customer",
            "content": "Test message during learning cycle",
            "timestamp": datetime.utcnow().isoformat()
        }

        result = await intelligence_manager.process_message_event(
            conversation_id,
            message,
            IntelligenceTrigger.MESSAGE_RECEIVED,
            {"agent_id": "agent_001"}
        )

        assert result["conversation_id"] == conversation_id


@pytest.mark.integration
class TestIntelligenceSystemCoordination:
    """Test suite for coordination between different intelligence systems."""

    @pytest.fixture
    def intelligence_engines(self, mock_llm_manager, mock_prompt_manager):
        """Create all intelligence engines for integration testing."""
        return {
            "escalation": EscalationEngine(mock_llm_manager, mock_prompt_manager),
            "quality": QualityAssessor(mock_llm_manager, mock_prompt_manager),
            "sentiment": SentimentAnalyzer(mock_llm_manager, mock_prompt_manager),
            "coaching": CoachingEngine(mock_llm_manager, mock_prompt_manager),
            "supervisor": SupervisorReviewEngine(mock_llm_manager, mock_prompt_manager),
            "qa": QAAutomationEngine(mock_llm_manager, mock_prompt_manager)
        }

    async def test_escalation_quality_sentiment_coordination(
        self,
        intelligence_engines,
        mock_llm_manager
    ):
        """Test coordination between escalation, quality, and sentiment systems."""
        conversation_data = {
            "conversation_id": "coord_test_001",
            "messages": [
                {"role": "customer", "content": "This is terrible! I'm very frustrated!"},
                {"role": "agent", "content": "I understand your frustration."}
            ],
            "agent_id": "agent_001",
            "customer_id": "cust_001"
        }

        # Setup coordinated mock responses
        response_count = 0
        def coordinated_responses(prompt, **kwargs):
            nonlocal response_count
            response_count += 1

            if response_count == 1:  # Escalation analysis
                return json.dumps({
                    "should_escalate": True,
                    "confidence": 0.9,
                    "reasoning": "High frustration detected",
                    "urgency_score": 8.5,
                    "triggers": [{"type": "customer_frustration", "severity": "high"}]
                })
            elif response_count == 2:  # Quality assessment
                return json.dumps({
                    "overall_score": 4.2,
                    "confidence": 0.85,
                    "strengths": ["Showed empathy"],
                    "weaknesses": ["Could have de-escalated better"],
                    "metrics": [],
                    "summary": "Needs improvement in handling frustrated customers"
                })
            else:  # Sentiment analysis
                return json.dumps({
                    "overall_sentiment": "very_negative",
                    "sentiment_score": -0.85,
                    "confidence": 0.92,
                    "key_phrases": ["terrible", "frustrated"],
                    "emotional_indicators": ["anger", "frustration"]
                })

        mock_llm_manager.generate_response.side_effect = coordinated_responses

        # Run coordinated analyses
        from app.core.intelligence import EscalationRequest, QualityAssessmentRequest

        # Escalation analysis
        escalation_request = EscalationRequest(
            conversation_id=conversation_data["conversation_id"],
            messages=conversation_data["messages"],
            customer_id=conversation_data["customer_id"]
        )
        escalation_result = await intelligence_engines["escalation"].analyze_escalation(escalation_request)

        # Quality assessment
        quality_request = QualityAssessmentRequest(
            conversation_id=conversation_data["conversation_id"],
            messages=conversation_data["messages"],
            agent_id=conversation_data["agent_id"]
        )
        quality_result = await intelligence_engines["quality"].assess_conversation_quality(quality_request)

        # Sentiment analysis
        sentiment_result = await intelligence_engines["sentiment"].analyze_sentiment(conversation_data["messages"])

        # Verify coordinated results
        assert escalation_result.decision.should_escalate is True
        assert escalation_result.decision.urgency_score >= 8.0

        assert quality_result.numeric_score <= 5.0  # Poor quality due to frustration handling

        assert sentiment_result.overall_sentiment.value == "very_negative"
        assert sentiment_result.sentiment_score <= -0.8

        # Verify all systems detected the same issue (customer frustration)
        assert any("frustration" in trigger.type for trigger in escalation_result.decision.triggers)
        assert any("frustrated" in weakness for weakness in quality_result.weaknesses)
        assert "frustration" in sentiment_result.emotional_indicators

    async def test_coaching_quality_integration(
        self,
        intelligence_engines,
        mock_llm_manager
    ):
        """Test integration between coaching and quality systems."""
        agent_id = "agent_coach_int_001"
        conversation_ids = ["conv_001", "conv_002", "conv_003"]

        # Mock quality data for coaching analysis
        mock_llm_manager.generate_response.return_value = json.dumps({
            "current_level": 3.5,
            "target_level": 4.5,
            "priority": "Medium",
            "feedback": "Agent shows good communication but needs product knowledge improvement",
            "action_items": ["Complete product training", "Study product catalog"],
            "resources": ["Product knowledge base", "Training videos"],
            "timeline": "3 weeks"
        })

        # Generate coaching insights based on quality data
        from app.core.intelligence import CoachingRequest
        coaching_request = CoachingRequest(
            agent_id=agent_id,
            conversation_ids=conversation_ids,
            feedback_type="automated",
            focus_areas=["product_knowledge", "communication"]
        )

        coaching_result = await intelligence_engines["coaching"].generate_coaching_insights(coaching_request)

        # Verify coaching insights incorporate quality focus areas
        assert coaching_result.agent_id == agent_id
        assert len(coaching_result.insights) > 0

        # Check that product knowledge and communication are addressed
        insight_categories = [insight.skill_category.value for insight in coaching_result.insights]
        assert "product_knowledge" in insight_categories or "communication" in insight_categories

    async def test_qa_supervisor_integration(
        self,
        intelligence_engines,
        mock_llm_manager
    ):
        """Test integration between QA automation and supervisor review systems."""
        conversation_data = {
            "conversation_id": "qa_supervisor_test",
            "messages": [
                {"role": "customer", "content": "I need to speak to a manager about this terrible service!"},
                {"role": "agent", "content": "I'm sorry you feel that way."}
            ],
            "agent_id": "agent_001",
            "customer_id": "cust_001"
        }

        # Create mock quality assessment for QA
        mock_quality_assessment = MagicMock()
        mock_quality_assessment.numeric_score = 2.8
        mock_quality_assessment.overall_score.value = "poor"
        mock_quality_assessment.weaknesses = ["Poor tone", "Lack of empathy"]
        mock_quality_assessment.confidence = 0.9

        # Create mock sentiment analysis
        mock_sentiment = MagicMock()
        mock_sentiment.overall_sentiment.value = "very_negative"
        mock_sentiment.sentiment_score = -0.9
        mock_sentiment.confidence = 0.95

        # Run QA automation check
        qa_alerts = await intelligence_engines["qa"].automated_qa_check(
            conversation_data,
            mock_quality_assessment,
            mock_sentiment
        )

        # Create supervisor review based on QA findings
        mock_escalation_response = MagicMock()
        mock_escalation_response.decision.should_escalate = True
        mock_escalation_response.decision.confidence = 0.95
        mock_escalation_response.decision.urgency_score = 9.0

        supervisor_review = await intelligence_engines["supervisor"].create_escalation_review(
            mock_escalation_response,
            conversation_data
        )

        # Verify integration between QA and supervisor systems
        assert len(qa_alerts) > 0  # QA should detect issues

        critical_qa_alerts = [alert for alert in qa_alerts if alert.severity.value == "critical"]
        assert len(critical_qa_alerts) > 0  # Should find critical quality issues

        # Supervisor review should be created with high priority
        assert supervisor_review.priority.value == "critical"
        assert supervisor_review.requires_immediate_attention is True

    async def test_intelligence_system_state_sharing(
        self,
        intelligence_engines,
        mock_llm_manager
    ):
        """Test that intelligence systems can share state and context."""
        conversation_context = {
            "conversation_id": "state_sharing_test",
            "customer_tier": "premium",
            "previous_issues": 3,
            "agent_experience": "senior",
            "issue_complexity": "high"
        }

        # Mock responses that consider shared context
        def context_aware_responses(prompt, **kwargs):
            if "premium" in str(prompt):
                return json.dumps({
                    "should_escalate": True,
                    "confidence": 0.9,
                    "reasoning": "Premium customer with repeated issues needs immediate attention",
                    "urgency_score": 9.0,
                    "triggers": [{"type": "customer_request", "severity": "high"}]
                })
            else:
                return json.dumps({
                    "analysis": "completed"
                })

        mock_llm_manager.generate_response.side_effect = context_aware_responses

        # Test escalation with context
        from app.core.intelligence import EscalationRequest
        escalation_request = EscalationRequest(
            conversation_id=conversation_context["conversation_id"],
            messages=[{"role": "customer", "content": "I need help again"}],
            context=conversation_context
        )

        escalation_result = await intelligence_engines["escalation"].analyze_escalation(escalation_request)

        # Verify that context influenced the decision
        assert escalation_result.decision.should_escalate is True
        assert escalation_result.decision.urgency_score >= 8.5  # High urgency due to premium tier and repeated issues