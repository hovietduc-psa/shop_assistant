"""
LangGraph workflow nodes for Shop Assistant AI.
Implements the individual processing nodes in the LangGraph workflow.
"""

import time
import json
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from app.services.langgraph_state import (
    ConversationState,
    AnalysisResult,
    ToolCallState,
    create_initial_state,
    update_state_timestamp,
    create_error_state
)
from app.services.llm import LLMService
from app.services.nlu import NLUService
from app.services.tool_system.executor_streamlined import StreamlinedToolExecutor
from app.core.config import settings


class LangGraphNodes:
    """
    Collection of LangGraph workflow nodes for Shop Assistant AI.
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.nlu_service = NLUService()
        self.tool_executor = StreamlinedToolExecutor()

    async def _routing_analysis_node(self, state: ConversationState) -> ConversationState:
        """
        Quick routing analysis node for intelligent workflow decisions.

        This node performs a lightweight analysis to determine if the conversation
        requires simple or parallel processing, enabling intelligent routing.

        Args:
            state: Current conversation state

        Returns:
            Updated state with basic entities for routing decision
        """
        start_time = time.time()
        user_message = state["user_message"]

        try:
            logger.info(f"Performing routing analysis for: {user_message[:100]}...")

            # Quick entity extraction using regex only (for speed)
            quick_result = await self._extract_with_regex(user_message)

            # Update state with basic entities for routing
            updated_state = {
                **state,
                "entities": quick_result.get("entities", []) if quick_result.get("success") else [],
                "entity_extraction_method": "routing_quick",
                "routing_analysis_time": time.time() - start_time,
                "updated_at": time.time()
            }

            logger.info(f"Routing analysis completed in {time.time() - start_time:.3f}s")
            return updated_state

        except Exception as e:
            logger.error(f"Routing analysis failed: {e}")
            # Return state without entities for safety
            return {
                **state,
                "entities": [],
                "entity_extraction_method": "routing_failed",
                "routing_analysis_time": time.time() - start_time,
                "updated_at": time.time()
            }

    async def parallel_entity_extraction_node(self, state: ConversationState) -> ConversationState:
        """
        Parallel entity extraction node that runs multiple extraction methods simultaneously.

        This Phase 2 improvement runs regex patterns, LLM extraction, and pattern matching
        in parallel, then merges the results for the most comprehensive entity extraction.

        Args:
            state: Current conversation state

        Returns:
            Updated state with merged entities from all extraction methods
        """
        start_time = time.time()
        user_message = state["user_message"]

        try:
            logger.info(f"Starting parallel entity extraction for: {user_message[:100]}...")

            # Create parallel extraction tasks
            tasks = [
                self._extract_with_regex(user_message),
                self._extract_with_llm(user_message),
                self._extract_with_patterns(user_message)
            ]

            # Execute all extraction methods in parallel
            logger.info("Running parallel entity extraction tasks...")
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Merge results from all extraction methods
            merged_entities = self._merge_extraction_results(results, user_message)

            # Update state with merged entities
            updated_state = {
                **state,
                "entities": merged_entities,
                "entity_extraction_method": "parallel_merged",
                "llm_calls_count": state["llm_calls_count"] + (1 if any(not isinstance(r, Exception) and "llm" in str(r) for r in results) else 0),
                "updated_at": time.time()
            }

            logger.info(f"Parallel entity extraction completed in {time.time() - start_time:.2f}s")
            logger.info(f"Merged {len(merged_entities)} entities from {len([r for r in results if not isinstance(r, Exception)])} successful methods")

            return updated_state

        except Exception as e:
            logger.error(f"Parallel entity extraction failed: {e}")
            # Fallback to single method
            return await self._fallback_entity_extraction(state, str(e))

    async def _extract_with_regex(self, user_message: str) -> Dict[str, Any]:
        """
        Extract entities using enhanced regex patterns.
        """
        try:
            import re

            # Enhanced price patterns (Phase 1 improvement maintained)
            price_patterns = [
                r'\$\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # $50, $1,500, $50.99
                r'\d{1,5}(?:,\d{3})*(?:\.\d{2})?\s+dollars?',  # 50 dollars, 1,500 dollars
                r'(?:under|below|less than)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # under $50, under $1,500
                r'(?:over|above|more than)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # over $100, over $1,000
                r'(?:between|from)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?\s+(?:and|to|-)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # between $50 and $100
                r'(?:around|about|approximately|close to)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # around $50, about $1,000
                r'(?:exactly|just)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # exactly $50, just $1,000
                r'(?:at|for)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # at $50, for $1,000
            ]

            # Brand patterns
            brands = ["Sony", "Apple", "Samsung", "Nike", "Adidas", "LG", "Microsoft", "Dell", "HP", "Canon", "Nikon", "Asus", "Lenovo", "Razer", "Logitech"]

            # Product categories
            categories = ["headphones", "laptops", "cameras", "watches", "shoes", "shirts", "electronics", "gaming", "office", "fitness", "smartphone", "tablet"]

            # Order number patterns
            order_patterns = [
                r'\b(?:order|tracking|shipment|#)?\s*([A-Z0-9]{10,20})\b',
                r'\b\d{10,20}\b',
                r'1Z[A-Z0-9]{16,24}'
            ]

            entities = []

            # Extract prices
            for pattern in price_patterns:
                for match in re.finditer(pattern, user_message, re.IGNORECASE):
                    price_text = match.group()
                    parsed_price = self._parse_price_text(price_text)

                    entities.append({
                        "text": price_text,
                        "label": "PRICE",
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.7,
                        "normalized_value": parsed_price,
                        "extraction_method": "regex"
                    })

            # Extract brands
            for brand in brands:
                for match in re.finditer(rf'\b{brand}\b', user_message, re.IGNORECASE):
                    entities.append({
                        "text": match.group(),
                        "label": "BRAND",
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.8,
                        "extraction_method": "regex"
                    })

            # Extract categories
            for category in categories:
                for match in re.finditer(rf'\b{category}\b', user_message, re.IGNORECASE):
                    entities.append({
                        "text": match.group(),
                        "label": "CATEGORY",
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.8,
                        "extraction_method": "regex"
                    })

            # Extract order numbers
            for pattern in order_patterns:
                for match in re.finditer(pattern, user_message, re.IGNORECASE):
                    order_text = match.group(1) if match.groups() else match.group()
                    entities.append({
                        "text": order_text,
                        "label": "ORDER_NUMBER",
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.9,
                        "extraction_method": "regex"
                    })

            return {
                "success": True,
                "entities": entities,
                "method": "regex",
                "processing_time": time.time() - start_time
            }

        except Exception as e:
            logger.error(f"Regex extraction failed: {e}")
            return {"success": False, "entities": [], "method": "regex", "error": str(e)}

    async def _extract_with_llm(self, user_message: str) -> Dict[str, Any]:
        """
        Extract entities using LLM function calling.
        """
        try:
            start_time = time.time()

            messages = [
                {
                    "role": "system",
                    "content": """You are an expert AI assistant for extracting entities from e-commerce customer messages.

