"""
Policy service for AI-powered policy analysis and response generation.

This service integrates with the Shopify policy system and AI services
to provide intelligent policy responses to customer inquiries.
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.services.llm import LLMService
from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import (
    PolicyQuery, PolicyResponse, ShopPolicy, ShopPolicies
)
from app.utils.exceptions import LLMError, ExternalServiceError


class PolicyService:
    """Service for AI-powered policy analysis and response generation."""

    def __init__(self):
        self.llm_service = LLMService()
        self.shopify_service = None  # Will be injected

        # Policy analysis prompts
        self.policy_prompts = self._load_policy_prompts()

        # Policy type mapping
        self.policy_keywords = self._load_policy_keywords()

    def _load_policy_prompts(self) -> Dict[str, str]:
        """Load policy analysis prompt templates."""
        return {
            "policy_classification": """You are an AI assistant that classifies user questions about shop policies.

Given a user's question, determine which policy type it relates to and extract the key information.

Policy types:
- refund: Returns, refunds, exchanges, money back
- shipping: Delivery, shipping methods, timeframes, tracking
- privacy: Data protection, personal information, cookies
- terms: Terms of service, legal terms, user agreement
- subscription: Subscriptions, recurring payments, cancellations
- legal: Legal notices, disclaimers, liability

User question: "{question}"

Return your analysis as JSON:
{{
    "policy_type": "policy_name",
    "confidence": 0.85,
    "extracted_entities": {{
        "time_period": "30 days",
        "condition": "unopened items",
        "specific_topic": "return shipping cost"
    }},
    "reasoning": "Brief explanation"
}}""",

            "policy_answer": """You are a helpful customer service assistant that answers questions based on shop policies.

Policy Type: {policy_type}
Policy Content:
{policy_content}

Customer Question: "{question}"

Additional Context:
- Customer context: {customer_context}
- Order context: {order_context}
- Product context: {product_context}

Using ONLY the provided policy content, answer the customer's question. If the policy doesn't contain the answer, say so politely and suggest what information would be needed.

Provide your response as JSON:
{{
    "answer": "Your detailed answer based on the policy",
    "relevant_sections": ["Direct quotes from policy that support your answer"],
    "confidence": 0.9,
    "additional_info_needed": ["Any additional information required"],
    "action_items": ["Next steps for the customer"]
}}""",

            "policy_summary": """Summarize the following policy into key points that customers need to know:

Policy Title: {title}
Policy Content: {content}

Create a concise summary with 3-5 main points that customers should understand.

