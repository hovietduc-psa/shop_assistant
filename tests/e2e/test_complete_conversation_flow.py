"""
End-to-end tests for complete conversation flows.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
import asyncio
import requests
from typing import Dict, Any

from app.main import app


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteConversationFlow:
    """Test suite for complete conversation flows from start to finish."""

    @pytest.fixture
    def e2e_client(self):
        """Create test client for E2E testing."""
        return TestClient(app)

    @pytest.fixture
    def mock_external_apis(self):
        """Mock all external API calls for E2E testing."""
        with patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate') as mock_chat, \
             patch('app.core.llm.llm_manager.openai.Embedding.acreate') as mock_embedding, \
             patch('app.integrations.shopify.client.ShopifyClient') as mock_shopify:

            # Mock LLM responses
            mock_chat.return_value = {
                "choices": [{"message": {"content": "I understand your concern and I'm here to help you resolve this issue."}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75}
            }

            # Mock embedding responses
            mock_embedding.return_value = {
                "data": [{"embedding": [0.1] * 1536}],
                "usage": {"prompt_tokens": 20, "total_tokens": 20}
            }

            # Mock Shopify responses
            mock_shopify_instance = MagicMock()
            mock_shopify_instance.search_products.return_value = ([], False)
            mock_shopify.return_value = mock_shopify_instance

            yield {
                "chat": mock_chat,
                "embedding": mock_embedding,
                "shopify": mock_shopify
            }

    def test_complete_customer_support_flow(
        self,
        e2e_client,
        mock_external_apis,
        mock_current_user
    ):
        """Test complete customer support flow from initial contact to resolution."""
        conversation_id = "e2e_conv_001"
        agent_id = "agent_e2e_001"
        customer_id = "cust_e2e_001"

        # Step 1: Customer initiates conversation
        initial_message = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Hi, I need help with my recent order. It hasn't arrived yet and it was supposed to be delivered yesterday.",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            "context": {
                "source": "web_chat",
                "customer_tier": "premium",
                "previous_conversations": 2
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=initial_message
        )

        assert response.status_code == 200
        message_data = response.json()
        assert message_data["message_id"] is not None

        # Step 2: AI processes message and generates response
        ai_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert ai_response.status_code == 200
        response_data = ai_response.json()
        assert "content" in response_data
        assert "order" in response_data["content"].lower()

        # Step 3: Customer provides order number
        order_number_message = {
            "conversation_id": conversation_id,
            "message": {
                "content": "My order number is ORD-12345. I'm getting really frustrated because I needed this for a event today!",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=order_number_message
        )
        assert response.status_code == 200

        # Step 4: Check if escalation is triggered due to frustration
        escalation_check = e2e_client.post(
            "/api/v1/intelligence/escalation/analyze",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": initial_message["message"]["content"]},
                    {"role": "assistant", "content": response_data["content"]},
                    {"role": "customer", "content": order_number_message["message"]["content"]}
                ],
                "customer_id": customer_id,
                "context": {"frustration_level": "high", "urgency": "event_today"}
            }
        )

        assert escalation_check.status_code == 200
        escalation_data = escalation_check.json()

        # Should recommend escalation due to frustration and urgency
        assert escalation_data["decision"]["should_escalate"] is True
        assert escalation_data["decision"]["urgency_score"] >= 7.0

        # Step 5: Agent accepts escalated conversation
        agent_assignment = {
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "assignment_type": "escalation"
        }

        response = e2e_client.post(
            "/api/v1/agents/assignments",
            json=agent_assignment
        )
        assert response.status_code == 200

        # Step 6: Agent provides human response
        agent_response = {
            "conversation_id": conversation_id,
            "message": {
                "content": "I understand how frustrating this must be, especially when you need it for an event today. I've located your order ORD-12345 and I'm personally going to ensure this gets resolved for you right away.",
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=agent_response
        )
        assert response.status_code == 200

        # Step 7: Customer satisfaction with resolution
        satisfaction_message = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Thank you so much! I really appreciate you taking care of this personally. This is why I'm a loyal customer.",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=satisfaction_message
        )
        assert response.status_code == 200

        # Step 8: End conversation and trigger quality assessment
        end_conversation = {
            "conversation_id": conversation_id,
            "status": "resolved",
            "resolution": "Customer satisfaction restored, order expedited",
            "agent_id": agent_id
        }

        response = e2e_client.post(
            "/api/v1/conversations/end",
            json=end_conversation
        )
        assert response.status_code == 200

        # Step 9: Verify quality assessment was performed
        quality_assessment = e2e_client.post(
            "/api/v1/intelligence/quality/assess",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": initial_message["message"]["content"]},
                    {"role": "assistant", "content": response_data["content"]},
                    {"role": "customer", "content": order_number_message["message"]["content"]},
                    {"role": "agent", "content": agent_response["message"]["content"]},
                    {"role": "customer", "content": satisfaction_message["message"]["content"]}
                ],
                "agent_id": agent_id,
                "customer_id": customer_id
            }
        )

        assert quality_assessment.status_code == 200
        quality_data = quality_assessment.json()

        # Should show good quality due to successful resolution
        assert quality_data["numeric_score"] >= 7.0
        assert "empathy" in str(quality_data["strengths"]).lower()

    def test_complex_product_inquiry_with_recommendations(
        self,
        e2e_client,
        mock_external_apis,
        mock_current_user,
        test_product_data
    ):
        """Test complex product inquiry with AI recommendations."""
        conversation_id = "e2e_prod_001"
        customer_id = "cust_e2e_002"

        # Setup Shopify mock responses
        mock_shopify_client = mock_external_apis["shopify"].return_value
        mock_shopify_client.search_products.return_value = (
            [test_product_data],
            True
        )

        # Step 1: Customer inquiry about product needs
        product_inquiry = {
            "conversation_id": conversation_id,
            "message": {
                "content": "I'm looking for a laptop for video editing. I need something with good processing power, at least 16GB RAM, and a dedicated graphics card. My budget is around $1500-2000. Any recommendations?",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=product_inquiry
        )
        assert response.status_code == 200

        # Step 2: AI provides product recommendations
        ai_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert ai_response.status_code == 200
        response_data = ai_response.json()

        # Should provide relevant recommendations
        assert "laptop" in response_data["content"].lower()
        assert "recommend" in response_data["content"].lower()

        # Step 3: Customer asks for product comparison
        comparison_request = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Can you compare the top 2 options you mentioned? I'm particularly interested in performance for 4K video editing and battery life.",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=comparison_request
        )
        assert response.status_code == 200

        # Step 4: AI provides detailed comparison
        comparison_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert comparison_response.status_code == 200
        comparison_data = comparison_response.json()

        # Should include comparison details
        assert "comparison" in comparison_data["content"].lower() or "compare" in comparison_data["content"].lower()
        assert "4k" in comparison_data["content"].lower() or "battery" in comparison_data["content"].lower()

        # Step 5: Customer makes purchase decision
        purchase_decision = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Thanks for the detailed comparison! I think I'll go with the first option. Can you help me place the order?",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=purchase_decision
        )
        assert response.status_code == 200

        # Step 6: Verify conversation was productive
        productivity_score = e2e_client.post(
            "/api/v1/intelligence/quality/assess",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": product_inquiry["message"]["content"]},
                    {"role": "assistant", "content": response_data["content"]},
                    {"role": "customer", "content": comparison_request["message"]["content"]},
                    {"role": "assistant", "content": comparison_data["content"]},
                    {"role": "customer", "content": purchase_decision["message"]["content"]}
                ],
                "agent_id": "ai_assistant",
                "customer_id": customer_id
            }
        )

        assert productivity_score.status_code == 200
        productivity_data = productivity_score.json()

        # Should show high quality for successful product recommendation
        assert productivity_data["numeric_score"] >= 8.0
        assert any("product" in str(strength).lower() for strength in productivity_data["strengths"])

    def test_multiple_language_support_flow(
        self,
        e2e_client,
        mock_external_apis,
        mock_current_user
    ):
        """Test conversation flow with multiple language support."""
        conversation_id = "e2e_lang_001"
        customer_id = "cust_e2e_003"

        # Step 1: Spanish inquiry
        spanish_inquiry = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Hola, necesito ayuda con mi pedido. No ha llegado todavía.",
                "language": "es",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=spanish_inquiry
        )
        assert response.status_code == 200

        # Step 2: AI responds in Spanish
        ai_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert ai_response.status_code == 200
        response_data = ai_response.json()

        # Should detect language and respond appropriately
        # Note: In a real implementation, this would involve translation services

        # Step 3: Customer switches to English
        language_switch = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Actually, let me switch to English. My order ORD-67890 hasn't arrived yet. Can you help me track it?",
                "language": "en",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post(
            "/api/v1/conversations/messages",
            json=language_switch
        )
        assert response.status_code == 200

        # Step 4: AI continues in English
        english_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert english_response.status_code == 200
        english_data = english_response.json()

        # Should adapt to language change
        assert "order" in english_data["content"].lower()
        assert "track" in english_data["content"].lower()

        # Step 5: Verify quality assessment considers language handling
        language_quality = e2e_client.post(
            "/api/v1/intelligence/quality/assess",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": spanish_inquiry["message"]["content"], "language": "es"},
                    {"role": "assistant", "content": response_data["content"]},
                    {"role": "customer", "content": language_switch["message"]["content"], "language": "en"},
                    {"role": "assistant", "content": english_data["content"]}
                ],
                "agent_id": "ai_assistant",
                "customer_id": customer_id,
                "context": {"language_switch": True, "initial_language": "es"}
            }
        )

        assert language_quality.status_code == 200
        quality_data = language_quality.json()

        # Should handle language switching well
        assert quality_data["numeric_score"] >= 7.0

    def test_high_volume_stress_scenario(
        self,
        e2e_client,
        mock_external_apis,
        mock_current_user
    ):
        """Test system behavior under high volume of concurrent conversations."""
        concurrent_conversations = 10
        conversation_ids = [f"stress_conv_{i:03d}" for i in range(concurrent_conversations)]

        # Create multiple concurrent conversations
        conversation_data = []
        for i, conv_id in enumerate(conversation_ids):
            message = {
                "conversation_id": conv_id,
                "message": {
                    "content": f"I need help with issue number {i}. This is urgent!",
                    "customer_id": f"cust_stress_{i:03d}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            conversation_data.append(message)

        # Submit all conversations concurrently
        responses = []
        for conv_data in conversation_data:
            response = e2e_client.post("/api/v1/conversations/messages", json=conv_data)
            responses.append(response)

        # Verify all conversations were accepted
        successful_responses = [r for r in responses if r.status_code == 200]
        assert len(successful_responses) >= concurrent_conversations * 0.9  # Allow 10% failure rate

        # Process AI responses for all conversations
        ai_responses = []
        for conv_id in conversation_ids:
            try:
                ai_response = e2e_client.get(f"/api/v1/conversations/{conv_id}/ai-response")
                if ai_response.status_code == 200:
                    ai_responses.append(ai_response.json())
            except:
                continue  # Some might fail under stress

        # Verify majority of conversations got AI responses
        assert len(ai_responses) >= concurrent_conversations * 0.8

        # End all conversations
        end_responses = []
        for conv_id in conversation_ids:
            try:
                end_response = e2e_client.post(
                    "/api/v1/conversations/end",
                    json={
                        "conversation_id": conv_id,
                        "status": "resolved",
                        "agent_id": "ai_assistant"
                    }
                )
                end_responses.append(end_response)
            except:
                continue

        successful_ends = [r for r in end_responses if r.status_code == 200]
        assert len(successful_ends) >= concurrent_conversations * 0.8

    def test_error_recovery_and_resilience(
        self,
        e2e_client,
        mock_current_user
    ):
        """Test system resilience and error recovery."""
        conversation_id = "e2e_error_001"
        customer_id = "cust_e2e_error"

        # Step 1: Normal conversation start
        normal_message = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Hi, I need help with my account.",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post("/api/v1/conversations/messages", json=normal_message)
        assert response.status_code == 200

        # Step 2: Simulate LLM API failure
        with patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate') as mock_chat:
            mock_chat.side_effect = Exception("API temporarily unavailable")

            # System should handle failure gracefully
            ai_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")

            # Should provide fallback response
            assert ai_response.status_code == 200
            response_data = ai_response.json()
            assert "content" in response_data

        # Step 3: Recovery - API works again
        recovery_message = {
            "conversation_id": conversation_id,
            "message": {
                "content": "Is anyone there? I still need help.",
                "customer_id": customer_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        }

        response = e2e_client.post("/api/v1/conversations/messages", json=recovery_message)
        assert response.status_code == 200

        # System should have recovered and provide normal response
        ai_response = e2e_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        assert ai_response.status_code == 200
        response_data = ai_response.json()
        assert len(response_data["content"]) > 10  # Normal length response

        # Step 4: Verify conversation quality despite errors
        quality_assessment = e2e_client.post(
            "/api/v1/intelligence/quality/assess",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": normal_message["message"]["content"]},
                    {"role": "assistant", "content": "I'm here to help with your account."},
                    {"role": "customer", "content": recovery_message["message"]["content"]},
                    {"role": "assistant", "content": response_data["content"]}
                ],
                "agent_id": "ai_assistant",
                "customer_id": customer_id
            }
        )

        assert quality_assessment.status_code == 200
        quality_data = quality_assessment.json()

        # Should maintain reasonable quality despite errors
        assert quality_data["numeric_score"] >= 5.0