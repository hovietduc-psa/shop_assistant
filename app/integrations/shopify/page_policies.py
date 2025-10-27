"""
Page-based policy integration for Shopify stores that use pages for policies.
"""

import re
from typing import Dict, List, Any, Optional
from loguru import logger

from app.integrations.shopify.models import (
    ShopPolicy, RefundPolicy, ShippingPolicy, PrivacyPolicy,
    TermsOfService, ShopPolicies, PolicyQuery, PolicyResponse
)


class PagePolicyService:
    """Service for handling policies stored as Shopify pages."""

    def __init__(self, shopify_service):
        """Initialize with Shopify service instance."""
        self.shopify_service = shopify_service

        # Policy page mapping - maps policy types to page search patterns
        self.policy_patterns = {
            "refund": [
                r"refund",
                r"return",
                r"cancellation",
                r"money back",
                r"satisfaction"
            ],
            "shipping": [
                r"shipping",
                r"delivery",
                r"tracking",
                r"dispatch",
                r"transit"
            ],
            "privacy": [
                r"privacy",
                r"personal data",
                r"ccpa",
                r"gdpr",
                r"data protection"
            ],
            "terms": [
                r"terms",
                r"conditions",
                r"agreement",
                r"legal",
                r"disclaimer"
            ]
        }

    async def get_policies_from_pages(self) -> ShopPolicies:
        """Get policies by analyzing Shopify pages."""
        try:
            logger.info("Getting policies from Shopify pages")

            # Get all pages from Shopify
            pages = await self.shopify_service.get_pages()
            if not pages:
                logger.warning("No pages found in Shopify store")
                return ShopPolicies()

            # Analyze pages to find policy content
            policies = self._analyze_pages_for_policies(pages)
            return policies

        except Exception as e:
            logger.error(f"Error getting policies from pages: {e}")
            return ShopPolicies()

    def _analyze_pages_for_policies(self, pages: List[Dict[str, Any]]) -> ShopPolicies:
        """Analyze pages to extract policy information."""
        policies = ShopPolicies()

        for page in pages:
            title = page.get('title', '').lower()
            handle = page.get('handle', '').lower()
            content = page.get('body_html', '')
            content_text = self._html_to_text(content)

            # Skip empty pages
            if not title or not content_text.strip():
                continue

            # Try to match each policy type
            for policy_type, patterns in self.policy_patterns.items():
                if self._matches_policy_pattern(title, handle, content_text, patterns):
                    policy_obj = self._create_policy_from_page(page, policy_type, content_text)
                    if policy_obj:
                        self._set_policy(policies, policy_type, policy_obj)
                        logger.info(f"Found {policy_type} policy: {page.get('title')}")
                        break

        return policies

    def _matches_policy_pattern(self, title: str, handle: str, content: str, patterns: List[str]) -> bool:
        """Check if page matches any policy patterns."""
        for pattern in patterns:
            if (re.search(pattern, title, re.IGNORECASE) or
                re.search(pattern, handle, re.IGNORECASE) or
                re.search(pattern, content[:1000], re.IGNORECASE)):  # Check first 1000 chars
                return True
        return False

    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text."""
        if not html_content:
            return ""

        # Simple HTML tag removal
        text = re.sub(r'<[^>]+>', ' ', html_content)
        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _create_policy_from_page(self, page: Dict[str, Any], policy_type: str, content_text: str) -> Optional[ShopPolicy]:
        """Create a policy object from page data."""
        try:
            # Common policy data
            base_data = {
                'id': str(page.get('id')),
                'title': page.get('title', ''),
                'body': content_text,
                'url': page.get('url', ''),
                'created_at': page.get('created_at'),
                'updated_at': page.get('updated_at')
            }

            # Create specific policy type
            if policy_type == "refund":
                return RefundPolicy(**base_data)
            elif policy_type == "shipping":
                return ShippingPolicy(**base_data)
            elif policy_type == "privacy":
                return PrivacyPolicy(**base_data)
            elif policy_type == "terms":
                return TermsOfService(**base_data)
            else:
                return ShopPolicy(**base_data)

        except Exception as e:
            logger.error(f"Error creating policy from page: {e}")
            return None

    def _set_policy(self, policies: ShopPolicies, policy_type: str, policy: ShopPolicy):
        """Set the appropriate policy type."""
        if policy_type == "refund":
            policies.refund_policy = policy
        elif policy_type == "shipping":
            policies.shipping_policy = policy
        elif policy_type == "privacy":
            policies.privacy_policy = policy
        elif policy_type == "terms":
            policies.terms_of_service = policy

    async def search_policies_in_pages(self, query: PolicyQuery) -> List[PolicyResponse]:
        """Search for policies using page content."""
        try:
            logger.info(f"Searching policies in pages: {query.query_type}")

            # Get all policies from pages
            policies = await self.get_policies_from_pages()

            # Convert to list for searching
            policy_list = []
            for policy_name, policy in policies.active_policies.items():
                policy_list.append((policy_name, policy))

            # Search based on query type
            if query.query_type == "all":
                return self._create_responses_from_policies(policy_list, query)
            else:
                # Filter by specific policy type
                filtered_policies = [
                    (name, policy) for name, policy in policy_list
                    if name == query.query_type
                ]
                return self._create_responses_from_policies(filtered_policies, query)

        except Exception as e:
            logger.error(f"Error searching policies in pages: {e}")
            return []

    def _create_responses_from_policies(self, policy_list: List[tuple], query: PolicyQuery) -> List[PolicyResponse]:
        """Create policy responses from policy list."""
        responses = []

        for policy_name, policy in policy_list:
            try:
                # Check if specific question is asked
                answer_to_question = None
                confidence_score = 0.8  # Default confidence
                relevant_sections = []

                if query.specific_question:
                    # Simple keyword matching for question answering
                    question_lower = query.specific_question.lower()
                    content_lower = policy.content.lower()

                    # Check for relevant content
                    if any(word in content_lower for word in question_lower.split() if len(word) > 3):
                        answer_to_question = f"Based on our {policy.title}, here's what I found: {policy.content[:500]}..."
                        confidence_score = 0.7
                        relevant_sections = [policy.content[:300] + "..."]

                response = PolicyResponse(
                    policy_type=policy_name,
                    policy_content=policy.content,
                    relevant_sections=relevant_sections,
                    answer_to_question=answer_to_question,
                    confidence_score=confidence_score,
                    additional_info={
                        "policy_url": policy.url,
                        "last_updated": policy.updated_at,
                        "customer_context": query.customer_context,
                        "order_context": query.order_context,
                        "product_context": query.product_context
                    }
                )
                responses.append(response)

            except Exception as e:
                logger.error(f"Error creating response for policy {policy_name}: {e}")
                continue

        return responses