Return as JSON:
{{
    "summary_points": ["Key point 1", "Key point 2", "Key point 3"],
    "important_dates": ["Any important deadlines or timeframes"],
    "contact_info": ["Relevant contact information if mentioned"],
    "key_restrictions": ["Main limitations or conditions"]
}}"""
        }

    def _load_policy_keywords(self) -> Dict[str, List[str]]:
        """Load keyword mappings for policy classification."""
        return {
            "refund": [
                "return", "refund", "exchange", "money back", "refund policy",
                "return policy", "30 days", "cancel order", "get my money back"
            ],
            "shipping": [
                "shipping", "delivery", "track", "tracking", "shipping cost",
                "delivery time", "how long", "when will", "shipping method",
                "free shipping", "express delivery"
            ],
            "privacy": [
                "privacy", "personal data", "data protection", "information",
                "cookies", "third party", "share data", " GDPR", "privacy policy"
            ],
            "terms": [
                "terms", "conditions", "terms of service", "legal terms",
                "user agreement", "acceptable use", "prohibited", "responsibility"
            ],
            "subscription": [
                "subscription", "recurring", "monthly", "cancel subscription",
                "billing", "auto-renew", "membership"
            ],
            "legal": [
                "legal", "disclaimer", "liability", "law", "legal notice",
                "copyright", "trademark", "jurisdiction"
            ]
        }

    async def classify_policy_question(self, question: str) -> Dict[str, Any]:
        """Classify a user's question to determine policy type."""
        try:
            logger.info(f"Classifying policy question: {question[:100]}...")

            # First, try keyword-based classification
            keyword_result = self._classify_by_keywords(question)

            # Use LLM for more accurate classification
            prompt = self.policy_prompts["policy_classification"].format(
                question=question
            )

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=500,
                temperature=0.1
            )

            try:
                llm_result = json.loads(response)
                # Combine both results
                final_result = {
                    "policy_type": llm_result.get("policy_type", keyword_result["policy_type"]),
                    "confidence": max(
                        llm_result.get("confidence", 0.5),
                        keyword_result["confidence"]
                    ),
                    "extracted_entities": llm_result.get("extracted_entities", {}),
                    "reasoning": llm_result.get("reasoning", ""),
                    "keyword_match": keyword_result
                }
                return final_result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response, using keyword classification")
                return keyword_result

        except Exception as e:
            logger.error(f"Error classifying policy question: {e}")
            return self._classify_by_keywords(question)

    def _classify_by_keywords(self, question: str) -> Dict[str, Any]:
        """Classify question using keyword matching."""
        question_lower = question.lower()

        best_match = {"policy_type": "refund", "confidence": 0.1}

        for policy_type, keywords in self.policy_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in question_lower)
            confidence = min(matches / len(keywords), 1.0)

            if confidence > best_match["confidence"]:
                best_match = {
                    "policy_type": policy_type,
                    "confidence": confidence
                }

        return best_match

    async def answer_policy_question(
        self,
        question: str,
        policy_type: Optional[str] = None,
        customer_context: Optional[Dict[str, Any]] = None,
        order_context: Optional[Dict[str, Any]] = None,
        product_context: Optional[Dict[str, Any]] = None
    ) -> PolicyResponse:
        """Answer a policy question using AI analysis."""
        try:
            logger.info(f"Answering policy question: {question[:100]}...")

            # Classify the question if policy_type not provided
            if not policy_type:
                classification = await self.classify_policy_question(question)
                policy_type = classification.get("policy_type", "refund")

            # Get the relevant policy
            if not self.shopify_service:
                raise ExternalServiceError("Shopify service not available")

            policy = await self.shopify_service.get_policy(policy_type)
            if not policy:
                return PolicyResponse(
                    policy_type=policy_type,
                    policy_content="",
                    answer_to_question=f"I don't have access to the {policy_type} policy. Please contact customer service for assistance.",
                    confidence_score=0.1,
                    relevant_sections=[]
                )

            # Use AI to answer the question
            prompt = self.policy_prompts["policy_answer"].format(
                policy_type=policy_type,
                policy_content=policy.content[:4000],  # Limit content length
                question=question,
                customer_context=json.dumps(customer_context or {}),
                order_context=json.dumps(order_context or {}),
                product_context=json.dumps(product_context or {})
            )

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )

            try:
                ai_result = json.loads(response)
                return PolicyResponse(
                    policy_type=policy_type,
                    policy_content=policy.content,
                    answer_to_question=ai_result.get("answer"),
                    relevant_sections=ai_result.get("relevant_sections", []),
                    confidence_score=ai_result.get("confidence", 0.7),
                    additional_info={
                        "policy_url": policy.url,
                        "last_updated": policy.updated_at.isoformat() if policy.updated_at else None,
                        "customer_context": customer_context,
                        "order_context": order_context,
                        "product_context": product_context,
                        "action_items": ai_result.get("action_items", []),
                        "additional_info_needed": ai_result.get("additional_info_needed", [])
                    }
                )
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AI response, returning policy content")
                return PolicyResponse(
                    policy_type=policy_type,
                    policy_content=policy.content,
                    answer_to_question=f"Based on our {policy.title}, here's the relevant information: {policy.content[:500]}...",
                    confidence_score=0.5,
                    relevant_sections=[policy.content[:200] + "..."]
                )

        except Exception as e:
            logger.error(f"Error answering policy question: {e}")
            raise LLMError(f"Failed to answer policy question: {str(e)}")

    async def generate_policy_summary(self, policy: ShopPolicy) -> Dict[str, Any]:
        """Generate an AI-powered summary of a policy."""
        try:
            logger.info(f"Generating summary for policy: {policy.title}")

            prompt = self.policy_prompts["policy_summary"].format(
                title=policy.title,
                content=policy.content[:3000]  # Limit content length
            )

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=500,
                temperature=0.2
            )

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse summary response")
                return {
                    "summary_points": ["Policy summary generation failed"],
                    "important_dates": [],
                    "contact_info": [],
                    "key_restrictions": []
                }

        except Exception as e:
            logger.error(f"Error generating policy summary: {e}")
            return {
                "summary_points": ["Error generating summary"],
                "important_dates": [],
                "contact_info": [],
                "key_restrictions": []
            }

    async def analyze_policy_compliance(self, policy_content: str, jurisdiction: str = "US") -> Dict[str, Any]:
        """Analyze policy for compliance with common regulations."""
        try:
            logger.info(f"Analyzing policy compliance for jurisdiction: {jurisdiction}")

            compliance_prompt = f"""Analyze the following policy for compliance with common {jurisdiction} regulations:

Policy Content:
{policy_content[:2000]}

Check for:
- Clear refund/return policy
- Data privacy protections
- Terms of service clarity
- Consumer rights information
- Contact information availability

Return compliance analysis as JSON:
{{
    "compliance_score": 0.8,
    "issues_found": ["Issue 1", "Issue 2"],
    "recommendations": ["Recommendation 1", "Recommendation 2"],
    "missing_elements": ["Missing element 1"],
    "jurisdiction_notes": "Specific notes for {jurisdiction}"
}}"""

            response = await self.llm_service.generate_response(
                prompt=compliance_prompt,
                max_tokens=800,
                temperature=0.1
            )

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse compliance analysis")
                return {
                    "compliance_score": 0.5,
                    "issues_found": ["Analysis failed"],
                    "recommendations": ["Manual review recommended"],
                    "missing_elements": [],
                    "jurisdiction_notes": f"Analysis for {jurisdiction} failed"
                }

        except Exception as e:
            logger.error(f"Error analyzing policy compliance: {e}")
            return {
                "compliance_score": 0.0,
                "issues_found": ["Analysis failed"],
                "recommendations": ["Manual review required"],
                "missing_elements": [],
                "jurisdiction_notes": f"Error analyzing {jurisdiction} compliance"
            }

    def set_shopify_service(self, shopify_service: ShopifyService):
        """Set the Shopify service instance."""
        self.shopify_service = shopify_service