Extract relevant entities with high precision:
- PRODUCT: Product names, models, types (e.g., "headphones", "laptop", "iPhone")
- PRICE: Monetary amounts, prices, budgets (e.g., "$50", "under $100", "50 dollars")
- BRAND: Brand names (e.g., "Sony", "Apple", "Nike", "Samsung")
- CATEGORY: Product categories (e.g., "electronics", "clothing", "gaming")
- COLOR: Colors mentioned (e.g., "red", "black", "blue")
- SIZE: Sizes mentioned (e.g., "large", "medium", "XL")
- ORDER_NUMBER: Order identifiers (e.g., "#1001", "order 12345")
- QUANTITY: Quantities mentioned (e.g., "2", "three", "a pair")

Return JSON with entities array."""
                },
                {
                    "role": "user",
                    "content": f"Extract entities from: \"{user_message}\""
                }
            ]

            llm_response = await self.llm_service.function_calling(
                messages=messages,
                functions=[{
                    "name": "extract_entities",
                    "description": "Extract entities from text",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {"type": "string"},
                                    "label": {"type": "string"},
                                    "confidence": {"type": "number"},
                                    "start": {"type": "integer"},
                                    "end": {"type": "integer"}
                                },
                                "required": ["text", "label", "confidence"]
                            }
                        },
                        "required": ["entities"]
                    }
                }],
                temperature=0.1
            )

            processing_time = time.time() - start_time

            # Parse function call response
            if "choices" in llm_response and len(llm_response["choices"]) > 0:
                choice = llm_response["choices"][0]
                message = choice.get("message", {})

                if "tool_calls" in message:
                    try:
                        tool_calls = message["tool_calls"]
                        if tool_calls and len(tool_calls) > 0:
                            function_args = json.loads(tool_calls[0]["function"]["arguments"])
                        entities = function_args.get("entities", [])

                        return {
                            "success": True,
                            "entities": entities,
                            "method": "llm",
                            "processing_time": processing_time
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse LLM function call: {e}")
                        return {"success": False, "entities": [], "method": "llm", "error": str(e)}

            return {"success": False, "entities": [], "method": "llm", "error": "No function call found"}

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {"success": False, "entities": [], "method": "llm", "error": str(e)}

    async def _extract_with_patterns(self, user_message: str) -> Dict[str, Any]:
        """
        Extract entities using advanced pattern matching.
        """
        try:
            start_time = time.time()
            entities = []

            # Common e-commerce patterns
            patterns = [
                # Product descriptors
                r'\b(?:gaming|business|gaming laptop|laptop for gaming|workstation|desktop)\b',
                r'\b(?:wireless|bluetooth|noise-cancelling|over-ear|in-ear)\s+(?:headphones|earbuds|buds)\b',
                r'\b(?:smartphone|phone|mobile|cell phone)\b',
                r'\b(?:tablet|iPad)\b',

                # Size indicators
                r'\b(?:size|sized)\s+(?:\w+|\d+\")\b',
                r'\b(?:small|medium|large|x[lm]|xxl)\b',

                # Color mentions
                r'\b(?:red|blue|black|white|green|yellow|pink|purple|orange|brown)\b',

                # Quantity indicators
                r'\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:items|pieces|units|pairs|sets)\b',

                # Urgency indicators
                r'\b(?:urgent|asap|immediately|right now|as soon as possible)\b',
                r'\b(?:frustrated|angry|disappointed|unhappy|confused)\b'
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, user_message, re.IGNORECASE):
                    text = match.group()

                    # Determine entity type based on pattern
                    if any(word in text.lower() for word in ["gaming", "business", "workstation"]):
                        label = "PRODUCT_TYPE"
                    elif any(word in text.lower() for word in ["wireless", "bluetooth", "noise-cancelling"]):
                        label = "PRODUCT_FEATURE"
                    elif any(word in text.lower() for word in ["phone", "mobile", "smartphone"]):
                        label = "PRODUCT_TYPE"
                    elif any(word in text.lower() for word in ["small", "medium", "large", "xl", "xxl"]):
                        label = "SIZE"
                    elif any(word in text.lower() for word in ["red", "blue", "black", "white"]):
                        label = "COLOR"
                    elif any(word in text.lower() for word in ["urgent", "asap", "immediately"]):
                        label = "URGENCY"
                    elif any(word in text.lower() for word in ["frustrated", "angry", "disappointed"]):
                        label = "SENTIMENT"
                    else:
                        label = "DESCRIPTOR"

                    entities.append({
                        "text": text,
                        "label": label,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.6,
                        "extraction_method": "patterns"
                    })

            return {
                "success": True,
                "entities": entities,
                "method": "patterns",
                "processing_time": time.time() - start_time
            }

        except Exception as e:
            logger.error(f"Pattern extraction failed: {e}")
            return {"success": False, "entities": [], "method": "patterns", "error": str(e)}

    def _merge_extraction_results(self, results: list, user_message: str) -> List[Dict[str, Any]]:
        """
        Merge results from all extraction methods into a comprehensive entity list.

        Args:
            results: List of extraction results from different methods
            user_message: Original user message for context

        Returns:
            Merged list of entities with confidence scores
        """
        all_entities = []
        method_confidence = {
            "regex": 0.7,      # High confidence for exact patterns
            "llm": 0.9,        # Highest confidence for LLM understanding
            "patterns": 0.6    # Lower confidence for general patterns
        }

        # Collect all successful extractions
        for result in results:
            if isinstance(result, dict) and result.get("success", False):
                for entity in result.get("entities", []):
                    # Add method-specific confidence
                    entity["extraction_confidence"] = method_confidence.get(result.get("method", "unknown"), 0.5)
                    all_entities.append(entity)

        # Remove duplicates and conflicts
        merged_entities = self._resolve_entity_conflicts(all_entities, user_message)

        # Sort by confidence and position
        merged_entities.sort(key=lambda x: (x.get("extraction_confidence", 0.5), -x.get("start", 0)))

        return merged_entities

    def _resolve_entity_conflicts(self, entities: List[Dict[str, Any]], user_message: str) -> List[Dict[str, Any]]:
        """
        Resolve conflicts between overlapping entities and deduplicate.

        Args:
            entities: List of entities with potential conflicts
            user_message: Original message for context

        Returns:
            Deduplicated and conflict-resolved entity list
        """
        if not entities:
            return []

        # Sort by confidence first
        entities.sort(key=lambda x: x.get("extraction_confidence", 0.5), reverse=True)

        merged = []
        used_ranges = []

        for entity in entities:
            entity_range = (entity["start"], entity["end"])

            # Check for overlap with already used ranges
            has_conflict = any(
                not (entity_range[1] <= used_range[0] or entity_range[0] >= used_range[1])
                for used_range in used_ranges
            )

            if not has_conflict:
                merged.append(entity)
                used_ranges.append(entity_range)

        return merged

    async def _fallback_entity_extraction(self, state: ConversationState, error: str) -> ConversationState:
        """
        Fallback entity extraction when parallel methods fail.
        """
        try:
            logger.warning(f"Parallel entity extraction failed, using fallback: {error}")

            # Simple fallback to regex patterns only
            fallback_result = await self._extract_with_regex(state["user_message"])

            if fallback_result["success"]:
                return {
                    **state,
                    "entities": fallback_result["entities"],
                    "entity_extraction_method": "fallback_regex",
                    "llm_calls_count": state["llm_calls_count"],
                    "updated_at": time.time()
                }
            else:
                # Create minimal entity from message
                return {
                    **state,
                    "entities": [
                        {
                            "text": state["user_message"],
                            "label": "GENERAL",
                            "start": 0,
                            "end": len(state["user_message"]),
                            "confidence": 0.3,
                            "extraction_method": "minimal_fallback"
                        }
                    ],
                    "entity_extraction_method": "minimal_fallback",
                    "updated_at": time.time()
                }

        except Exception as e:
            logger.error(f"Fallback entity extraction failed: {e}")
            return create_error_state(state, str(e), "fallback_entity_extraction")

    async def enhanced_tool_decision_node(self, state: ConversationState) -> ConversationState:
        """
        Enhanced tool decision node that uses parallel entity extraction results.

        This Phase 2 improvement uses the merged entity extraction results
        to make more intelligent tool decisions with better context.

        Args:
            state: Current conversation state with extracted entities

        Returns:
            Updated state with enhanced tool decisions
        """
        start_time = time.time()
        user_message = state["user_message"]
        entities = state.get("entities", [])

        try:
            logger.info(f"Starting enhanced tool decision for {len(entities)} entities")

            # Build enhanced prompt with extracted entities
            enhanced_prompt = self._build_enhanced_tool_decision_prompt(user_message, entities, state)

            # Make tool decision using extracted entities
            llm_response = await self.llm_service.generate_response(
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert AI assistant for an e-commerce store. Using the extracted entities, make intelligent decisions about which tools to call.

**ENTITIES HAVE ALREADY BEEN EXTRACTED:**
{self._format_entities_for_prompt(entities)}

**TOOL SELECTION RULES:**
- search_products: Use when products, categories, brands, or prices are mentioned
- get_order_status: Use when order numbers or tracking is mentioned
- get_policy: Use for returns, shipping, refunds, policies
- get_faq: Use for general questions and common issues
- get_store_info: For store hours, location, contact
- get_contact_info: When escalation or human help is needed

**PRIORITY RULES:**
1. Customer intent (what they want to accomplish)
2. Entity completeness (do we have enough information?)
3. Tool relevance (does this tool help with the request?)

Return JSON with tool decisions."""
                    },
                    {
                        "role": "user",
                        "content": enhanced_prompt
                    }
                ],
                temperature=0.1,
                max_tokens=800
            )

            # Parse tool decision result
            tool_decision = self._parse_tool_decision_result(llm_response)

            # Update state with tool decisions
            updated_state = {
                **state,
                "tool_decisions": [tool_call.__dict__ for tool_call in tool_decision["tool_calls"]],
                "tool_reasoning": tool_decision["reasoning"],
                "confidence": tool_decision["confidence"],
                "requires_clarification": tool_decision["requires_clarification"],
                "suggested_follow_up": tool_decision["suggested_follow_up"],
                "escalation_needed": len(tool_decision["escalation_indicators"]) > 0,
                "escalation_reason": tool_decision["escalation_indicators"][0] if tool_decision["escalation_indicators"] else None,
                "llm_calls_count": state["llm_calls_count"] + 1,
                "updated_at": time.time()
            }

            logger.info(f"Enhanced tool decision completed in {time.time() - start_time:.2f}s")
            logger.info(f"Decided on {len(tool_decision['tool_calls'])} tools")

            return updated_state

        except Exception as e:
            logger.error(f"Enhanced tool decision failed: {e}")
            return create_error_state(state, str(e), "enhanced_tool_decision")

    def _build_enhanced_tool_decision_prompt(self, user_message: str, entities: List[Dict[str, Any]], state: ConversationState) -> str:
        """
        Build enhanced tool decision prompt using extracted entities.

        Args:
            user_message: Original user message
            entities: Extracted entities from parallel processing
            state: Current conversation state

        Returns:
            Enhanced prompt for tool decision making
        """
        prompt = f"""Make intelligent tool decisions based on this customer message and extracted entities:

**Customer Message:** "{user_message}"

**Extracted Entities:**
{self._format_entities_for_prompt(entities)}

**Available Tools:**
- search_products: Search products (query, price_min, price_max, category, brand, color, size, limit)
- get_order_status: Check order status (order_number, tracking_number)
- get_policy: Get policy information (policy_type: refund, shipping, privacy, terms)
- get_faq: Get FAQ information (category, question)
- get_store_info: Get store information (info_type: hours, location, contact)
- get_contact_info: Get contact details (contact_type: support, sales, returns)

**Instructions:**
1. Use the extracted entities to make precise tool selections
2. Generate accurate tool parameters from the entities
3. Consider customer intent and urgency
4. Choose tools that will best address the customer's needs

Return JSON with:
{{
    "tool_calls": [
        {{
            "tool_name": "search_products",
            "parameters": {{
                "query": "gaming laptop",
                "price_max": 1500,
                "limit": 10
            }},
            "execution_order": 1,
            "depends_on": []
        }}
    ],
    "reasoning": "Detailed explanation of your tool selection logic",
    "confidence": 0.85,
    "requires_clarification": false,
    "suggested_follow_up": ["Optional follow-up questions"],
    "escalation_indicators": []  // Keywords indicating human intervention needed
}}"""

        return prompt

    def _format_entities_for_prompt(self, entities: List[Dict[str, Any]]) -> str:
        """
        Format extracted entities for inclusion in LLM prompts.

        Args:
            entities: List of extracted entities

        Returns:
            Formatted string representation of entities
        """
        if not entities:
            return "No entities extracted"

        entity_lines = []
        for entity in entities:
            text = entity.get("text", "")
            label = entity.get("label", "")
            confidence = entity.get("confidence", 0.0)
            normalized = entity.get("normalized_value", "")

            line = f"- {label}: '{text}' (confidence: {confidence:.2f})"
            if normalized:
                line += f" -> {normalized}"
            entity_lines.append(line)

        return "\n".join(entity_lines)

    def _parse_tool_decision_result(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse LLM response for tool decision making.

        Args:
            llm_response: Response from LLM

        Returns:
            Parsed tool decision result
        """
        try:
            if "choices" in llm_response and len(llm_response["choices"]) > 0:
                content = llm_response["choices"][0]["message"]["content"]

                # Try to parse as JSON
                try:
                    tool_decision = json.loads(content)
                except json.JSONDecodeError:
                    # Fallback to basic structure
                    tool_decision = {
                        "tool_calls": [
                            {
                                "tool_name": "search_products",
                                "parameters": {"query": content, "limit": 10},
                                "execution_order": 1,
                                "depends_on": []
                            }
                        ],
                        "reasoning": f"Parsed from response: {content[:100]}...",
                        "confidence": 0.7,
                        "requires_clarification": False,
                        "suggested_follow_up": [],
                        "escalation_indicators": []
                    }

                # Convert to ToolCallState objects
                tool_calls = []
                for tool_call_data in tool_decision.get("tool_calls", []):
                    tool_call = ToolCallState(
                        tool_name=tool_call_data.get("tool_name", "search_products"),
                        parameters=tool_call_data.get("parameters", {}),
                        execution_order=tool_call_data.get("execution_order", 1),
                        depends_on=tool_call_data.get("depends_on", []),
                        status="pending",
                        result=None,
                        error=None,
                        execution_time=0.0
                    )
                    tool_calls.append(tool_call)

                return {
                    "tool_calls": tool_calls,
                    "reasoning": tool_decision.get("reasoning", "Tool decision completed"),
                    "confidence": tool_decision.get("confidence", 0.7),
                    "requires_clarification": tool_decision.get("requires_clarification", False),
                    "suggested_follow_up": tool_decision.get("suggested_follow_up", []),
                    "escalation_indicators": tool_decision.get("escalation_indicators", [])
                }

            else:
                # Fallback response
                return {
                    "tool_calls": [
                        ToolCallState(
                            tool_name="search_products",
                            parameters={"limit": 10},
                            execution_order=1,
                            depends_on=[],
                            status="pending",
                            result=None,
                            error=None,
                            execution_time=0.0
                        )
                    ],
                    "reasoning": "Fallback tool decision due to parsing failure",
                    "confidence": 0.5,
                    "requires_clarification": True,
                    "suggested_follow_up": ["Please clarify your request"],
                    "escalation_indicators": []
                }

        except Exception as e:
            logger.error(f"Failed to parse tool decision result: {e}")
            # Return fallback structure
            return {
                "tool_calls": [
                    ToolCallState(
                        tool_name="search_products",
                        parameters={"limit": 10},
                        execution_order=1,
                        depends_on=[],
                        status="pending",
                        result=None,
                        error=None,
                        execution_time=0.0
                    )
                ],
                "reasoning": "Error occurred during tool decision parsing",
                "confidence": 0.3,
                "requires_clarification": True,
                "suggested_follow_up": ["Please try again or contact support"],
                "escalation_indicators": []
            }

    def _parse_price_text(self, price_text: str) -> Dict[str, Any]:
        """
        Parse price text into structured data with operators and normalized values.

        Args:
            price_text: Raw price text from regex extraction

        Returns:
            Structured price data with operator and normalized values
        """
        try:
            import re

            # Extract the numeric value
            number_match = re.search(r'[\d,]+(?:\.\d{2})?', price_text.replace('$', '').replace(',', ''))
            if not number_match:
                return {"operator": "unknown", "min_value": None, "max_value": None}

            value = float(number_match.group())

            # Determine the operator based on the full text
            text_lower = price_text.lower()
            if any(word in text_lower for word in ["under", "below", "less than"]):
                operator = "lt"
                max_value = value
                min_value = None
            elif any(word in text_lower for word in ["over", "above", "more than"]):
                operator = "gt"
                min_value = value
                max_value = None
            elif any(word in text_lower for word in ["between", "from", "to", "and", "-"]):
                # For ranges, we'd need to extract two numbers - simplified for now
                operator = "between"
                max_value = value
                min_value = value * 0.8  # Estimate lower bound
            elif any(word in text_lower for word in ["around", "about", "approximately", "close to"]):
                operator = "approx"
                min_value = value * 0.9
                max_value = value * 1.1
            else:
                operator = "eq"
                min_value = value * 0.9
                max_value = value * 1.1

            return {
                "operator": operator,
                "min_value": min_value,
                "max_value": max_value,
                "raw_text": price_text
            }

        except Exception as e:
            logger.error(f"Failed to parse price text '{price_text}': {e}")
            return {"operator": "unknown", "min_value": None, "max_value": None, "raw_text": price_text}

    def _build_comprehensive_analysis_prompt(self, user_message: str, state: ConversationState) -> str:
        """
        Build the comprehensive analysis prompt for the LLM.

        Args:
            user_message: The user's message
            state: Current conversation state

        Returns:
            Formatted prompt for comprehensive analysis
        """
        prompt = f"""Analyze this customer message comprehensively:

**Customer Message:** "{user_message}"

**Tasks:**
1. Extract all relevant entities with confidence scores
2. Determine what the customer wants to accomplish
3. Decide which tools to call
4. Generate proper tool parameters

**Available Tools:**
- search_products: Search products (query, price_min, price_max, category, brand, color, size, limit)
- get_order_status: Check order status (order_number, tracking_number)
- get_policy: Get policy information (policy_type: refund, shipping, privacy, terms)
- get_faq: Get FAQ information (category, question)
- get_store_info: Get store information (info_type: hours, location, contact)
- get_contact_info: Get contact details (contact_type: support, sales, returns)

**Instructions:**
- Extract prices accurately (handle "under $1500", "between $100-$200", etc.)
- Identify products, brands, and specific requirements
- Detect sentiment and urgency
- Choose appropriate tools based on customer intent
- Generate precise tool parameters

Return a JSON object with:
{{
    "entities": [
        {{
            "text": "extracted text",
            "label": "PRICE|PRODUCT|BRAND|CATEGORY|ORDER_NUMBER",
            "confidence": 0.9,
            "normalized_value": {{"min_value": 100, "max_value": 150, "operator": "between"}}  // For prices only
        }}
    ],
    "tool_calls": [
        {{
            "tool_name": "search_products",
            "parameters": {{
                "query": "gaming laptop",
                "price_max": 1500,
                "limit": 10
            }},
            "execution_order": 1,
            "depends_on": []
        }}
    ],
    "reasoning": "Customer wants gaming laptop under $1500, so I'll search products with that budget constraint.",
    "confidence": 0.85,
    "requires_clarification": false,
    "suggested_follow_up": ["What specific features are you looking for?"],
    "escalation_indicators": [],  // Keywords indicating human intervention needed
    "processing_method": "llm_comprehensive"
}}

Be thorough but efficient. Focus on what will actually help the customer."""

        return prompt

    async def _parse_comprehensive_analysis_result(
        self,
        llm_response: Dict[str, Any],
        user_message: str
    ) -> AnalysisResult:
        """
        Parse the LLM response into a structured analysis result.

        Args:
            llm_response: Response from the LLM
            user_message: Original user message for fallback

        Returns:
            Structured analysis result
        """
        try:
            # Extract content from LLM response
            if "choices" in llm_response and len(llm_response["choices"]) > 0:
                content = llm_response["choices"][0]["message"]["content"]

                # Try to parse as JSON
                try:
                    analysis_data = json.loads(content)
                except json.JSONDecodeError:
                    # Fallback: extract information from text response
                    analysis_data = self._extract_analysis_from_text(content, user_message)

                # Validate and normalize the analysis data
                return self._normalize_analysis_result(analysis_data)

            else:
                # Fallback to basic analysis
                return self._create_fallback_analysis(user_message)

        except Exception as e:
            logger.error(f"Failed to parse comprehensive analysis result: {e}")
            return self._create_fallback_analysis(user_message)

    def _extract_analysis_from_text(self, content: str, user_message: str) -> Dict[str, Any]:
        """
        Extract analysis information from text response when JSON parsing fails.

        Args:
            content: Text content from LLM
            user_message: Original user message

        Returns:
            Analysis data extracted from text
        """
        # For Phase 1, create a simple fallback structure
        # In a production system, this would be more sophisticated
        return {
            "entities": [
                {
                    "text": user_message,
                    "label": "PRODUCT",
                    "confidence": 0.7,
                    "normalized_value": None
                }
            ],
            "tool_calls": [
                {
                    "tool_name": "search_products",
                    "parameters": {
                        "query": user_message,
                        "limit": 10
                    },
                    "execution_order": 1,
                    "depends_on": []
                }
            ],
            "reasoning": f"Based on the message: '{user_message}', I'm searching for relevant products.",
            "confidence": 0.7,
            "requires_clarification": False,
            "suggested_follow_up": [],
            "escalation_indicators": [],
            "processing_method": "text_fallback"
        }

    def _normalize_analysis_result(self, analysis_data: Dict[str, Any]) -> AnalysisResult:
        """
        Normalize and validate the analysis result from the LLM.

        Args:
            analysis_data: Raw analysis data from LLM

        Returns:
            Normalized analysis result
        """
        # Ensure all required fields exist
        normalized = {
            "entities": analysis_data.get("entities", []),
            "tool_calls": [],
            "reasoning": analysis_data.get("reasoning", "Analysis completed"),
            "confidence": analysis_data.get("confidence", 0.7),
            "requires_clarification": analysis_data.get("requires_clarification", False),
            "suggested_follow_up": analysis_data.get("suggested_follow_up", []),
            "escalation_indicators": analysis_data.get("escalation_indicators", []),
            "processing_method": analysis_data.get("processing_method", "llm_comprehensive"),
            "llm_response": analysis_data
        }

        # Convert tool calls to ToolCallState objects
        for tool_call_data in analysis_data.get("tool_calls", []):
            tool_call = ToolCallState(
                tool_name=tool_call_data.get("tool_name", "search_products"),
                parameters=tool_call_data.get("parameters", {}),
                execution_order=tool_call_data.get("execution_order", 1),
                depends_on=tool_call_data.get("depends_on", []),
                status="pending",
                result=None,
                error=None,
                execution_time=0.0
            )
            normalized["tool_calls"].append(tool_call)

        return normalized

    def _create_fallback_analysis(self, user_message: str) -> AnalysisResult:
        """
        Create a fallback analysis when LLM parsing fails.

        Args:
            user_message: Original user message

        Returns:
            Basic fallback analysis result
        """
        # Simple pattern-based fallback for Phase 1
        has_price = any(keyword in user_message.lower() for keyword in ["$", "price", "cost", "under", "over", "between"])
        has_order = any(keyword in user_message.lower() for keyword in ["order", "tracking", "shipment"])

        tool_name = "search_products"
        if has_order:
            tool_name = "get_order_status"
        elif "policy" in user_message.lower() or "return" in user_message.lower():
            tool_name = "get_policy"

        return {
            "entities": [
                {
                    "text": user_message,
                    "label": "PRODUCT" if not has_order else "ORDER_NUMBER",
                    "confidence": 0.6,
                    "normalized_value": None
                }
            ],
            "tool_calls": [
                ToolCallState(
                    tool_name=tool_name,
                    parameters={"query": user_message} if tool_name == "search_products" else {},
                    execution_order=1,
                    depends_on=[],
                    status="pending",
                    result=None,
                    error=None,
                    execution_time=0.0
                )
            ],
            "reasoning": f"Fallback analysis for message: '{user_message}'",
            "confidence": 0.6,
            "requires_clarification": False,
            "suggested_follow_up": [],
            "escalation_indicators": [],
            "processing_method": "pattern_fallback",
            "llm_response": None
        }

    async def execute_tools_node(self, state: ConversationState) -> ConversationState:
        """
        Execute the tools decided upon in the comprehensive analysis node.

        Args:
            state: Current conversation state with tool decisions

        Returns:
            Updated state with tool execution results
        """
        start_time = time.time()
        tool_decisions = state.get("tool_decisions", [])

        try:
            logger.info(f"Executing {len(tool_decisions)} tools")

            # Convert tool decisions back to ToolCall objects for execution
            tool_calls = []
            for tool_data in tool_decisions:
                from app.services.tool_system.tools_streamlined import ToolCall
                tool_call = ToolCall(
                    tool_name=tool_data["tool_name"],
                    parameters=tool_data["parameters"]
                )
                tool_calls.append(tool_call)

            # Execute tools (sequentially for Phase 1, parallel for Phase 2)
            tool_results = []
            for tool_call in tool_calls:
                try:
                    result = await self.tool_executor.execute_tool(tool_call)
                    tool_results.append({
                        "tool_name": tool_call.tool_name,
                        "success": result.success,
                        "data": result.data,
                        "error": result.error,
                        "execution_time": result.metadata.get("execution_time", 0.0) if result.metadata else 0.0
                    })
                except Exception as e:
                    logger.error(f"Tool execution failed for {tool_call.tool_name}: {e}")
                    tool_results.append({
                        "tool_name": tool_call.tool_name,
                        "success": False,
                        "data": None,
                        "error": str(e),
                        "execution_time": 0.0
                    })

            # Update state with tool execution results
            updated_state = {
                **state,
                "tool_results": tool_results,
                "tool_execution_time": time.time() - start_time,
                "updated_at": time.time()
            }

            logger.info(f"Tool execution completed in {time.time() - start_time:.2f}s")
            return updated_state

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return create_error_state(state, str(e), "tool_execution")

    async def parallel_tool_execution_node(self, state: ConversationState) -> ConversationState:
        """
        Parallel tool execution node that runs independent tools concurrently.

        This Phase 2 improvement analyzes tool dependencies and executes
        independent tools in parallel using asyncio.gather() for significant
        performance improvements.

        Args:
            state: Current conversation state with tool decisions

        Returns:
            Updated state with tool execution results
        """
        start_time = time.time()
        tool_decisions = state.get("tool_decisions", [])

        try:
            logger.info(f"Starting parallel tool execution for {len(tool_decisions)} tools")

            # Convert tool decisions to ToolCall objects
            tool_calls = []
            for tool_data in tool_decisions:
                from app.services.tool_system.tools_streamlined import ToolCall
                tool_call = ToolCall(
                    tool_name=tool_data["tool_name"],
                    parameters=tool_data["parameters"]
                )
                tool_calls.append(tool_call)

            # Analyze tool dependencies and create execution groups
            execution_groups = self._analyze_tool_dependencies(tool_calls)

            logger.info(f"Created {len(execution_groups)} execution groups for parallel processing")

            # Execute tools in parallel groups
            all_tool_results = []
            for group_idx, group in enumerate(execution_groups):
                logger.info(f"Executing group {group_idx + 1} with {len(group)} tools in parallel")

                if len(group) == 1:
                    # Single tool - execute sequentially
                    tool_call = group[0]
                    result = await self._execute_single_tool(tool_call)
                    all_tool_results.append(result)
                else:
                    # Multiple tools - execute in parallel
                    tasks = [self._execute_single_tool(tool_call) for tool_call in group]
                    group_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results and handle exceptions
                    for i, result in enumerate(group_results):
                        if isinstance(result, Exception):
                            logger.error(f"Parallel tool execution failed for {group[i].tool_name}: {result}")
                            all_tool_results.append({
                                "tool_name": group[i].tool_name,
                                "success": False,
                                "data": None,
                                "error": str(result),
                                "execution_time": 0.0
                            })
                        else:
                            all_tool_results.append(result)

            # Update state with all tool execution results
            updated_state = {
                **state,
                "tool_results": all_tool_results,
                "tool_execution_time": time.time() - start_time,
                "updated_at": time.time()
            }

            successful_tools = sum(1 for r in all_tool_results if r["success"])
            logger.info(f"Parallel tool execution completed in {time.time() - start_time:.2f}s")
            logger.info(f"Successfully executed {successful_tools}/{len(all_tool_results)} tools")

            return updated_state

        except Exception as e:
            logger.error(f"Parallel tool execution failed: {e}")
            return create_error_state(state, str(e), "parallel_tool_execution")

    def _analyze_tool_dependencies(self, tool_calls: List) -> List[List]:
        """
        Analyze tool dependencies and create execution groups.

        Tools that don't depend on each other can be executed in parallel.
        For Phase 2, we use a simple dependency analysis based on tool types.

        Args:
            tool_calls: List of tool calls to analyze

        Returns:
            List of execution groups (each group can run in parallel)
        """
        if not tool_calls:
            return []

        # For Phase 2, use a simple grouping strategy
        # Independent tools can run in parallel, dependent tools run sequentially

        independent_tools = []  # Can run in parallel
        dependent_tools = []    # Must run sequentially

        for tool_call in tool_calls:
            tool_name = tool_call.tool_name

            # Tools that are typically independent
            if tool_name in ["get_faq", "get_policy", "get_store_info", "get_contact_info"]:
                independent_tools.append(tool_call)
            else:
                # Tools that might depend on previous results
                dependent_tools.append(tool_call)

        # Create execution groups
        execution_groups = []

        # Group 1: Independent tools (can run in parallel)
        if independent_tools:
            execution_groups.append(independent_tools)

        # Group 2-N: Dependent tools (run sequentially or in small parallel groups)
        if dependent_tools:
            # For simplicity, run dependent tools one by one
            # In Phase 3, we could implement more sophisticated dependency analysis
            for tool in dependent_tools:
                execution_groups.append([tool])

        return execution_groups

    async def _execute_single_tool(self, tool_call) -> Dict[str, Any]:
        """
        Execute a single tool and return standardized result.

        Args:
            tool_call: ToolCall object to execute

        Returns:
            Standardized tool execution result
        """
        try:
            result = await self.tool_executor.execute_tool(tool_call)

            return {
                "tool_name": tool_call.tool_name,
                "success": result.success,
                "data": result.data,
                "error": result.error,
                "execution_time": result.metadata.get("execution_time", 0.0) if result.metadata else 0.0
            }
        except Exception as e:
            logger.error(f"Single tool execution failed for {tool_call.tool_name}: {e}")
            return {
                "tool_name": tool_call.tool_name,
                "success": False,
                "data": None,
                "error": str(e),
                "execution_time": 0.0
            }

    async def generate_response_node(self, state: ConversationState) -> ConversationState:
        """
        Generate the final response based on tool execution results.

        Args:
            state: Current conversation state with tool results

        Returns:
            Updated state with final response
        """
        start_time = time.time()
        user_message = state["user_message"]
        tool_results = state.get("tool_results", [])
        tool_reasoning = state.get("tool_reasoning", "")

        try:
            logger.info("Generating final response")

            # Build response generation prompt
            response_prompt = self._build_response_generation_prompt(
                user_message,
                tool_results,
                tool_reasoning,
                state
            )

            # Generate response
            llm_response = await self.llm_service.generate_response(
                messages=[
                    {
                        "role": "system",
                        "content": """You are a helpful customer service assistant for an e-commerce store. Generate natural, helpful responses based on tool execution results.

Your response should be:
- Friendly and professional
- Directly address the customer's question
- Use information from tool results when available
- Provide helpful suggestions or next steps
- Be concise but comprehensive"""
                    },
                    {
                        "role": "user",
                        "content": response_prompt
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )

            # Extract response content
            if "choices" in llm_response and len(llm_response["choices"]) > 0:
                response_content = llm_response["choices"][0]["message"]["content"]
            else:
                response_content = "I'm sorry, I encountered an issue while processing your request. Please try again or contact our support team."

            # Update state with final response
            updated_state = {
                **state,
                "response": response_content,
                "response_generation_method": "llm",
                "processing_time": state.get("processing_time", 0.0) + (time.time() - start_time),
                "llm_calls_count": state["llm_calls_count"] + 1,
                "updated_at": time.time()
            }

            logger.info(f"Response generation completed in {time.time() - start_time:.2f}s")
            return updated_state

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            error_response = "I'm sorry, I encountered an error while generating a response. Please try again."
            return create_error_state(state, str(e), "response_generation")

    def _build_response_generation_prompt(
        self,
        user_message: str,
        tool_results: List[Dict[str, Any]],
        tool_reasoning: str,
        state: ConversationState
    ) -> str:
        """
        Build the response generation prompt for the LLM.

        Args:
            user_message: Original user message
            tool_results: Results from tool execution
            tool_reasoning: Reasoning from tool selection
            state: Current conversation state

        Returns:
            Formatted prompt for response generation
        """
        prompt = f"""Generate a helpful response to the customer:

**Customer Message:** "{user_message}"

**Tool Reasoning:** {tool_reasoning}

**Tool Results:**
"""

        for result in tool_results:
            tool_name = result["tool_name"]
            success = result["success"]

            if success:
                data = result["data"]
                if isinstance(data, list) and len(data) > 0:
                    prompt += f"\n- {tool_name}: Found {len(data)} results"
                    if tool_name == "search_products" and len(data) > 0:
                        # Add product summary
                        prompt += f" (e.g., {data[0].get('title', 'Product')} - ${data[0].get('price', 'N/A')})"
                elif isinstance(data, dict):
                    prompt += f"\n- {tool_name}: {str(data)[:100]}..."
                else:
                    prompt += f"\n- {tool_name}: {str(data)[:100]}..."
            else:
                prompt += f"\n- {tool_name}: Failed - {result.get('error', 'Unknown error')}"

        prompt += f"""

**Additional Context:**
- Confidence: {state.get('confidence', 0.0):.2f}
- Requires clarification: {state.get('requires_clarification', False)}
- Suggested follow-up: {state.get('suggested_follow_up', [])}

Generate a natural, helpful response that:
1. Directly addresses the customer's question
2. Uses information from tool results
3. Provides helpful next steps or suggestions
4. Maintains a friendly, professional tone"""

        return prompt