"""
Streamlined LLM integration for essential tool calling functionality.
"""

import json
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from app.services.llm import LLMService
from app.services.tool_system.tools_streamlined import ToolCall, ToolResult, streamlined_tool_registry
from app.services.cache_service import CacheService
from app.core.config import settings


class StreamlinedToolCallingService:
    """Service for LLM-powered essential tool calling."""

    def __init__(self):
        self.llm_service = LLMService()
        from app.services.nlu import NLUService
        self.nlu_service = NLUService()
        self.cache_service = CacheService()
        self.system_prompt = self._load_system_prompt()

    def _get_cache_key(self, message: str, prefix: str = "response") -> str:
        """Generate cache key for responses."""
        # Create hash of normalized message for consistent caching
        normalized_message = message.strip().lower()
        message_hash = hashlib.md5(normalized_message.encode()).hexdigest()[:16]
        return f"{prefix}:{message_hash}"

    def _load_system_prompt(self) -> str:
        """Load the system prompt for essential tool calling."""
        return """You are a helpful AI assistant for an e-commerce store. You have access to essential tools to help customers with their inquiries.

Available tools:
- search_products: Search for products (supports price filtering, categories, brands)
- get_product_details: Get detailed product information
- get_order_status: Check order status and tracking
- get_policy: Get specific policies (refund, shipping, privacy, terms, subscription, legal)
- get_faq: Get frequently asked questions
- get_store_info: Get store information
- get_contact_info: Get contact details

Guidelines:
1. Use tools whenever you need specific information from the store
2. Focus on helping customers find products, check orders, and get policy information
3. **IMPORTANT**: When customers ask about return policy, refund policy, shipping policy, or any policy-related questions, ALWAYS use the get_policy tool
4. For policy questions, use the appropriate policy_type: "refund" for return/refund policies, "shipping" for shipping policies, "privacy" for privacy policies, "terms" for terms of service
5. **PRICE FILTERING - CRITICAL**: When customers mention prices, extract price information and use search_products with price parameters:
   - "under $50" → price_max: 50
   - "over $100" → price_min: 100
   - "between $50 and $100" → price_min: 50, price_max: 100
   - "exactly $75" → price_min: 75, price_max: 75
   - Remove dollar signs and convert to integers
   - Handle formats: "$50", "50 dollars", "50 USD", etc.
6. **MULTI-PARAMETER SEARCHES**: When customers mention brand + price, category + price, etc., include all relevant parameters in search_products:
   - "Sony headphones under $100" → query: "headphones", category: "electronics", brand: "Sony", price_max: 100
   - "gaming keyboards between $50-$150" → query: "gaming keyboards", price_min: 50, price_max: 150
7. Always provide helpful, customer-friendly responses
8. If you need to use multiple tools, make them one at a time
9. If tools fail, explain the issue and suggest alternatives

Think step by step about what tools you need and how they'll help answer the customer's question."""

    def _get_tools_schema(self) -> List[Dict[str, Any]]:
        """Get essential tools schema in OpenAI function calling format."""
        tools_schema = []

        for tool_name, tool_def in streamlined_tool_registry.get_all_tools().items():
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }

            for param in tool_def.parameters:
                param_schema = {
                    "type": param.type,
                    "description": param.description
                }

                if not param.required:
                    param_schema["default"] = param.default

                if param.enum:
                    param_schema["enum"] = param.enum

                parameters["properties"][param.name] = param_schema

                if param.required:
                    parameters["required"].append(param.name)

            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_def.description,
                    "parameters": parameters
                }
            }

            tools_schema.append(tool_schema)

        return tools_schema

    async def analyze_and_call_tools(
        self,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze user message and call appropriate essential tools using optimized 2-step process."""
        try:
            logger.info(f"OPTIMIZED_TRACE: analyze_and_call_tools started for message: '{user_message}'")
            logger.info(f"OPTIMIZATION: Using 2-step process instead of 3 sequential LLM calls")

            # STEP 1: Intent Classification (LLM Call #1)
            logger.info(f"OPTIMIZED_STEP_1: Intent classification")
            intent_result = await self._classify_intent_optimized(user_message, conversation_context)
            logger.info(f"OPTIMIZED_STEP_1_RESULT: {intent_result}")

            # Check if tools are required (greeting, conversational, etc.)
            if not intent_result.get("require_tool_call", False):
                logger.info(f"OPTIMIZATION: No tool call required - generating direct response")
                return {
                    "response": await self._generate_greeting_response(user_message),
                    "tool_calls": [],
                    "tool_results": [],
                    "reasoning": f"Intent classified as '{intent_result.get('intent')}' - no tool needed",
                    "extracted_entities": [],
                    "requires_clarification": False,
                    "suggested_follow_up": [],
                    "optimization_info": {
                        "llm_calls_used": 1,
                        "optimization_applied": "intent_classification_only"
                    }
                }

            # STEP 2: Tool and Argument Resolution (LLM Call #2) - combines entity extraction + tool selection
            logger.info(f"OPTIMIZED_STEP_2: Tool and argument resolution")
            tool_resolution = await self._resolve_tools_and_arguments_optimized(
                user_message, intent_result, conversation_context
            )
            logger.info(f"OPTIMIZED_STEP_2_RESULT: {tool_resolution}")

            # Execute the selected tools
            tool_results = await self._execute_tools(tool_resolution["tool_calls"])

            # Generate final response based on tool results
            final_response = await self._generate_response_with_results(
                user_message,
                tool_resolution["reasoning"],
                tool_results,
                conversation_context
            )

            return {
                "response": final_response["response"],
                "tool_calls": tool_resolution["tool_calls"],
                "tool_results": tool_results,
                "reasoning": tool_resolution["reasoning"],
                "requires_clarification": final_response.get("requires_clarification", False),
                "suggested_follow_up": final_response.get("suggested_follow_up", []),
                "extracted_entities": tool_resolution.get("extracted_entities", []),
                "optimization_info": {
                    "llm_calls_used": 2,
                    "optimization_applied": "2_step_process",
                    "intent": intent_result.get("intent"),
                    "confidence": intent_result.get("confidence")
                }
            }

        except Exception as e:
            logger.error(f"Error in essential tool calling analysis: {e}")
            return {
                "response": "I'm sorry, I encountered an error while processing your request. Please try again or contact our support team for assistance.",
                "tool_calls": [],
                "tool_results": [],
                "error": str(e),
                "extracted_entities": []
            }

    async def _classify_message_intent(self, user_message: str) -> Dict[str, Any]:
        """Use LLM to classify message intent and determine if tool calling is needed."""
        logger.info(f"INTENT_CLASSIFICATION: Starting classification for message: '{user_message}'")

        try:
            classification_prompt = f"""Classify the user message intent. You must respond with JSON only.

Message: "{user_message}"

Classify as one of these intents:
1. "greeting_conversational" - greetings, thanks, introductions, small talk, questions about the assistant
2. "product_search" - looking for products, asking about items, wanting to buy something, product inquiries
3. "order_inquiry" - asking about existing orders, tracking, returns, order status
4. "policy_inquiry" - asking about refund policy, shipping policy, privacy policy, terms of service, or other legal policies
5. "help_support" - asking for help, how-to questions, technical support, issues with products
6. "pricing_inquiry" - questions about prices, discounts, promotions, payment options
7. "account_inquiry" - issues with user account, login, profile, preferences
8. "general_question" - other questions that might need information, business hours, company info
9. "complaint" - expressing dissatisfaction or problems with products/service
10. "praise" - expressing satisfaction or positive feedback

Also indicate if tools should be called:
- greeting_conversational: skip_tools = true
- product_search: skip_tools = false
- order_inquiry: skip_tools = false
- policy_inquiry: skip_tools = false (policy tools available)
- help_support: skip_tools = false
- pricing_inquiry: skip_tools = false
- account_inquiry: skip_tools = false
- general_question: skip_tools = false
- complaint: skip_tools = false
- praise: skip_tools = true

Respond with JSON format:
{{"intent": "intent_name", "confidence": 0.9, "skip_tools": true/false, "reasoning": "brief explanation"}}"""

            logger.info(f"INTENT_CLASSIFICATION: About to call LLM service with prompt")
            response = await self.llm_service.generate_response(
                messages=[{"role": "user", "content": classification_prompt}],
                model=settings.INTENT_CLASSIFICATION_MODEL,
                temperature=0.1,
                max_tokens=100
            )
            logger.info(f"INTENT_CLASSIFICATION: LLM service responded with: '{response}'")

            # Try to parse JSON response
            try:
                # Handle both string and dictionary responses from LLM service
                if isinstance(response, dict):
                    # LLM service returned a dictionary directly (OpenRouter API response)
                    # Extract content from OpenRouter response format
                    if "choices" in response and len(response["choices"]) > 0:
                        content = response["choices"][0]["message"]["content"]
                        logger.info(f"INTENT_CLASSIFICATION: Extracted content from OpenRouter response: {content}")

                        # Remove markdown code blocks if present
                        content = content.replace('```json', '').replace('```', '').strip()

                        # Extract JSON from content string
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = content[json_start:json_end]
                            classification = json.loads(json_str)
                            logger.info(f"INTENT_CLASSIFICATION: Parsed JSON from OpenRouter content")
                        else:
                            raise ValueError("No JSON found in OpenRouter response content")
                    else:
                        raise ValueError("Invalid OpenRouter response format")
                elif isinstance(response, str):
                    # Remove markdown code blocks if present
                    content = response.replace('```json', '').replace('```', '').strip()
                    # Extract JSON from string response
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start != -1 and json_end != 0:
                        json_str = content[json_start:json_end]
                        classification = json.loads(json_str)
                        logger.info(f"INTENT_CLASSIFICATION: Parsed JSON from string response")
                    else:
                        raise ValueError("No JSON found in string response")
                else:
                    raise ValueError(f"Unexpected response type: {type(response)}")

                # Validate required fields
                if all(key in classification for key in ['intent', 'skip_tools']):
                    logger.info(f"LLM classified message as: {classification['intent']} (skip_tools: {classification['skip_tools']})")
                    return classification
                else:
                    raise ValueError(f"Missing required fields in classification: {classification}")

            except (json.JSONDecodeError, KeyError, ValueError, AttributeError) as e:
                logger.warning(f"Failed to parse LLM classification response: {e}")

            # Fallback to conservative approach - enable tools
            logger.warning("LLM classification failed, defaulting to tool calling enabled")
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "skip_tools": False,
                "reasoning": "Classification failed, defaulting to tool calling"
            }

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            # Fallback to conservative approach
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "skip_tools": False,
                "reasoning": "Classification error, defaulting to tool calling"
            }

    async def _handle_policy_inquiry_optimized(self, user_message: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """Optimized policy inquiry handling with intelligent caching and direct tool execution."""
        try:
            logger.info(f"POLICY_OPTIMIZATION: Processing policy inquiry: '{user_message}'")

            # Check cache first for policy responses
            cache_key = self._get_cache_key(user_message, "policy")
            cached_response = await self.cache_service.get(cache_key)
            if cached_response:
                logger.info(f"POLICY_OPTIMIZATION: Cache hit for policy inquiry: {cached_response[:30]}...")
                return {
                    "skip_tools": True,
                    "response_type": "policy",
                    "intent": "policy_inquiry",
                    "reasoning": "Optimized policy response from cache",
                    "tool_calls": [],
                    "response": cached_response,
                    "extracted_entities": []
                }

            # Extract policy type using simple pattern matching
            policy_type = self._extract_policy_type(user_message)
            logger.info(f"POLICY_OPTIMIZATION: Extracted policy type: {policy_type}")

            # Execute get_policy tool directly
            tool_results = await self._execute_tools([{
                "tool_name": "get_policy",
                "parameters": {"policy_type": policy_type}
            }])

            # Generate response based on policy result
            if tool_results and tool_results[0].success:
                policy_data = tool_results[0].data.get("policy", {})
                policy_response = await self._generate_policy_response(policy_type, policy_data, user_message)

                # Cache the response for 30 minutes
                await self.cache_service.set(cache_key, policy_response, ttl=1800)

                return {
                    "skip_tools": True,
                    "response_type": "policy",
                    "intent": "policy_inquiry",
                    "reasoning": f"Optimized policy response for {policy_type}",
                    "tool_calls": [{"tool_name": "get_policy", "parameters": {"policy_type": policy_type}}],
                    "tool_results": [tr.__dict__ for tr in tool_results],
                    "response": policy_response,
                    "extracted_entities": []
                }
            else:
                # Fallback to LLM-generated response if tool fails
                fallback_response = await self._generate_fallback_policy_response(user_message)
                return {
                    "skip_tools": True,
                    "response_type": "policy",
                    "intent": "policy_inquiry",
                    "reasoning": "Tool failed, using fallback LLM response",
                    "tool_calls": [],
                    "response": fallback_response,
                    "extracted_entities": []
                }

        except Exception as e:
            logger.error(f"POLICY_OPTIMIZATION: Error in optimized policy handling: {e}")
            # Fallback to standard tool processing
            return {
                "skip_tools": False,
                "intent": "policy_inquiry",
                "reasoning": "Optimized path failed, falling back to standard processing",
                "tool_calls": [],
                "extracted_entities": []
            }

    def _extract_policy_type(self, user_message: str) -> str:
        """Extract policy type from user message using pattern matching."""
        message_lower = user_message.lower()

        if any(word in message_lower for word in ["return", "refund", "exchange", "money back"]):
            return "refund"
        elif any(word in message_lower for word in ["ship", "delivery", "tracking", "shipping"]):
            return "shipping"
        elif any(word in message_lower for word in ["privacy", "data", "personal", "information"]):
            return "privacy"
        elif any(word in message_lower for word in ["terms", "service", "agreement", "legal"]):
            return "terms"
        elif any(word in message_lower for word in ["subscription", "recurring", "cancel"]):
            return "subscription"
        else:
            return "refund"  # Default to refund policy

    async def _generate_policy_response(self, policy_type: str, policy_data: Any, user_message: str) -> str:
        """Generate intelligent LLM-based policy response by analyzing customer question + store policy."""
        try:
            # Extract policy content from data
            if hasattr(policy_data, 'body'):
                policy_content = policy_data.body
            elif isinstance(policy_data, dict) and 'body' in policy_data:
                policy_content = policy_data['body']
            elif isinstance(policy_data, dict) and 'title' in policy_data:
                # Use title if body is not available
                policy_content = f"Policy: {policy_data.get('title', 'Unknown')}\n{policy_data.get('body', 'No details available')}"
            else:
                policy_content = "Policy information is currently unavailable. Please contact our support team for assistance."

            # Use LLM to intelligently analyze customer question + policy data
            analysis_prompt = f"""You are a helpful customer service assistant. Analyze the customer's question about store policies and provide a clear, helpful response based on the actual store policy.

Customer Question: "{user_message}"

Store Policy ({policy_type}):
{policy_content}

Instructions:
1. Read and understand the customer's specific question
2. Review the relevant store policy information
3. Provide a direct answer to their question based on the policy
4. If the policy doesn't fully address their question, explain what the policy does cover
5. Keep your response conversational and helpful
6. If relevant, suggest next steps or offer further assistance

Be thorough but concise. Focus on answering their specific question using the actual policy information provided."""

            response = await self.llm_service.generate_response(
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.3,
                max_tokens=500
            )

            return response if response else "I apologize, but I'm having trouble processing your policy question right now. Please contact our support team for assistance with this inquiry."

        except Exception as e:
            logger.error(f"Error generating intelligent policy response: {e}")
            return "I apologize, but I'm having trouble accessing our policy information right now. Please contact our support team for immediate assistance with your policy question."

    async def _generate_fallback_policy_response(self, user_message: str) -> str:
        """Generate a fallback policy response when tools fail."""
        response_prompt = f"""Generate a helpful response to this policy question. If you don't have specific policy information, provide general guidance and offer to connect with customer support.

User question: "{user_message}"

You are a helpful shop assistant. Provide a general response about the policy topic and offer to help further or connect to support if needed."""

        try:
            response = await self.llm_service.generate_response(
                messages=[{"role": "user", "content": response_prompt}],
                temperature=0.3,
                max_tokens=200
            )
            return response
        except Exception as e:
            logger.error(f"Failed to generate fallback policy response: {e}")
            return "I'm sorry, I'm having trouble accessing our policy information right now. Please contact our customer support team for immediate assistance with your policy question."

    async def _generate_greeting_response(self, user_message: str) -> str:
        """Generate a flexible LLM response for greetings and conversational messages with intelligent caching."""
        try:
            # Check cache first for semantically similar messages
            cache_key = self._get_cache_key(user_message, "conversational")
            cached_response = await self.cache_service.get(cache_key)
            if cached_response:
                logger.info(f"Cache hit for conversational message '{user_message}': {cached_response[:30]}...")
                return cached_response

            # Use LLM to generate natural, contextual response
            response_prompt = f"""Generate a natural, friendly response to this user message. Keep it concise (1-2 sentences) and conversational.

User message: "{user_message}"

You are a helpful shop assistant AI. Respond appropriately to the message type:
- For greetings: Return the greeting warmly and offer to help with shopping
- For questions about you: Briefly explain what you do and offer help
- For thanks: Acknowledge and offer further assistance
- For casual conversation: Be friendly and redirect to how you can help with shopping
- For test messages: Respond naturally and confirm you're working properly

Respond with just the conversational text, no JSON or formatting."""

            # Generate LLM response with shorter token limit for speed
            response = await self.llm_service.generate_response_for_stage(
                stage="response_generation",
                messages=[{"role": "user", "content": response_prompt}],
                temperature=0.7,
                max_tokens=60  # Reduced for faster responses
            )

            # Clean up response - handle both string and dict formats
            if isinstance(response, dict):
                # Extract content from OpenRouter response format
                if "choices" in response and len(response["choices"]) > 0:
                    content = response["choices"][0]["message"]["content"]
                    clean_response = content.strip().strip('"\'')
                else:
                    clean_response = str(response)
            else:
                clean_response = str(response).strip().strip('"\'')

            if clean_response:
                # Cache the response for 15 minutes (900 seconds) for conversational messages
                await self.cache_service.set(cache_key, clean_response, ttl=900)
                logger.info(f"Generated LLM conversational response for '{user_message}': {clean_response[:30]}...")
                return clean_response
            else:
                # Fallback to simple response
                fallback = "Hello! I'm your Shop Assistant AI. How can I help you today?"
                await self.cache_service.set(cache_key, fallback, ttl=900)
                return fallback

        except Exception as e:
            logger.error(f"Error generating LLM conversational response: {e}")
            # Simple fallback
            return "Hello! I'm here to help you find products and answer questions. How can I assist you today?"

    async def _decide_tools_to_use(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Decide which essential tools to use for the user message using LLM-powered intent classification exclusively."""
        logger.info(f"DEBUG: _decide_tools_to_use called for message: '{user_message}'")

        # Use LLM to classify message intent and determine if tools should be called
        try:
            logger.info(f"DEBUG: About to call _classify_message_intent")
            intent_classification = await self._classify_message_intent(user_message)
            logger.info(f"DEBUG: _classify_message_intent returned: {intent_classification}")
        except Exception as e:
            logger.error(f"DEBUG: Exception in _classify_message_intent: {e}")
            logger.error(f"DEBUG: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"DEBUG: Full traceback: {traceback.format_exc()}")
            # Fallback to continue with entity extraction if classification fails
            intent_classification = {"skip_tools": False, "intent": "unknown", "reasoning": "Classification failed"}

        # If LLM says this is conversational, skip tool calling entirely and return immediate response
        if intent_classification.get("skip_tools", False):
            logger.info(f"LLM classified as conversational: '{user_message}' - skipping tool calling and returning immediate greeting response")
            return {
                "skip_tools": True,
                "response_type": "greeting",
                "intent": intent_classification.get("intent"),
                "reasoning": intent_classification.get("reasoning", "LLM classified as conversational"),
                "tool_calls": [],
                "response": await self._generate_greeting_response(user_message)
            }

        # Optimized policy inquiry handling with intelligent caching
        if intent_classification.get("intent") == "policy_inquiry":
            logger.info(f"POLICY_OPTIMIZATION: Handling policy inquiry: '{user_message}'")
            return await self._handle_policy_inquiry_optimized(user_message, conversation_context)

        # For non-conversational messages, proceed with entity extraction and tool calling
        tools_schema = self._get_tools_schema()

        # Use LLM-based entity extraction for product/tool-related queries
        try:
            entity_extraction = await self.nlu_service.extract_entities(
                text=user_message,
                context=context,
                entity_types=["PRICE", "BRAND", "CATEGORY", "COLOR", "SIZE", "ORDER_NUMBER", "PRODUCT"]
            )
            extracted_entities = entity_extraction.get("entities", [])

            # Log extraction results for debugging
            logger.info(f"LLM entity extraction found {len(extracted_entities)} entities")
            for entity in extracted_entities:
                logger.debug(f"Entity: {entity.get('label')} = '{entity.get('text')}' (confidence: {entity.get('confidence', 0)})")

        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")
            extracted_entities = []

        # Build enhanced prompt with extracted entities
        entities_text = ""
        if extracted_entities:
            entities_text = "\n\n**LLM-Extracted Entities:**\n"
            for entity in extracted_entities:
                entity_info = f"- {entity.get('label', 'Unknown')}: '{entity.get('text', '')}' (confidence: {entity.get('confidence', 0):.2f})"

                # Include normalized values for price entities
                if entity.get('label') == 'PRICE' and 'normalized_value' in entity:
                    normalized = entity['normalized_value']
                    if normalized.get('min_value') is not None:
                        entity_info += f" → Parsed: min={normalized['min_value']}"
                    if normalized.get('max_value') is not None and normalized['max_value'] != normalized.get('min_value'):
                        entity_info += f", max={normalized['max_value']}"
                    if normalized.get('operator') != 'equals':
                        entity_info += f" (operator: {normalized['operator']})"

                entities_text += entity_info + "\n"
        else:
            entities_text = "\n\n**LLM-Extracted Entities:**\nNo entities extracted by LLM."

        prompt = f"""You are a helpful AI assistant for an e-commerce store. Analyze the customer's message and the LLM-extracted entities to decide what essential tools you need to use.

**Customer Message:** "{user_message}"

**Context:** {json.dumps(context or {}, indent=2)}{entities_text}

**TASK - LLM-POWERED ENTITY INTEGRATION AND TOOL SELECTION:**

The entities above were extracted by a sophisticated LLM entity extraction system. **CRITICAL:** Use these extracted entities as the foundation for your tool selection.

1. **Entity Integration Strategy:**
   - Trust the LLM-extracted entities (they're high-quality and precise)
   - Focus on PRICE entities for budget constraints
   - Use BRAND entities for brand-specific searches
   - Combine CATEGORY and PRODUCT entities for better search results
   - Integrate COLOR and SIZE entities when available

2. **Price Processing from LLM Entities:**
   - LLM has already identified AND PARSED price entities with high precision
   - **IMPORTANT**: Use the pre-parsed values (shown as "Parsed: min=X, max=Y") instead of re-parsing the text
   - For price entities with parsed values, use those directly:

1. **Extract and categorize entities from the message**:
   - Price information: Extract numerical values, remove currency symbols, determine ranges
   - Product specifications: Brand names, categories, features, colors, sizes
   - Order information: Order numbers, tracking details
   - Intent classification: What the customer wants to accomplish

2. **Price Processing Rules**:
   - Convert ALL price mentions to clean integers (no $, no commas, no text)
   - "under $50" → price_max: 50
   - "over $100" → price_min: 100
   - "between $50-$100" or "50 to 100" → price_min: 50, price_max: 100
   - "around $75" or "about $75" → price_min: 70, price_max: 80
   - "exactly $50" → price_min: 50, price_max: 50
   - Handle variations: "$50", "50 dollars", "50 USD", "$50.00", etc.

3. **Multi-Parameter Integration**:
   - Combine related entities into coherent search parameters
   - "Sony headphones under $100" → query: "Sony headphones", price_max: 100
   - "red gaming laptop between $800-$1200" → query: "gaming laptop", color: "red", price_min: 800, price_max: 1200
   - Include all relevant parameters that will help find the right products

4. **Context-Aware Decisions**:
   - Use extracted entities to make intelligent tool selections
   - Prioritize relevant entities over generic interpretations
   - Handle ambiguous cases by providing multiple options

Available tools:
- search_products: Search for products (supports query, price_min, price_max, category, brand, color, size, limit)
- get_product_details: Get detailed product information
- get_order_status: Check order status and tracking
- get_policy: Get specific policies (refund, shipping, privacy, terms, subscription, legal)
- get_faq: Get frequently asked questions
- get_store_info: Get store information
- get_contact_info: Get contact details

**CRITICAL INSTRUCTION:** Use the LLM-extracted entities shown above to make precise tool calls. The LLM entity extraction system is reliable and has already done the hard work of identifying and categorizing entities.

Respond with a JSON object containing:
1. "reasoning" - detailed explanation of your entity extraction and tool selection logic
2. "tool_calls" - list of tool calls with properly formatted parameters
3. "follow_up_questions" - only if essential information is missing

Example responses:
{{
    "reasoning": "LLM extracted PRICE='under $50' (confidence: 0.9) and PRODUCT='headphones' (confidence: 0.8). Customer wants headphones within a $50 budget. Using search_products with these precise LLM-extracted parameters.",
    "tool_calls": [
        {{
            "tool_name": "search_products",
            "parameters": {{
                "query": "headphones",
                "price_max": 50,
                "limit": 10
            }}
        }}
    ],
    "follow_up_questions": []
}}

{{
    "reasoning": "LLM extracted BRAND='Sony' (confidence: 0.95), PRODUCT='headphones' (confidence: 0.8), PRICE='between $100 and $200' (confidence: 0.9). Customer wants Sony headphones in $100-$200 range. Combining all LLM-extracted entities for optimal search results.",
    "tool_calls": [
        {{
            "tool_name": "search_products",
            "parameters": {{
                "query": "Sony headphones",
                "price_min": 100,
                "price_max": 200,
                "brand": "Sony",
                "limit": 10
            }}
        }}
    ],
    "follow_up_questions": []
}}

**REMEMBER:** The LLM has already done the entity extraction work. Your job is to integrate these high-quality entities into appropriate tool calls. Trust and use the extracted entities!"""

        messages = [{"role": "user", "content": prompt}]
        response = await self.llm_service.generate_response(
            messages=messages,
            max_tokens=1000,
            temperature=0.1
        )

        try:
            # Handle response format from OpenRouter
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)

            result = json.loads(content)
            if "tool_calls" not in result:
                result["tool_calls"] = []
            if "reasoning" not in result:
                result["reasoning"] = "No specific reasoning provided"
            if "follow_up_questions" not in result:
                result["follow_up_questions"] = []
            # Add extracted entities to the result
            result["extracted_entities"] = extracted_entities
            return result
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse tool decision JSON: {e}")
            return {
                "reasoning": "Failed to parse tool decision",
                "tool_calls": [],
                "follow_up_questions": [],
                "extracted_entities": extracted_entities
            }

    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[ToolResult]:
        """Execute the selected essential tools."""
        from app.services.tool_system.executor_streamlined import StreamlinedToolExecutor

        executor = StreamlinedToolExecutor()
        results = []

        for tool_call_data in tool_calls:
            tool_call = ToolCall(
                tool_name=tool_call_data["tool_name"],
                parameters=tool_call_data.get("parameters", {})
            )

            result = await executor.execute_tool(tool_call)
            results.append(result)

        return results

    async def _generate_response_with_results(
        self,
        user_message: str,
        reasoning: str,
        tool_results: List[ToolResult],
        context: Optional[Dict[str, Any]],
        skip_tools: bool = False,
        response_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate response based on essential tool results."""

        # If tools were skipped (greeting/conversational), generate appropriate response
        if skip_tools and response_type == "greeting":
            return {
                "response": await self._generate_greeting_response(user_message),
                "requires_clarification": False,
                "suggested_follow_up": ["What would you like to shop for?", "How can I help you today?"],
                "tool_calls": []
            }

        # Format tool results for the LLM (only for tool-based responses)
        formatted_results = []
        for result in tool_results:
            if result.success:
                # Convert complex objects to serializable format
                try:
                    # Handle special case for product lists and other complex objects
                    if isinstance(result.data, dict):
                        if 'products' in result.data:
                            # Use enhanced product formatting from existing parsers
                            try:
                                from ...integrations.shopify.parsers import format_products_for_llm
                                products = result.data['products']

                                if isinstance(products, list) and products:
                                    # Format products with enhanced context including inventory, customization, etc.
                                    data_text = format_products_for_llm(products[:5])  # Limit to first 5 products
                                else:
                                    data_text = "No products found matching your criteria."
                            except ImportError:
                                # Fallback to basic formatting if enhanced functions not available
                                products = result.data['products']
                                if isinstance(products, list) and products:
                                    product_info = []
                                    for product in products[:3]:
                                        if hasattr(product, 'title'):
                                            product_info.append(f"- {product.title}")
                                        elif isinstance(product, dict):
                                            product_info.append(f"- {product.get('title', 'Unknown Product')}")
                                        else:
                                            product_info.append(f"- {str(product)}")
                                    data_text = f"Found {len(products)} products:\n" + "\n".join(product_info)
                                else:
                                    data_text = str(result.data)
                        elif 'orders' in result.data:
                            # Use enhanced order formatting from existing parsers
                            try:
                                from ...integrations.shopify.parsers import format_order_context_for_llm
                                orders = result.data['orders']

                                if isinstance(orders, list) and orders:
                                    # Format first order with enhanced context
                                    data_text = format_order_context_for_llm(orders[0])
                                else:
                                    data_text = "No order information found."
                            except ImportError:
                                data_text = str(result.data)
                        else:
                            data_text = str(result.data)
                    else:
                        data_text = str(result.data)

                    formatted_results.append(f"[OK] {result.tool_name}: {data_text}")
                except Exception as e:
                    formatted_results.append(f"[OK] {result.tool_name}: Data available but formatting error: {e}")
            else:
                formatted_results.append(f"[FAIL] {result.tool_name}: {result.error}")

        tool_results_text = "\n\n".join(formatted_results) if formatted_results else "No tools were called."

        # Check if this is a "no products found" scenario by examining tool results data directly
        is_no_products_scenario = False
        for result in tool_results:
            if (result.success and
                hasattr(result, 'data') and
                result.data and
                'total_count' in result.data and
                result.data['total_count'] == 0):
                is_no_products_scenario = True
                break

        # Also check formatted results for backup detection - but only if product search was attempted
        if not is_no_products_scenario:
            is_no_products_scenario = (
                any("Found 0 products" in result for result in formatted_results)
            )

        # Use shorter prompt for no-products scenarios
        if is_no_products_scenario:
            prompt = f"""Generate a brief, helpful response when no products were found.

Customer message: "{user_message}"

Tool results: {tool_results_text}

**IMPORTANT: Keep your response SHORT and CONCISE (1-2 sentences maximum).**
- Acknowledge the search
- Briefly explain why no products matched
- Offer ONE simple alternative or suggestion

Example format: "I'm sorry, no [product] were found matching your criteria. Try [one simple suggestion]."

Respond with JSON:
{{
    "response": "Brief 1-2 sentence response",
    "requires_clarification": false,
    "suggested_follow_up": []
}}"""
        else:
            prompt = f"""Generate a helpful response to the customer based on their question and the tool results.

Customer message: "{user_message}"

My reasoning: {reasoning}

Tool results:
{tool_results_text}

Context: {json.dumps(context or {}, indent=2)}

Guidelines:
1. Be helpful, friendly, and professional
2. Use the tool results to provide specific, accurate information
3. If some tools failed, explain what happened and suggest alternatives
4. If you need more information, ask clarifying questions
5. Always provide actionable next steps when possible
6. **If no products were found, keep response SHORT and to the point (1-2 sentences max)**

**PRODUCT RESPONSE REQUIREMENTS:**
- When products are found, present them in a clear, organized format
- Include key product details in this order: title, price and discounts, short description, top features and customization options.
- Use markdown formatting for better readability (bold for emphasis, bullet points for features)
- For each product, write 2-3 sentences describing what the product is and why it's a good gift choice
- Group similar products together and explain why they're good recommendations
- End with helpful next steps or suggestions for finding more options

Respond with a JSON object containing:
{{
    "response": "Your response to the customer",
    "requires_clarification": true/false if you need more information,
    "suggested_follow_up": ["follow-up questions to ask"]
}}"""

        messages = [{"role": "user", "content": prompt}]

        # Use shorter token limit for no-products scenarios to force conciseness
        max_tokens = 150 if is_no_products_scenario else 1500

        response = await self.llm_service.generate_response(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7
        )

        try:
            # Handle response format from OpenRouter
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)

            result = json.loads(content)
            if "requires_clarification" not in result:
                result["requires_clarification"] = False
            if "suggested_follow_up" not in result:
                result["suggested_follow_up"] = []
            return result
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse response JSON: {e}")
            return {
                "response": content if 'content' in locals() else str(response),  # Return raw text if JSON parsing fails
                "requires_clarification": False,
                "suggested_follow_up": []
            }

    async def generate_tool_suggestions(
        self,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Generate suggestions for what essential tools might be helpful."""
        try:
            prompt = f"""Based on the customer's message, suggest what essential tools might be helpful.

Customer message: "{user_message}"

Context: {json.dumps(conversation_context or {}, indent=2)}

Available essential tools:
- search_products: Find products matching criteria
- get_product_details: Get detailed product information
- get_order_status: Check order status and tracking
- get_policy: Get refund, shipping, privacy policies
- get_faq: Get frequently asked questions
- get_store_info: Get store information
- get_contact_info: Get contact details

Return a JSON array of suggested tool names that might be helpful. Return an empty array if no tools seem relevant."""

            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_service.generate_response(
                messages=messages,
                max_tokens=300,
                temperature=0.1
            )

            try:
                # Handle response format from OpenRouter
                if isinstance(response, dict) and "choices" in response:
                    content = response["choices"][0]["message"]["content"]
                else:
                    content = str(response)

                suggestions = json.loads(content)
                if isinstance(suggestions, list):
                    return suggestions
                else:
                    return []
            except (json.JSONDecodeError, KeyError, IndexError):
                return []

        except Exception as e:
            logger.error(f"Error generating essential tool suggestions: {e}")
            return []

    async def format_tools_for_llm(self, tool_names: List[str]) -> str:
        """Format available essential tools for display to the user."""
        tools_info = []
        for tool_name in tool_names:
            tool_def = streamlined_tool_registry.get_tool(tool_name)
            if tool_def:
                tools_info.append(f"- **{tool_def.name}**: {tool_def.description}")

        return "\n".join(tools_info) if tools_info else "No specific essential tools identified."

    # ========== OPTIMIZED 2-STEP METHODS ==========

    async def _classify_intent_optimized(
        self,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        STEP 1: Optimized intent classification.
        Single LLM call to determine intent and whether tool calling is required.
        """
        logger.info(f"OPTIMIZED_CLASSIFICATION: Classifying intent for: '{user_message}'")

        classification_prompt = f"""You are an AI intent classifier for a shopping assistant.

Given the user's message, identify their primary intent from the following list:
- product_search: User wants to find, browse, or search for products
- order_inquiry: User wants to check order status, tracking, or order details
- policy_question: User asks about refund, shipping, return, privacy policies
- contact_inquiry: User wants contact information, store hours, location
- help_support: User needs help, how-to questions, technical support
- greeting_conversational: Greetings, thanks, introductions, small talk
- general_question: General business questions, company info
- complaint: User expressing dissatisfaction or problems
- praise: User expressing satisfaction or positive feedback

**CRITICAL:** Determine if this intent requires calling external tools:
- Tool Required: product_search, order_inquiry, policy_question, contact_inquiry, help_support, general_question
- No Tool Required: greeting_conversational, praise

Message: "{user_message}"

Return JSON only:
{{
    "intent": "intent_name",
    "confidence": 0.xx,
    "require_tool_call": true|false,
    "reasoning": "brief explanation of why this intent was chosen"
}}"""

        try:
            response = await self.llm_service.generate_response_for_stage(
                stage="intent_classification",
                messages=[{"role": "user", "content": classification_prompt}],
                temperature=0.1,
                max_tokens=150
            )

            # Parse JSON response
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)

            # Clean and parse JSON
            content = content.replace('```json', '').replace('```', '').strip()
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                # Validate required fields
                if all(key in result for key in ['intent', 'confidence', 'require_tool_call']):
                    logger.info(f"OPTIMIZED_CLASSIFICATION_RESULT: {result}")
                    return result
                else:
                    raise ValueError(f"Missing required fields: {result}")
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"OPTIMIZED_CLASSIFICATION_ERROR: {e}")
            # Fallback to assume tool calling is needed
            return {
                "intent": "general_question",
                "confidence": 0.5,
                "require_tool_call": True,
                "reasoning": "Classification failed, defaulting to tool calling"
            }

    async def _resolve_tools_and_arguments_optimized(
        self,
        user_message: str,
        intent_result: Dict[str, Any],
        conversation_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        STEP 2: Optimized tool and argument resolution.
        Single LLM call that combines entity extraction and tool selection with parameter mapping.
        """
        logger.info(f"OPTIMIZED_RESOLUTION: Resolving tools and arguments for intent: {intent_result.get('intent')}")

        tools_schema = self._get_tools_schema()

        resolution_prompt = f"""You are an intelligent tool selector for a shopping assistant.

Based on the user message and classified intent, select the correct tool and extract ALL required arguments in a single step.

**User Message:** "{user_message}"
**Classified Intent:** {intent_result.get('intent')} (confidence: {intent_result.get('confidence')})
**Context:** {json.dumps(conversation_context or {}, indent=2)}

**Available Tools:**
{json.dumps(tools_schema, indent=2)}

**TASK - COMPREHENSIVE ENTITY EXTRACTION AND TOOL SELECTION:**

1. **Extract and categorize ALL entities from the message:**
   - Price information: Extract numerical values, determine ranges (under $50, over $100, between $50-$100)
   - Product specifications: Brand names, categories, features, colors, sizes
   - Order information: Order numbers, tracking details
   - Contact/store information: What they're asking about

2. **Price Processing Rules:**
   - Convert ALL price mentions to clean integers (no $, no commas, no text)
   - "under $50" → price_max: 50
   - "over $100" → price_min: 100
   - "between $50-$100" → price_min: 50, price_max: 100
   - "around $75" → price_min: 70, price_max: 80
   - "exactly $50" → price_min: 50, price_max: 50

3. **Multi-Parameter Integration:**
   - Combine related entities into coherent search parameters
   - "Sony headphones under $100" → query: "Sony headphones", brand: "Sony", price_max: 100
   - Include ALL relevant parameters that will help find the right information

4. **Tool Selection Logic:**
   - product_search → search_products tool
   - order_inquiry → get_order_status tool
   - policy_question → get_policy tool
   - contact_inquiry → get_contact_info or get_store_info tool
   - help_support → get_faq tool
   - general_question → get_store_info tool

**CRITICAL INSTRUCTION:** Extract entities and map them to tool parameters in this single call. Do comprehensive analysis!

Return JSON only:
{{
    "tool_calls": [
        {{
            "tool_name": "tool_name",
            "parameters": {{
                "query": "search query constructed from entities",
                "price_min": 50,
                "price_max": 100,
                "brand": "Sony",
                "category": "electronics",
                "policy_type": "refund",
                "order_id": "12345",
                // Include all relevant parameters based on extracted entities
            }}
        }}
    ],
    "extracted_entities": [
        {{
            "type": "PRICE|BRAND|CATEGORY|PRODUCT|ORDER_NUMBER|POLICY_TYPE",
            "value": "extracted value",
            "confidence": 0.9,
            "normalized": "parsed/structured value if applicable"
        }}
    ],
    "reasoning": "detailed explanation of entity extraction and tool selection logic"
}}

Example for product search:
{{
    "tool_calls": [
        {{
            "tool_name": "search_products",
            "parameters": {{
                "query": "Sony headphones",
                "brand": "Sony",
                "price_max": 100,
                "limit": 10
            }}
        }}
    ],
    "extracted_entities": [
        {{"type": "BRAND", "value": "Sony", "confidence": 0.95}},
        {{"type": "PRODUCT", "value": "headphones", "confidence": 0.8}},
        {{"type": "PRICE", "value": "under $100", "normalized": {{"max_value": 100}}, "confidence": 0.9}}
    ],
    "reasoning": "User wants Sony headphones with budget under $100. Mapped brand, product, and price entities to search_products tool."
}}"""

        try:
            response = await self.llm_service.generate_response_for_stage(
                stage="tool_call",
                messages=[{"role": "user", "content": resolution_prompt}],
                temperature=0.1,
                max_tokens=1000
            )

            # Parse JSON response
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)

            # Clean and parse JSON
            content = content.replace('```json', '').replace('```', '').strip()
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = content[json_start:json_end]
                result = json.loads(json_str)

                # Validate and set defaults
                if "tool_calls" not in result:
                    result["tool_calls"] = []
                if "extracted_entities" not in result:
                    result["extracted_entities"] = []
                if "reasoning" not in result:
                    result["reasoning"] = "No reasoning provided"

                logger.info(f"OPTIMIZED_RESOLUTION_RESULT: {len(result['tool_calls'])} tools, {len(result['extracted_entities'])} entities")
                return result
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            logger.error(f"OPTIMIZED_RESOLUTION_ERROR: {e}")
            # Fallback - try to use original method
            logger.info("OPTIMIZATION_FALLBACK: Using original _decide_tools_to_use method")
            return await self._decide_tools_to_use(user_message, conversation_context)