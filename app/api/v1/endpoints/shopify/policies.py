"""
Shopify policy API endpoints.

These endpoints provide access to shop policies including refund, shipping,
privacy, terms of service, and other legal policies.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from loguru import logger

from app.integrations.shopify.service import ShopifyService
from app.integrations.shopify.models import (
    ShopPolicies, ShopPolicy, PolicyQuery, PolicyResponse, PolicySummary
)
from app.core.dependencies import get_shopify_service


router = APIRouter()


@router.get("/policies", response_model=ShopPolicies)
async def get_all_policies(
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get all shop policies.

    Returns all configured policies for the shop including refund policy,
    shipping policy, privacy policy, terms of service, etc.
    """
    try:
        logger.info("Getting all shop policies via API")
        policies = await shopify_service.get_all_policies()
        return policies
    except Exception as e:
        logger.error(f"Error getting all policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/{policy_type}", response_model=Optional[Dict[str, Any]])
async def get_policy(
    policy_type: str,
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a specific policy by type.

    Valid policy types:
    - privacy: Privacy policy
    - refund: Refund policy
    - shipping: Shipping policy
    - terms: Terms of service
    - subscription: Subscription policy
    - legal: Legal notice
    """
    try:
        logger.info(f"Getting policy: {policy_type}")
        policy = await shopify_service.get_policy(policy_type)

        if not policy:
            raise HTTPException(
                status_code=404,
                detail=f"Policy not found: {policy_type}"
            )

        return {
            "id": policy.id,
            "title": policy.title,
            "body": policy.body,
            "url": policy.url,
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
            "is_active": policy.is_active,
            "policy_type": policy_type
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting policy {policy_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/{policy_type}/summary", response_model=Optional[PolicySummary])
async def get_policy_summary(
    policy_type: str,
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a summary of a specific policy.

    Returns key points and important information from the policy.
    """
    try:
        logger.info(f"Getting policy summary: {policy_type}")
        summary = await shopify_service.get_policy_summary(policy_type)

        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"Policy not found: {policy_type}"
            )

        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting policy summary {policy_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/summaries", response_model=Dict[str, PolicySummary])
async def get_all_policy_summaries(
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get summaries of all available policies.

    Returns a dictionary with policy types as keys and summaries as values.
    """
    try:
        logger.info("Getting all policy summaries via API")
        summaries = await shopify_service.get_all_policy_summaries()
        return summaries
    except Exception as e:
        logger.error(f"Error getting all policy summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/policies/search", response_model=List[PolicyResponse])
async def search_policies(
    query: PolicyQuery,
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Search policies based on a query.

    Allows searching for specific policy information with context.
    Can answer specific questions about policies.
    """
    try:
        logger.info(f"Searching policies for query: {query.query_type}")
        responses = await shopify_service.search_policies(query)
        return responses
    except Exception as e:
        logger.error(f"Error searching policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/refund/details", response_model=Optional[Dict[str, Any]])
async def get_refund_policy_details(
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get detailed refund policy information.

    Returns enhanced refund policy details including extracted conditions
    and timeframes where available.
    """
    try:
        logger.info("Getting refund policy details")
        policy = await shopify_service.get_refund_policy_details()

        if not policy:
            raise HTTPException(
                status_code=404,
                detail="Refund policy not found"
            )

        return {
            "id": policy.id,
            "title": policy.title,
            "body": policy.body,
            "url": policy.url,
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
            "refund_window_days": policy.refund_window_days,
            "conditions_for_refund": policy.conditions_for_refund,
            "is_active": policy.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting refund policy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/shipping/details", response_model=Optional[Dict[str, Any]])
async def get_shipping_policy_details(
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get detailed shipping policy information.

    Returns enhanced shipping policy details including extracted shipping
    methods and delivery timeframes where available.
    """
    try:
        logger.info("Getting shipping policy details")
        policy = await shopify_service.get_shipping_policy_details()

        if not policy:
            raise HTTPException(
                status_code=404,
                detail="Shipping policy not found"
            )

        return {
            "id": policy.id,
            "title": policy.title,
            "body": policy.body,
            "url": policy.url,
            "created_at": policy.created_at,
            "updated_at": policy.updated_at,
            "shipping_methods": policy.shipping_methods,
            "delivery_timeframes": policy.delivery_timeframes,
            "is_active": policy.is_active
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting shipping policy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/available", response_model=Dict[str, Any])
async def get_available_policies(
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get a list of available policy types.

    Returns which policies are configured and active in the shop.
    """
    try:
        logger.info("Getting available policy types")
        policies = await shopify_service.get_all_policies()

        available_policies = {}
        for policy_name, policy in policies.active_policies.items():
            available_policies[policy_name] = {
                "title": policy.title,
                "last_updated": policy.updated_at,
                "has_url": bool(policy.url)
            }

        return {
            "total_policies": policies.policy_count,
            "available_policies": available_policies
        }
    except Exception as e:
        logger.error(f"Error getting available policies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies/faq", response_model=Dict[str, Any])
async def get_policy_faq(
    policy_type: Optional[str] = Query(None, description="Filter by policy type"),
    shopify_service: ShopifyService = Depends(get_shopify_service)
):
    """
    Get frequently asked questions and answers about policies.

    Returns common questions and their answers based on shop policies.
    """
    try:
        logger.info(f"Getting policy FAQ for: {policy_type or 'all'}")

        # This could be enhanced with AI to generate actual FAQs
        # For now, return basic FAQ structure
        faqs = {
            "refund": [
                {
                    "question": "What is your return policy?",
                    "answer": "Please refer to our refund policy for detailed return information."
                },
                {
                    "question": "How long do I have to return an item?",
                    "answer": "Return periods are specified in our refund policy."
                }
            ],
            "shipping": [
                {
                    "question": "What shipping methods do you offer?",
                    "answer": "Shipping methods are detailed in our shipping policy."
                },
                {
                    "question": "How long will delivery take?",
                    "answer": "Delivery timeframes are specified in our shipping policy."
                }
            ],
            "privacy": [
                {
                    "question": "How do you protect my personal information?",
                    "answer": "Our privacy policy explains how we handle your data."
                }
            ]
        }

        if policy_type and policy_type in faqs:
            return {"policy_type": policy_type, "faqs": faqs[policy_type]}
        else:
            return {"faqs": faqs}

    except Exception as e:
        logger.error(f"Error getting policy FAQ: {e}")
        raise HTTPException(status_code=500, detail=str(e))