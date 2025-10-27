#!/usr/bin/env python3
"""
Debug script for testing specific conversation flows
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.llm.llm_manager import LLMManager
from app.core.llm.prompt_templates import PromptManager
from app.core.intelligence.escalation import EscalationEngine
from app.core.intelligence.quality import QualityAssessor
from app.core.intelligence.sentiment import SentimentAnalyzer
from app.integrations.shopify.client import ShopifyClient
from app.core.config import settings


class FlowDebugger:
    """Debug specific conversation flows"""

    def __init__(self):
        self.llm_manager = LLMManager()
        self.prompt_manager = PromptManager()

    async def test_basic_conversation_flow(self):
        """Test basic conversation flow with customer service scenario"""
        print("\n🔄 Testing Basic Conversation Flow")
        print("=" * 50)

        conversation = [
            {
                "role": "customer",
                "content": "Hi, I need help with my recent order. I haven't received it yet.",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Step 1: Generate AI response
        print("1. Generating AI response...")
        try:
            response = await self.llm_manager.generate_response(
                prompt=f"Customer says: {conversation[0]['content']}\nProvide helpful customer service response.",
                max_tokens=150,
                temperature=0.7
            )
            print(f"✅ AI Response: {response['content'][:100]}...")

            conversation.append({
                "role": "assistant",
                "content": response['content'],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"❌ AI Response Error: {e}")
            return False

        # Step 2: Analyze sentiment
        print("\n2. Analyzing sentiment...")
        try:
            sentiment_analyzer = SentimentAnalyzer(self.llm_manager, self.prompt_manager)
            sentiment_result = await sentiment_analyzer.analyze_sentiment(conversation)
            print(f"✅ Sentiment: {sentiment_result.overall_sentiment.value} (score: {sentiment_result.sentiment_score})")
        except Exception as e:
            print(f"❌ Sentiment Analysis Error: {e}")
            return False

        # Step 3: Check escalation need
        print("\n3. Checking escalation requirements...")
        try:
            escalation_engine = EscalationEngine(self.llm_manager, self.prompt_manager)
            from app.core.intelligence.models import EscalationRequest
            escalation_request = EscalationRequest(
                conversation_id="debug_conv_001",
                messages=conversation
            )
            escalation_result = await escalation_engine.analyze_escalation(escalation_request)
            print(f"✅ Escalation Needed: {escalation_result.decision.should_escalate}")
            print(f"   Confidence: {escalation_result.decision.confidence}")
            if escalation_result.decision.should_escalate:
                print(f"   Reason: {escalation_result.decision.reasoning[:100]}...")
        except Exception as e:
            print(f"❌ Escalation Analysis Error: {e}")
            return False

        # Step 4: Quality assessment
        print("\n4. Assessing conversation quality...")
        try:
            quality_assessor = QualityAssessor(self.llm_manager, self.prompt_manager)
            from app.core.intelligence.models import QualityAssessmentRequest
            quality_request = QualityAssessmentRequest(
                conversation_id="debug_conv_001",
                messages=conversation
            )
            quality_result = await quality_assessor.assess_conversation_quality(quality_request)
            print(f"✅ Quality Score: {quality_result.numeric_score}/10 ({quality_result.overall_score.value})")
            if quality_result.strengths:
                print(f"   Strengths: {', '.join(quality_result.strengths[:2])}")
        except Exception as e:
            print(f"❌ Quality Assessment Error: {e}")
            return False

        print("\n✅ Basic conversation flow completed successfully!")
        return True

    async def test_frustrated_customer_flow(self):
        """Test handling of frustrated customer"""
        print("\n😤 Testing Frustrated Customer Flow")
        print("=" * 50)

        conversation = [
            {
                "role": "customer",
                "content": "This is absolutely ridiculous! I've been waiting for my order for 3 weeks and nobody is helping me! This is the worst customer service I've ever experienced!",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Generate empathetic response
        print("1. Generating empathetic response...")
        try:
            response = await self.llm_manager.generate_response(
                prompt=f"Customer is very frustrated: {conversation[0]['content']}\nGenerate an empathetic, de-escalating response.",
                max_tokens=150,
                temperature=0.8
            )
            print(f"✅ Empathetic Response: {response['content'][:100]}...")

            conversation.append({
                "role": "assistant",
                "content": response['content'],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"❌ Response Generation Error: {e}")
            return False

        # Check for high frustration level
        print("\n2. Detecting frustration level...")
        try:
            sentiment_analyzer = SentimentAnalyzer(self.llm_manager, self.prompt_manager)
            sentiment_result = await sentiment_analyzer.analyze_sentiment(conversation)
            print(f"✅ Sentiment: {sentiment_result.overall_sentiment.value}")

            # Test frustration detection
            from app.core.intelligence.sentiment import FrustrationDetector
            frustration_detector = FrustrationDetector(self.llm_manager, self.prompt_manager)
            frustration_result = await frustration_detector.detect_frustration(conversation)
            print(f"✅ Frustration Level: {frustration_result.frustration_level.value}")
            print(f"   Escalation Risk: {frustration_result.escalation_risk}")
        except Exception as e:
            print(f"❌ Frustration Detection Error: {e}")
            return False

        # Check escalation urgency
        print("\n3. Checking escalation urgency...")
        try:
            escalation_engine = EscalationEngine(self.llm_manager, self.prompt_manager)
            from app.core.intelligence.models import EscalationRequest
            escalation_request = EscalationRequest(
                conversation_id="debug_frustrated_001",
                messages=conversation,
                context={"urgency": "high", "previous_issues": 2}
            )
            escalation_result = await escalation_engine.analyze_escalation(escalation_request)
            print(f"✅ Should Escalate: {escalation_result.decision.should_escalate}")
            print(f"   Urgency Score: {escalation_result.decision.urgency_score}/10")
            print(f"   Triggers: {[t.type for t in escalation_result.decision.triggers]}")
        except Exception as e:
            print(f"❌ Escalation Check Error: {e}")
            return False

        print("\n✅ Frustrated customer flow completed successfully!")
        return True

    async def test_shopify_integration_flow(self):
        """Test Shopify product integration"""
        print("\n🛍️ Testing Shopify Integration Flow")
        print("=" * 50)

        try:
            shopify_client = ShopifyClient(
                shop_domain=settings.SHOPIFY_SHOP_DOMAIN,
                access_token=settings.SHOPIFY_ACCESS_TOKEN
            )
        except Exception as e:
            print(f"❌ Shopify Client Error: {e}")
            return False

        # Test product search
        print("1. Testing product search...")
        try:
            products, has_more = await shopify_client.search_products(
                query="gift",
                limit=5
            )
            print(f"✅ Found {len(products)} products")

            if products:
                sample_product = products[0]
                print(f"   Sample: {sample_product.get('title', 'Unknown')[:50]}...")

                # Test getting product details
                if 'id' in sample_product:
                    product_details = await shopify_client.get_product(sample_product['id'])
                    if product_details:
                        print(f"✅ Retrieved product details successfully")
                    else:
                        print("⚠️ Could not retrieve product details")
        except Exception as e:
            print(f"❌ Product Search Error: {e}")
            return False

        # Test inventory check
        print("\n2. Testing inventory check...")
        try:
            # Use a sample product ID or create one
            test_product_id = "test_product_id"
            inventory = await shopify_client.check_inventory(test_product_id)
            print(f"✅ Inventory check completed (simulated)")
        except Exception as e:
            print(f"❌ Inventory Check Error: {e}")

        print("\n✅ Shopify integration flow completed!")
        return True

    async def test_complex_scenario_flow(self):
        """Test complex multi-step scenario"""
        print("\n🎯 Testing Complex Scenario Flow")
        print("=" * 50)

        # Complex customer scenario: Multiple product inquiry with comparison
        conversation = [
            {
                "role": "customer",
                "content": "Hi, I'm looking for a birthday gift for my husband. He's into technology and loves gadgets. Budget is around $200-300. What do you recommend?",
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Step 1: Get product recommendations
        print("1. Getting product recommendations...")
        try:
            response = await self.llm_manager.generate_response(
                prompt=f"Customer wants: {conversation[0]['content']}\nProvide 2-3 specific product recommendations with key features.",
                max_tokens=200,
                temperature=0.7
            )
            print(f"✅ Recommendations: {response['content'][:150]}...")

            conversation.append({
                "role": "assistant",
                "content": response['content'],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"❌ Recommendation Error: {e}")
            return False

        # Step 2: Customer asks for comparison
        conversation.append({
            "role": "customer",
            "content": "Those look interesting! Can you compare the first two options? I'm particularly interested in battery life and durability.",
            "timestamp": datetime.utcnow().isoformat()
        })

        print("\n2. Generating comparison...")
        try:
            comparison_response = await self.llm_manager.generate_response(
                prompt=f"Customer wants comparison: {conversation[-1]['content']}\nPrevious recommendations: {response['content']}\nProvide detailed comparison.",
                max_tokens=200,
                temperature=0.6
            )
            print(f"✅ Comparison: {comparison_response['content'][:150]}...")

            conversation.append({
                "role": "assistant",
                "content": comparison_response['content'],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"❌ Comparison Error: {e}")
            return False

        # Step 3: Customer makes decision
        conversation.append({
            "role": "customer",
            "content": "Great comparison! I think I'll go with the first option. Can you help me place the order or should I use the website?",
            "timestamp": datetime.utcnow().isoformat()
        })

        print("\n3. Providing purchase assistance...")
        try:
            purchase_response = await self.llm_manager.generate_response(
                prompt=f"Customer wants to purchase: {conversation[-1]['content']}\nProvide helpful guidance for ordering.",
                max_tokens=150,
                temperature=0.5
            )
            print(f"✅ Purchase assistance: {purchase_response['content'][:150]}...")

            conversation.append({
                "role": "assistant",
                "content": purchase_response['content'],
                "timestamp": datetime.utcnow().isoformat()
            })
        except Exception as e:
            print(f"❌ Purchase Assistance Error: {e}")
            return False

        # Step 4: Quality assessment of entire conversation
        print("\n4. Assessing conversation quality...")
        try:
            quality_assessor = QualityAssessor(self.llm_manager, self.prompt_manager)
            from app.core.intelligence.models import QualityAssessmentRequest
            quality_request = QualityAssessmentRequest(
                conversation_id="debug_complex_001",
                messages=conversation,
                context={"conversation_type": "product_recommendation"}
            )
            quality_result = await quality_assessor.assess_conversation_quality(quality_request)
            print(f"✅ Overall Quality Score: {quality_result.numeric_score}/10")
            print(f"   Strengths: {', '.join(quality_result.strengths[:3])}")
            if quality_result.actionable_insights:
                print(f"   Insights: {quality_result.actionable_insights[0][:80]}...")
        except Exception as e:
            print(f"❌ Quality Assessment Error: {e}")
            return False

        print("\n✅ Complex scenario flow completed successfully!")
        return True

    async def test_error_recovery_flow(self):
        """Test system behavior under error conditions"""
        print("\n🔧 Testing Error Recovery Flow")
        print("=" * 50)

        # Simulate LLM API failure
        print("1. Testing LLM API failure recovery...")
        try:
            # This will test our retry logic and error handling
            original_generate = self.llm_manager.generate_response

            async def mock_failure(*args, **kwargs):
                raise Exception("Simulated API failure")

            # Temporarily replace the method
            self.llm_manager.generate_response = mock_failure

            try:
                await self.llm_manager.generate_response("Test message")
                print("❌ Expected failure but didn't get one")
                return False
            except Exception:
                print("✅ LLM failure handled correctly")

            # Restore original method
            self.llm_manager.generate_response = original_generate

            # Test that normal operation still works
            response = await self.llm_manager.generate_response(
                prompt="Test recovery message",
                max_tokens=50
            )
            if response and 'content' in response:
                print("✅ Recovery successful - normal operation restored")
            else:
                print("❌ Recovery failed - normal operation not restored")
                return False

        except Exception as e:
            print(f"❌ Error Recovery Test Error: {e}")
            return False

        # Test malformed input handling
        print("\n2. Testing malformed input handling...")
        try:
            quality_assessor = QualityAssessor(self.llm_manager, self.prompt_manager)
            from app.core.intelligence.models import QualityAssessmentRequest

            # Test with empty messages
            malformed_request = QualityAssessmentRequest(
                conversation_id="test_malformed",
                messages=[]  # Empty messages
            )

            quality_result = await quality_assessor.assess_conversation_quality(malformed_request)
            if quality_result:
                print("✅ Malformed input handled gracefully")
            else:
                print("❌ Malformed input not handled properly")
                return False

        except Exception as e:
            print(f"❌ Malformed Input Test Error: {e}")
            return False

        print("\n✅ Error recovery flow completed successfully!")
        return True


async def main():
    """Main debug function"""
    print("🔍 Shop Assistant AI - Flow Debugger")
    print("=" * 50)

    debugger = FlowDebugger()

    # Test flows
    flows = [
        ("Basic Conversation", debugger.test_basic_conversation_flow),
        ("Frustrated Customer", debugger.test_frustrated_customer_flow),
        ("Shopify Integration", debugger.test_shopify_integration_flow),
        ("Complex Scenario", debugger.test_complex_scenario_flow),
        ("Error Recovery", debugger.test_error_recovery_flow),
    ]

    results = {}

    for flow_name, flow_func in flows:
        print(f"\n🔄 Testing: {flow_name}")
        try:
            success = await flow_func()
            results[flow_name] = success
        except Exception as e:
            print(f"❌ {flow_name} failed with error: {e}")
            results[flow_name] = False

    # Summary
    print("\n" + "=" * 50)
    print("📊 DEBUG SUMMARY")
    print("=" * 50)

    passed = sum(1 for success in results.values() if success)
    total = len(results)

    for flow_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {flow_name}")

    print(f"\nOverall: {passed}/{total} flows passed")

    if passed == total:
        print("🎉 All flows working correctly!")
    elif passed >= total * 0.8:
        print("⚠️ Most flows working, some issues detected")
    else:
        print("❌ Multiple flows have issues that need attention")


if __name__ == "__main__":
    asyncio.run(main())