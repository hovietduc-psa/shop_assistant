"""
Unit tests for API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import json

from app.main import app
from app.api.v1.endpoints.intelligence.escalation import router as escalation_router
from app.api.v1.endpoints.intelligence.quality import router as quality_router


@pytest.mark.unit
class TestEscalationAPI:
    """Test suite for Escalation API endpoints."""

    @pytest.fixture
    def escalation_client(self, test_client):
        """Create test client for escalation endpoints."""
        return test_client

    def test_analyze_escalation_success(
        self,
        escalation_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test successful escalation analysis."""
        with patch('app.api.v1.endpoints.intelligence.escalation.get_llm_manager') as mock_get_llm:
            mock_get_llm.return_value = mock_llm_manager

            with patch('app.api.v1.endpoints.intelligence.escalation.get_prompt_manager') as mock_get_prompt:
                mock_prompt_manager = MagicMock()
                mock_get_prompt.return_value = mock_prompt_manager

                # Mock LLM response
                mock_llm_manager.generate_response.return_value = json.dumps({
                    "should_escalate": True,
                    "confidence": 0.85,
                    "reasoning": "Customer shows signs of frustration",
                    "urgency_score": 7.5,
                    "triggers": [
                        {
                            "type": "customer_frustration",
                            "reason": "frustration",
                            "description": "Repeated expressions of frustration",
                            "severity": "high"
                        }
                    ]
                })

                escalation_request = {
                    "conversation_id": "conv_001",
                    "messages": [
                        {"role": "customer", "content": "I'm getting very frustrated with this service!"},
                        {"role": "agent", "content": "I understand your frustration and want to help."}
                    ],
                    "customer_id": "cust_001",
                    "context": {"previous_issues": 2}
                }

                response = escalation_client.post(
                    "/api/v1/intelligence/escalation/analyze",
                    json=escalation_request
                )

                assert response.status_code == 200
                data = response.json()
                assert data["decision"]["should_escalate"] is True
                assert data["decision"]["confidence"] >= 0.8
                assert len(data["decision"]["triggers"]) > 0

    def test_analyze_escalation_invalid_request(self, escalation_client):
        """Test escalation analysis with invalid request."""
        invalid_request = {
            "conversation_id": "",  # Invalid empty ID
            "messages": [],  # Empty messages
            "customer_id": "cust_001"
        }

        response = escalation_client.post(
            "/api/v1/intelligence/escalation/analyze",
            json=invalid_request
        )

        assert response.status_code == 422  # Validation error

    def test_analyze_escalation_unauthorized(self, escalation_client):
        """Test escalation analysis without authentication."""
        # Remove authentication override
        app.dependency_overrides.clear()

        escalation_request = {
            "conversation_id": "conv_001",
            "messages": [{"role": "customer", "content": "Test message"}],
            "customer_id": "cust_001"
        }

        response = escalation_client.post(
            "/api/v1/intelligence/escalation/analyze",
            json=escalation_request
        )

        assert response.status_code == 401  # Unauthorized

    def test_batch_analyze_escalations_success(
        self,
        escalation_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test successful batch escalation analysis."""
        with patch('app.api.v1.endpoints.intelligence.escalation.get_llm_manager') as mock_get_llm:
            mock_get_llm.return_value = mock_llm_manager

            with patch('app.api.v1.endpoints.intelligence.escalation.get_prompt_manager') as mock_get_prompt:
                mock_get_prompt.return_value = MagicMock()

                mock_llm_manager.generate_response.return_value = json.dumps({
                    "should_escalate": False,
                    "confidence": 0.9,
                    "reasoning": "Routine inquiry, no escalation needed",
                    "urgency_score": 2.0,
                    "triggers": []
                })

                batch_request = [
                    {
                        "conversation_id": "conv_001",
                        "messages": [{"role": "customer", "content": "What are your hours?"}],
                        "customer_id": "cust_001"
                    },
                    {
                        "conversation_id": "conv_002",
                        "messages": [{"role": "customer", "content": "Do you have this in stock?"}],
                        "customer_id": "cust_002"
                    }
                ]

                response = escalation_client.post(
                    "/api/v1/intelligence/escalation/analyze/batch",
                    json=batch_request
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert all(result["decision"]["should_escalate"] is False for result in data)

    def test_batch_analyze_escalations_too_large(self, escalation_client, mock_current_user):
        """Test batch escalation analysis with too many requests."""
        # Create batch with 51 requests (over the limit)
        batch_request = [
            {
                "conversation_id": f"conv_{i:03d}",
                "messages": [{"role": "customer", "content": f"Test message {i}"}],
                "customer_id": f"cust_{i:03d}"
            }
            for i in range(51)
        ]

        response = escalation_client.post(
            "/api/v1/intelligence/escalation/analyze/batch",
            json=batch_request
        )

        assert response.status_code == 400
        assert "cannot exceed 50" in response.json()["detail"]

    def test_get_escalation_triggers(self, escalation_client, mock_current_user):
        """Test getting escalation trigger information."""
        response = escalation_client.get("/api/v1/intelligence/escalation/triggers")

        assert response.status_code == 200
        data = response.json()
        assert "triggers" in data
        assert "customer_frustration" in data["triggers"]
        assert "technical_limitation" in data["triggers"]
        assert "complexity" in data["triggers"]

    def test_get_escalation_statistics(
        self,
        escalation_client,
        mock_current_user
    ):
        """Test getting escalation statistics."""
        response = escalation_client.get("/api/v1/intelligence/escalation/statistics?days=30")

        assert response.status_code == 200
        data = response.json()
        assert "time_period_days" in data
        assert data["time_period_days"] == 30
        assert "total_conversations" in data
        assert "escalation_rate" in data
        assert "top_triggers" in data
        assert len(data["top_triggers"]) > 0

    def test_get_escalation_statistics_invalid_days(self, escalation_client, mock_current_user):
        """Test escalation statistics with invalid days parameter."""
        response = escalation_client.get("/api/v1/intelligence/escalation/statistics?days=400")

        assert response.status_code == 400
        assert "cannot exceed 365" in response.json()["detail"]

    def test_submit_escalation_feedback_success(
        self,
        escalation_client,
        mock_current_user
    ):
        """Test successful escalation feedback submission."""
        feedback_data = {
            "conversation_id": "conv_001",
            "escalation_id": "esc_001",
            "was_correct": True,
            "feedback_notes": "Escalation was appropriate and timely",
            "actual_outcome": "Customer issue resolved successfully"
        }

        response = escalation_client.post(
            "/api/v1/intelligence/escalation/feedback",
            json=feedback_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "feedback_id" in data

    def test_submit_escalation_feedback_invalid_rating(self, escalation_client, mock_current_user):
        """Test escalation feedback with invalid accuracy rating."""
        feedback_data = {
            "conversation_id": "conv_001",
            "escalation_id": "esc_001",
            "was_correct": True,
            "feedback_notes": "Test feedback"
        }

        response = escalation_client.post(
            "/api/v1/intelligence/escalation/feedback",
            json=feedback_data
        )

        # Missing accuracy_rating should cause validation error
        assert response.status_code == 422


@pytest.mark.unit
class TestQualityAPI:
    """Test suite for Quality API endpoints."""

    @pytest.fixture
    def quality_client(self, test_client):
        """Create test client for quality endpoints."""
        return test_client

    def test_assess_conversation_quality_success(
        self,
        quality_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test successful conversation quality assessment."""
        with patch('app.api.v1.endpoints.intelligence.quality.get_llm_manager') as mock_get_llm:
            mock_get_llm.return_value = mock_llm_manager

            with patch('app.api.v1.endpoints.intelligence.quality.get_prompt_manager') as mock_get_prompt:
                mock_get_prompt.return_value = MagicMock()

                # Mock LLM response
                mock_llm_manager.generate_response.return_value = json.dumps({
                    "overall_score": 8.2,
                    "confidence": 0.88,
                    "strengths": ["Excellent communication", "Quick problem resolution"],
                    "weaknesses": ["Could improve product knowledge"],
                    "metrics": [
                        {
                            "category": "communication",
                            "score": 9.0,
                            "confidence": 0.9,
                            "evidence": ["Clear explanations", "Empathetic tone"]
                        }
                    ],
                    "summary": "Strong overall performance with minor improvement areas",
                    "actionable_insights": ["Complete product knowledge training"]
                })

                quality_request = {
                    "conversation_id": "conv_001",
                    "messages": [
                        {"role": "customer", "content": "I need help with my order"},
                        {"role": "agent", "content": "I'd be happy to help you with your order. Can you provide the order number?"}
                    ],
                    "agent_id": "agent_001",
                    "customer_id": "cust_001"
                }

                response = quality_client.post(
                    "/api/v1/intelligence/quality/assess",
                    json=quality_request
                )

                assert response.status_code == 200
                data = response.json()
                assert data["numeric_score"] >= 8.0
                assert data["confidence"] >= 0.8
                assert len(data["strengths"]) > 0
                assert len(data["metrics"]) > 0

    def test_assess_conversation_quality_invalid_request(self, quality_client):
        """Test quality assessment with invalid request."""
        invalid_request = {
            "conversation_id": "conv_001",
            "messages": "invalid_messages",  # Should be a list
            "agent_id": "agent_001"
        }

        response = quality_client.post(
            "/api/v1/intelligence/quality/assess",
            json=invalid_request
        )

        assert response.status_code == 422

    def test_batch_assess_quality_success(
        self,
        quality_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test successful batch quality assessment."""
        with patch('app.api.v1.endpoints.intelligence.quality.get_llm_manager') as mock_get_llm:
            mock_get_llm.return_value = mock_llm_manager

            with patch('app.api.v1.endpoints.intelligence.quality.get_prompt_manager') as mock_get_prompt:
                mock_get_prompt.return_value = MagicMock()

                mock_llm_manager.generate_response.return_value = json.dumps({
                    "overall_score": 7.5,
                    "confidence": 0.85,
                    "strengths": ["Good customer service"],
                    "weaknesses": ["Response time could be improved"],
                    "metrics": [],
                    "summary": "Good performance with room for improvement",
                    "actionable_insights": ["Focus on reducing response time"]
                })

                batch_request = [
                    {
                        "conversation_id": "conv_001",
                        "messages": [{"role": "customer", "content": "Question about product"}],
                        "agent_id": "agent_001"
                    },
                    {
                        "conversation_id": "conv_002",
                        "messages": [{"role": "customer", "content": "Order status inquiry"}],
                        "agent_id": "agent_002"
                    }
                ]

                response = quality_client.post(
                    "/api/v1/intelligence/quality/assess/batch",
                    json=batch_request
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 2
                assert all(assessment["numeric_score"] >= 7.0 for assessment in data)

    def test_get_quality_metrics(self, quality_client, mock_current_user):
        """Test getting quality metrics information."""
        response = quality_client.get("/api/v1/intelligence/quality/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "communication" in data["metrics"]
        assert "problem_solving" in data["metrics"]
        assert "product_knowledge" in data["metrics"]
        assert "scoring_scale" in data

    def test_get_quality_statistics(
        self,
        quality_client,
        mock_current_user
    ):
        """Test getting quality statistics."""
        response = quality_client.get("/api/v1/intelligence/quality/statistics?days=30")

        assert response.status_code == 200
        data = response.json()
        assert "time_period_days" in data
        assert data["time_period_days"] == 30
        assert "total_conversations_assessed" in data
        assert "average_quality_score" in data
        assert "quality_distribution" in data
        assert "metric_averages" in data

    def test_get_agent_quality_performance(
        self,
        quality_client,
        mock_current_user
    ):
        """Test getting agent quality performance."""
        agent_id = "agent_001"
        response = quality_client.get(f"/api/v1/intelligence/quality/agent/{agent_id}/performance?days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == agent_id
        assert "overall_quality_score" in data
        assert "metric_breakdown" in data
        assert "strengths" in data
        assert "improvement_areas" in data
        assert "recommendations" in data

    def test_submit_quality_feedback_success(
        self,
        quality_client,
        mock_current_user
    ):
        """Test successful quality feedback submission."""
        feedback_data = {
            "conversation_id": "conv_001",
            "assessment_id": "qa_001",
            "accuracy_rating": 5,
            "feedback_notes": "Quality assessment was very accurate",
            "corrected_metrics": {
                "communication": 9.0,
                "problem_solving": 8.5
            }
        }

        response = quality_client.post(
            "/api/v1/intelligence/quality/feedback",
            json=feedback_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "feedback_id" in data

    def test_submit_quality_feedback_invalid_rating(self, quality_client, mock_current_user):
        """Test quality feedback with invalid rating."""
        feedback_data = {
            "conversation_id": "conv_001",
            "assessment_id": "qa_001",
            "accuracy_rating": 6,  # Invalid rating (should be 1-5)
            "feedback_notes": "Test feedback"
        }

        response = quality_client.post(
            "/api/v1/intelligence/quality/feedback",
            json=feedback_data
        )

        assert response.status_code == 400
        assert "must be between 1 and 5" in response.json()["detail"]


@pytest.mark.unit
class TestIntelligenceAPI:
    """Test suite for Intelligence Dashboard API endpoints."""

    @pytest.fixture
    def intelligence_client(self, test_client):
        """Create test client for intelligence dashboard endpoints."""
        return test_client

    def test_get_intelligence_overview(self, intelligence_client, mock_current_user):
        """Test getting intelligence system overview."""
        response = intelligence_client.get("/api/v1/intelligence/dashboard/overview")

        assert response.status_code == 200
        data = response.json()
        assert "system_status" in data
        assert "escalation_intelligence" in data
        assert "quality_intelligence" in data
        assert "coaching_intelligence" in data
        assert "qa_automation" in data
        assert "learning_system" in data
        assert "performance_metrics" in data

    def test_get_intelligence_overview_unauthorized(self, intelligence_client):
        """Test intelligence overview without authentication."""
        app.dependency_overrides.clear()

        response = intelligence_client.get("/api/v1/intelligence/dashboard/overview")

        assert response.status_code == 401

    def test_trigger_intelligence_analysis_success(
        self,
        intelligence_client,
        mock_current_user,
        mock_intelligence_manager
    ):
        """Test successful intelligence analysis trigger."""
        with patch('app.api.v1.endpoints.intelligence.dashboard.get_intelligence_manager') as mock_get_manager:
            mock_get_manager.return_value = mock_intelligence_manager

            # Mock the check escalation method
            mock_intelligence_manager.check_escalation_needed = AsyncMock(
                return_value=(True, {"decision": {"should_escalate": True}})
            )

            analysis_data = {
                "conversation_id": "conv_001",
                "analysis_types": ["escalation", "quality"]
            }

            response = intelligence_client.post(
                "/api/v1/intelligence/dashboard/trigger-analysis",
                json=analysis_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == "conv_001"
            assert "escalation" in data["analyses"]
            assert "quality" in data["analyses"]

    def test_trigger_intelligence_analysis_invalid_types(
        self,
        intelligence_client,
        mock_current_user
    ):
        """Test intelligence analysis with invalid analysis types."""
        analysis_data = {
            "conversation_id": "conv_001",
            "analysis_types": ["invalid_type", "another_invalid"]
        }

        response = intelligence_client.post(
            "/api/v1/intelligence/dashboard/trigger-analysis",
            json=analysis_data
        )

        assert response.status_code == 400
        assert "Invalid analysis types" in response.json()["detail"]

    def test_get_intelligence_alerts(
        self,
        intelligence_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test getting intelligence alerts."""
        with patch('app.api.v1.endpoints.intelligence.dashboard.get_llm_manager') as mock_get_llm:
            mock_get_llm.return_value = mock_llm_manager

            with patch('app.api.v1.endpoints.intelligence.dashboard.get_prompt_manager') as mock_get_prompt:
                mock_get_prompt.return_value = MagicMock()

                response = intelligence_client.get("/api/v1/intelligence/dashboard/alerts")

                assert response.status_code == 200
                data = response.json()
                assert "alerts" in data
                assert "total_count" in data
                assert "retrieved_at" in data

    def test_get_intelligence_alerts_with_filters(
        self,
        intelligence_client,
        mock_current_user
    ):
        """Test getting intelligence alerts with filters."""
        response = intelligence_client.get(
            "/api/v1/intelligence/dashboard/alerts?severity=warning&alert_type=quality_threshold_breach&limit=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert "filters_applied" in data
        assert data["filters_applied"]["severity"] == "warning"
        assert data["filters_applied"]["alert_type"] == "quality_threshold_breach"
        assert data["filters_applied"]["limit"] == 10

    def test_trigger_learning_cycle_success(
        self,
        intelligence_client,
        mock_current_user,
        mock_intelligence_manager
    ):
        """Test successful learning cycle trigger."""
        with patch('app.api.v1.endpoints.intelligence.dashboard.get_intelligence_manager') as mock_get_manager:
            mock_get_manager.return_value = mock_intelligence_manager

            # Mock learning cycle method
            mock_intelligence_manager.run_learning_cycle = AsyncMock(
                return_value={
                    "iterations": 3,
                    "insights_generated": 12,
                    "improvements_applied": 5
                }
            )

            learning_data = {
                "learning_types": ["quality_scoring", "escalation_triggers"]
            }

            response = intelligence_client.post(
                "/api/v1/intelligence/dashboard/learning/trigger",
                json=learning_data
            )

            assert response.status_code == 200
            data = response.json()
            assert data["learning_cycle_triggered"] is True
            assert data["learning_types"] == ["quality_scoring", "escalation_triggers"]
            assert "results" in data

    def test_get_intelligence_system_health(
        self,
        intelligence_client,
        mock_current_user,
        mock_intelligence_manager
    ):
        """Test getting intelligence system health."""
        with patch('app.api.v1.endpoints.intelligence.dashboard.get_intelligence_manager') as mock_get_manager:
            mock_get_manager.return_value = mock_intelligence_manager

            # Mock active analyses
            mock_intelligence_manager.active_analyses = {
                "conv_001": {"status": "processing"},
                "conv_002": {"status": "processing"}
            }
            mock_intelligence_manager.analysis_queue = MagicMock()
            mock_intelligence_manager.analysis_queue.qsize.return_value = 3

            response = intelligence_client.get("/api/v1/intelligence/dashboard/health")

            assert response.status_code == 200
            data = response.json()
            assert "overall_health" in data
            assert "systems" in data
            assert "performance_metrics" in data
            assert "resource_usage" in data
            assert "uptime_percentage" in data


@pytest.mark.unit
class TestErrorHandling:
    """Test suite for API error handling."""

    @pytest.fixture
    def error_client(self, test_client):
        """Create test client for error testing."""
        return test_client

    def test_404_not_found(self, error_client, mock_current_user):
        """Test 404 error handling."""
        response = error_client.get("/api/v1/intelligence/nonexistent-endpoint")

        assert response.status_code == 404
        assert "Not Found" in response.json()["detail"]

    def test_422_validation_error(self, error_client, mock_current_user):
        """Test validation error handling."""
        # Send malformed JSON
        response = error_client.post(
            "/api/v1/intelligence/escalation/analyze",
            json="invalid_json"
        )

        assert response.status_code == 422

    def test_500_internal_server_error(self, error_client, mock_current_user):
        """Test internal server error handling."""
        with patch('app.api.v1.endpoints.intelligence.escalation.get_llm_manager') as mock_get_llm:
            # Make LLM manager raise an exception
            mock_get_llm.side_effect = Exception("Database connection failed")

            escalation_request = {
                "conversation_id": "conv_001",
                "messages": [{"role": "customer", "content": "Test"}],
                "customer_id": "cust_001"
            }

            response = error_client.post(
                "/api/v1/intelligence/escalation/analyze",
                json=escalation_request
            )

            assert response.status_code == 500
            assert "Failed to analyze escalation request" in response.json()["detail"]