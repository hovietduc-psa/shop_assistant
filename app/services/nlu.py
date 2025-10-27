"""
Natural Language Understanding service for intent classification and entity extraction.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from app.services.llm import LLMService
from app.services.embedding import EmbeddingService
from app.utils.exceptions import LLMError, ValidationError


class NLUService:
    """Service for Natural Language Understanding tasks."""

    def __init__(self):
        self.llm_service = LLMService()
        self.embedding_service = EmbeddingService()

        # Intent classification templates
        self.intent_prompts = self._load_intent_prompts()

        # Entity extraction function definitions
        self.entity_functions = self._load_entity_functions()

        # Few-shot examples for intent classification
        self.intent_examples = self._load_intent_examples()

    def _load_intent_prompts(self) -> Dict[str, str]:
        """Load intent classification prompt templates."""
        return {
            "system": """You are an AI assistant that classifies user intents for an e-commerce chatbot.

Your task is to analyze the user's message and determine their primary intent from the following categories:

1. **product_inquiry** - User wants information about products, features, specifications, or availability
2. **order_status** - User wants to check status of existing orders, tracking, delivery information
3. **support_request** - User needs help with issues, returns, exchanges, or technical problems
4. **general_question** - General information requests, company policies, business hours
5. **pricing_inquiry** - Questions about prices, discounts, promotions, payment options
6. **account_inquiry** - Issues with user account, login, profile, preferences
7. **policy_inquiry** - User asking about refund policy, shipping policy, privacy policy, terms of service, or other legal policies
8. **complaint** - User expressing dissatisfaction or problems
9. **praise** - User expressing satisfaction or positive feedback
10. **greeting** - Simple greetings or farewells
11. **other** - Any intent not covered above

Consider the context and nuances of the message. If multiple intents are present, choose the primary one.
""",

            "user_prompt": """Analyze the following user message and classify the intent:

Message: "{message}"

Return your analysis as a JSON object with the following format:
{
    "intent": "intent_name",
    "confidence": 0.85,
    "reasoning": "Brief explanation of why this intent was chosen"
}
""",
        }

    def _load_entity_functions(self) -> List[Dict[str, Any]]:
        """Load entity extraction function definitions."""
        return [
            {
                "name": "extract_entities",
                "description": "Extract entities from the user message",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "type": "string",
                                        "description": "The exact text of the entity"
                                    },
                                    "label": {
                                        "type": "string",
                                        "description": "The entity type (PRODUCT, PRICE, QUANTITY, COLOR, SIZE, BRAND, etc.)"
                                    },
                                    "start": {
                                        "type": "integer",
                                        "description": "Start position in the original text"
                                    },
                                    "end": {
                                        "type": "integer",
                                        "description": "End position in the original text"
                                    },
                                    "confidence": {
                                        "type": "number",
                                        "description": "Confidence score between 0 and 1"
                                    }
                                },
                                "required": ["text", "label", "start", "end"]
                            }
                        }
                    },
                    "required": ["entities"]
                }
            }
        ]

    def _load_intent_examples(self) -> List[Dict[str, str]]:
        """Load few-shot examples for intent classification."""
        return [
            {
                "message": "What's the price of the iPhone 15 Pro?",
                "intent": "pricing_inquiry",
                "reasoning": "User is asking about price information for a specific product"
            },
            {
                "message": "Where is my order #12345?",
                "intent": "order_status",
                "reasoning": "User is asking about the status/location of an existing order"
            },
            {
                "message": "The blue shirt I received is the wrong size",
                "intent": "support_request",
                "reasoning": "User is reporting a problem with a received item and needs help"
            },
            {
                "message": "What are your business hours?",
                "intent": "general_question",
                "reasoning": "User is asking for general business information"
            },
            {
                "message": "Show me laptops under $1000",
                "intent": "product_inquiry",
                "reasoning": "User wants to explore products with specific criteria"
            },
            {
                "message": "I can't log into my account",
                "intent": "account_inquiry",
                "reasoning": "User is having trouble with their account access"
            },
            {
                "message": "Your customer service is terrible!",
                "intent": "complaint",
                "reasoning": "User is expressing strong dissatisfaction"
            },
            {
                "message": "Hello! How can I help you today?",
                "intent": "greeting",
                "reasoning": "Simple greeting message"
            }
        ]

    async def classify_intent(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        use_few_shot: bool = True,
        alternatives_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Classify user intent using LLM.

        Args:
            text: User message text
            context: Additional context for classification
            use_few_shot: Whether to use few-shot examples
            alternatives_count: Number of alternative intents to return

        Returns:
            Dictionary with intent classification results
        """
        start_time = time.time()

        try:
            # Build messages
            messages = [
                {"role": "system", "content": self.intent_prompts["system"]}
            ]

            # Add few-shot examples if enabled
            if use_few_shot:
                messages.append({
                    "role": "system",
                    "content": "Here are some examples to help you understand the patterns:"
                })

                for example in self.intent_examples[:5]:  # Use first 5 examples
                    messages.append({
                        "role": "user",
                        "content": example["message"]
                    })
                    messages.append({
                        "role": "assistant",
                        "content": json.dumps({
                            "intent": example["intent"],
                            "confidence": 0.9,
                            "reasoning": example["reasoning"]
                        })
                    })

            # Add context if provided
            context_text = ""
            if context:
                context_parts = []
                if "previous_messages" in context:
                    context_parts.append(f"Recent conversation: {context['previous_messages'][-2:]}")
                if "user_info" in context:
                    context_parts.append(f"User context: {context['user_info']}")
                if "session_context" in context:
                    context_parts.append(f"Session context: {context['session_context']}")

                if context_parts:
                    context_text = "\n\nContext:\n" + "\n".join(context_parts)

            # Add the main prompt
            user_prompt = self.intent_prompts["user_prompt"].format(
                message=text,
                context=context_text
            )

            messages.append({"role": "user", "content": user_prompt})

            # Get LLM response
            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=200,
            )

            processing_time = time.time() - start_time

            # Parse response
            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]

                try:
                    # Check if this is a function call response
                    message_obj = response["choices"][0]["message"]
                    if "tool_calls" in message_obj:
                        # Handle function call result
                        tool_calls = message_obj["tool_calls"]
                        if tool_calls and len(tool_calls) > 0:
                            result = json.loads(tool_calls[0]["function"]["arguments"])
                    else:
                        # Try to parse JSON response
                        result = json.loads(content)

                    # Validate required fields
                    if "intent" not in result:
                        result["intent"] = "other"
                    if "confidence" not in result:
                        result["confidence"] = 0.5
                    if "reasoning" not in result:
                        result["reasoning"] = "No reasoning provided"

                    # Add metadata
                    result["processing_time"] = processing_time
                    result["model_used"] = response.get("model", "unknown")

                    # Generate alternatives if requested
                    if alternatives_count > 1:
                        result["alternatives"] = await self._generate_intent_alternatives(
                            text, result["intent"], alternatives_count - 1
                        )
                    else:
                        result["alternatives"] = []

                    return result

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse intent classification JSON: {content}")
                    # Fallback parsing
                    return self._parse_intent_fallback(content, processing_time)

            else:
                raise LLMError("No valid response from LLM for intent classification")

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return {
                "intent": "other",
                "confidence": 0.0,
                "reasoning": f"Classification failed: {str(e)}",
                "processing_time": time.time() - start_time,
                "alternatives": []
            }

    async def _generate_intent_alternatives(
        self,
        text: str,
        primary_intent: str,
        count: int
    ) -> List[Dict[str, Any]]:
        """Generate alternative intent classifications."""
        alternatives = []

        # Simple rule-based alternatives based on intent similarities
        intent_alternatives = {
            "product_inquiry": ["pricing_inquiry", "general_question"],
            "order_status": ["support_request", "account_inquiry"],
            "support_request": ["complaint", "order_status"],
            "pricing_inquiry": ["product_inquiry", "general_question"],
            "account_inquiry": ["support_request", "general_question"],
            "complaint": ["support_request"],
            "praise": ["general_question"],
            "general_question": ["product_inquiry", "pricing_inquiry"],
        }

        if primary_intent in intent_alternatives:
            for alt_intent in intent_alternatives[primary_intent][:count]:
                alternatives.append({
                    "intent": alt_intent,
                    "confidence": 0.3,  # Lower confidence for alternatives
                    "reasoning": f"Alternative to {primary_intent}"
                })

        return alternatives

    def _parse_intent_fallback(
        self,
        content: str,
        processing_time: float
    ) -> Dict[str, Any]:
        """Fallback parsing for intent classification when JSON parsing fails."""
        # Simple pattern matching as fallback
        content_lower = content.lower()

        intent_patterns = {
            "product_inquiry": ["product", "show", "find", "looking for", "recommend"],
            "order_status": ["order", "tracking", "delivery", "shipped", "status"],
            "pricing_inquiry": ["price", "cost", "how much", "discount", "sale"],
            "support_request": ["help", "problem", "issue", "broken", "wrong", "return"],
            "account_inquiry": ["account", "login", "password", "profile"],
            "complaint": ["terrible", "awful", "worst", "disappointed", "angry"],
            "general_question": ["what", "when", "where", "how", "why"],
            "greeting": ["hello", "hi", "hey", "goodbye", "bye"],
        }

        detected_intent = "other"
        for intent, patterns in intent_patterns.items():
            if any(pattern in content_lower for pattern in patterns):
                detected_intent = intent
                break

        return {
            "intent": detected_intent,
            "confidence": 0.3,  # Low confidence for fallback
            "reasoning": "Fallback classification due to parsing error",
            "processing_time": processing_time,
            "alternatives": []
        }

    async def extract_entities(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract entities from text using LLM function calling.

        Args:
            text: Text to extract entities from
            context: Additional context
            entity_types: Specific entity types to focus on

        Returns:
            Dictionary with extracted entities
        """
        start_time = time.time()

        try:
            # Build messages
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI assistant that extracts entities from user messages for an e-commerce chatbot.

Extract relevant entities such as:
- PRODUCT: Product names, models, types
- PRICE: Monetary amounts, prices
- QUANTITY: Numbers, quantities
- COLOR: Colors
- SIZE: Sizes
- BRAND: Brand names
- CATEGORY: Product categories
- ORDER_NUMBER: Order identifiers
- LOCATION: Addresses, locations

Be precise with start and end positions. Only extract entities you are confident about."""
                }
            ]

            # Add context if provided
            if context:
                context_text = f"\nContext: {json.dumps(context, indent=2)}"
                messages[0]["content"] += context_text

            # Add the main message
            messages.append({
                "role": "user",
                "content": f"Extract entities from this message: \"{text}\""
            })

            # Use function calling
            response = await self.llm_service.function_calling(
                messages=messages,
                functions=self.entity_functions,
                temperature=0.1,
            )

            processing_time = time.time() - start_time

            # Parse function call response
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                message = choice.get("message", {})

                if "tool_calls" in message:
                    try:
                        # Handle OpenRouter tool calls format
                        tool_calls = message["tool_calls"]
                        if tool_calls and len(tool_calls) > 0:
                            function_args = json.loads(tool_calls[0]["function"]["arguments"])
                        entities = function_args.get("entities", [])

                        # Filter by entity types if specified
                        if entity_types:
                            entities = [
                                entity for entity in entities
                                if entity.get("label") in entity_types
                            ]

                        return {
                            "entities": entities,
                            "processing_time": processing_time,
                            "model_used": response.get("model", "unknown")
                        }

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse function call arguments: {e}")
                        return await self._extract_entities_llm_only(text, context, entity_types)
                else:
                    # No function call, try the enhanced LLM approach
                    logger.warning("No function call in initial LLM response, trying enhanced approach")
                    return await self._extract_entities_llm_only(text, context, entity_types)

            else:
                raise LLMError("No valid response from LLM for entity extraction")

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {
                "entities": [],
                "processing_time": time.time() - start_time,
                "error": str(e)
            }

    async def _extract_entities_llm_only(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """LLM-only entity extraction with enhanced prompting."""
        start_time = time.time()

        try:
            # Enhanced system prompt with better entity extraction guidance
            system_prompt = """You are an expert AI assistant for extracting entities from e-commerce customer messages.

Your task is to carefully analyze the customer's message and extract relevant entities with high precision.

**ENTITY TYPES TO EXTRACT:**
- **PRODUCT**: Product names, models, types (e.g., "headphones", "laptop", "iPhone")
- **PRICE**: Monetary amounts, prices, budgets (e.g., "$50", "under $100", "50 dollars")
- **BRAND**: Brand names (e.g., "Sony", "Apple", "Nike", "Samsung")
- **CATEGORY**: Product categories (e.g., "electronics", "clothing", "gaming")
- **COLOR**: Colors mentioned (e.g., "red", "black", "blue")
- **SIZE**: Sizes mentioned (e.g., "large", "medium", "XL")
- **ORDER_NUMBER**: Order identifiers (e.g., "#1001", "order 12345")
- **QUANTITY**: Quantities mentioned (e.g., "2", "three", "a pair")

**PRICE EXTRACTION RULES - CRITICAL:**
1. Convert ALL price mentions to clean integers (remove $, commas, etc.)
2. "under $50" → Extract as "PRICE" entity with text "under $50"
3. "over $100" → Extract as "PRICE" entity with text "over $100"
4. "between $50 and $100" → Extract as "PRICE" entity with text "between $50 and $100"
5. "around $75" → Extract as "PRICE" entity with text "around $75"
6. "exactly $50" → Extract as "PRICE" entity with text "exactly $50"
7. Handle formats: "$50", "50 dollars", "50 USD", "$50.00", etc.

**PRECISION GUIDELINES:**
- Only extract entities you are confident about (confidence 0.7+)
- Provide exact start/end positions for each entity
- Use context to disambiguate (e.g., "apple" as brand vs fruit)
- Prioritize brand names and price information for e-commerce
- If unsure about an entity, exclude it rather than guess

**CONTEXT AWARENESS:**
- Consider the conversation context for entity disambiguation
- Prioritize entities that are relevant to e-commerce scenarios
- Handle compound entities (e.g., "Sony headphones" should extract both "Sony" and "headphones")"""

            # Add context if provided
            if context:
                system_prompt += f"\n\nConversation Context:\n{json.dumps(context, indent=2)}"

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Extract entities from this customer message: \"{text}\"\n\nFocus on precision and only extract entities you are confident about. Return results using the extract_entities function.\n\nIMPORTANT: You MUST use the extract_entities function to return your results. Do not provide a regular text response."
                }
            ]

            # Use function calling with enhanced error handling
            response = await self.llm_service.function_calling(
                messages=messages,
                functions=self.entity_functions,
                temperature=0.1,
            )

            processing_time = time.time() - start_time

            # Parse function call response
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                message = choice.get("message", {})

                if "tool_calls" in message:
                    try:
                        tool_calls = message["tool_calls"]
                        if tool_calls and len(tool_calls) > 0:
                            function_args = json.loads(tool_calls[0]["function"]["arguments"])
                            entities = function_args.get("entities", [])

                            # Filter by entity types if specified
                            if entity_types:
                                entities = [
                                    entity for entity in entities
                                    if entity.get("label") in entity_types
                                ]

                            # Validate entity quality
                            validated_entities = []
                            for entity in entities:
                                # Ensure minimum confidence
                                if entity.get("confidence", 0) < 0.6:
                                    continue

                                # Validate structure
                                if all(key in entity for key in ["text", "label", "start", "end", "confidence"]):
                                    validated_entities.append(entity)

                            return {
                                "entities": validated_entities,
                                "processing_time": processing_time,
                                "model_used": response.get("model", "unknown"),
                                "method": "llm_only_enhanced"
                            }

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse LLM function call: {e}")
                        # Return empty results instead of regex fallback
                        return {
                            "entities": [],
                            "processing_time": processing_time,
                            "error": "LLM response parsing failed",
                            "method": "llm_only_error"
                        }
                else:
                    # No function call returned, try to extract from content
                    logger.warning("LLM did not return function call for entity extraction, trying JSON fallback")
                    return await self._extract_entities_json_fallback(response, processing_time, text)

            else:
                raise LLMError("No valid response from LLM for entity extraction")

        except Exception as e:
            logger.error(f"LLM entity extraction failed: {e}")
            return {
                "entities": [],
                "processing_time": time.time() - start_time,
                "error": str(e),
                "method": "llm_only_exception"
            }

    async def _extract_entities_json_fallback(
        self,
        response: Dict[str, Any],
        processing_time: float,
        original_text: str
    ) -> Dict[str, Any]:
        """Fallback method to extract entities from LLM JSON response when function calling fails."""
        try:
            # Get the content from the response
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")

                if not content:
                    return {
                        "entities": [],
                        "processing_time": processing_time,
                        "error": "No content in LLM response",
                        "method": "json_fallback_error"
                    }

                # Try to parse JSON from the content
                try:
                    # Look for JSON in the content
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        data = json.loads(json_str)

                        # Handle different response formats
                        if "entities" in data:
                            entities = data["entities"]
                        elif "extracted_entities" in data:
                            entities = data["extracted_entities"]
                        else:
                            # Try to extract entities from a different format
                            entities = []

                        # Validate entities
                        validated_entities = []
                        for entity in entities:
                            if isinstance(entity, dict):
                                # Ensure required fields
                                if "text" in entity and "label" in entity:
                                    # Add missing fields with defaults
                                    if "start" not in entity:
                                        entity["start"] = original_text.find(entity["text"])
                                    if "end" not in entity:
                                        entity["end"] = entity["start"] + len(entity["text"])
                                    if "confidence" not in entity:
                                        entity["confidence"] = 0.8  # Default confidence

                                    validated_entities.append(entity)

                        return {
                            "entities": validated_entities,
                            "processing_time": processing_time,
                            "method": "json_fallback"
                        }
                    else:
                        # No JSON found, try a simple text-based extraction
                        return await self._extract_entities_simple_fallback(content, processing_time, original_text)

                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON from LLM response, trying simple fallback")
                    return await self._extract_entities_simple_fallback(content, processing_time, original_text)
            else:
                return {
                    "entities": [],
                    "processing_time": processing_time,
                    "error": "Invalid response structure",
                    "method": "json_fallback_error"
                }

        except Exception as e:
            logger.error(f"JSON fallback failed: {e}")
            return {
                "entities": [],
                "processing_time": processing_time,
                "error": str(e),
                "method": "json_fallback_exception"
            }

    async def _extract_entities_simple_fallback(
        self,
        content: str,
        processing_time: float,
        original_text: str
    ) -> Dict[str, Any]:
        """Simple fallback to extract entities from plain text LLM response."""
        entities = []

        # Simple pattern matching for common entities
        import re

        # Price patterns - Enhanced for better extraction
        price_patterns = [
            r'\$\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # $50, $1,500, $50.99, $1,500.99
            r'\d{1,5}(?:,\d{3})*(?:\.\d{2})?\s+dollars?',  # 50 dollars, 1,500 dollars, 50.99 dollars
            r'(?:under|below|less than)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # under $50, under $1,500
            r'(?:over|above|more than)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # over $100, over $1,000
            r'(?:between|from)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?\s+(?:and|to|-)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # between $50 and $100, between $1,000 and $1,500
            r'(?:around|about|approximately|close to)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # around $50, about $1,000
            r'(?:exactly|just)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # exactly $50, just $1,000
            r'(?:at|for)\s+\$?\s*\d{1,5}(?:,\d{3})*(?:\.\d{2})?',  # at $50, for $1,000
        ]

        # Brand patterns
        brands = ["Sony", "Apple", "Samsung", "Nike", "Adidas", "LG", "Microsoft", "Dell", "HP", "Canon", "Nikon"]

        # Product categories
        categories = ["headphones", "laptops", "cameras", "watches", "shoes", "shirts"]

        # Extract prices
        for pattern in price_patterns:
            for match in re.finditer(pattern, original_text, re.IGNORECASE):
                price_text = match.group()
                parsed_price = self._parse_price_text(price_text)

                entities.append({
                    "text": price_text,
                    "label": "PRICE",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.7,
                    "normalized_value": parsed_price
                })

        # Extract brands
        for brand in brands:
            for match in re.finditer(rf'\b{brand}\b', original_text, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "label": "BRAND",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.8
                })

        # Extract products
        for category in categories:
            for match in re.finditer(rf'\b{category}\b', original_text, re.IGNORECASE):
                entities.append({
                    "text": match.group(),
                    "label": "PRODUCT",
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.8
                })

        return {
            "entities": entities,
            "processing_time": processing_time,
            "method": "simple_fallback"
        }

    async def analyze_sentiment(
        self,
        text: str,
        detailed: bool = False,
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze
            detailed: Whether to return detailed emotion analysis

        Returns:
            Dictionary with sentiment analysis results
        """
        start_time = time.time()

        try:
            if detailed:
                prompt = f"""
                Analyze the sentiment of this text: "{text}"

                Return a JSON object with:
                - sentiment: "positive", "negative", or "neutral"
                - confidence: confidence score between 0 and 1
                - emotions: dictionary with scores for joy, anger, sadness, fear, surprise (0-1 scale)
                - reasoning: brief explanation
                """
            else:
                prompt = f"""
                Analyze the sentiment of this text: "{text}"

                Return a JSON object with:
                - sentiment: "positive", "negative", or "neutral"
                - confidence: confidence score between 0 and 1
                - reasoning: brief explanation
                """

            messages = [
                {"role": "system", "content": "You are a sentiment analysis AI. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=300,
            )

            processing_time = time.time() - start_time

            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]

                try:
                    result = json.loads(content)

                    # Ensure required fields
                    if "sentiment" not in result:
                        result["sentiment"] = "neutral"
                    if "confidence" not in result:
                        result["confidence"] = 0.5
                    if "reasoning" not in result:
                        result["reasoning"] = "No reasoning provided"

                    # Add default emotions if not detailed
                    if detailed and "emotions" not in result:
                        result["emotions"] = {
                            "joy": 0.0,
                            "anger": 0.0,
                            "sadness": 0.0,
                            "fear": 0.0,
                            "surprise": 0.0
                        }

                    result["processing_time"] = processing_time
                    result["model_used"] = response.get("model", "unknown")

                    return result

                except json.JSONDecodeError:
                    logger.error(f"Failed to parse sentiment JSON: {content}")
                    return self._parse_sentiment_fallback(text, processing_time)

            else:
                raise LLMError("No valid response from LLM for sentiment analysis")

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
                "processing_time": time.time() - start_time
            }

    def _parse_sentiment_fallback(
        self,
        text: str,
        processing_time: float
    ) -> Dict[str, Any]:
        """Fallback sentiment analysis using simple keyword matching."""
        text_lower = text.lower()

        positive_words = ["good", "great", "excellent", "amazing", "love", "perfect", "wonderful", "fantastic"]
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "horrible", "disappointed", "angry"]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
            confidence = min(0.8, 0.5 + (positive_count * 0.1))
        elif negative_count > positive_count:
            sentiment = "negative"
            confidence = min(0.8, 0.5 + (negative_count * 0.1))
        else:
            sentiment = "neutral"
            confidence = 0.5

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "reasoning": "Fallback sentiment analysis using keyword matching",
            "processing_time": processing_time,
            "method": "fallback"
        }

    def _parse_price_text(self, price_text: str) -> Dict[str, Any]:
        """
        Parse price text into structured data.

        Handles various price formats:
        - $1500, $1,500, $1500.99
        - under $1500, over $1000
        - between $1000 and $1500
        - around $1500, exactly $1500
        - 1500 dollars, 1500.99 dollars

        Args:
            price_text: The extracted price text

        Returns:
            Dictionary with parsed price information
        """
        import re

        result = {
            "original_text": price_text,
            "min_value": None,
            "max_value": None,
            "operator": "equals",
            "currency": "USD"
        }

        try:
            # Remove common words and extract numbers
            cleaned_text = price_text.lower().strip()

            # Check for operators
            if any(word in cleaned_text for word in ["under", "below", "less than"]):
                result["operator"] = "less_than"
            elif any(word in cleaned_text for word in ["over", "above", "more than"]):
                result["operator"] = "greater_than"
            elif any(word in cleaned_text for word in ["between", "from"]):
                result["operator"] = "between"
            elif any(word in cleaned_text for word in ["around", "about", "approximately", "close to"]):
                result["operator"] = "approximately"

            # Extract all numbers from the text
            numbers = re.findall(r'[\d,]+(?:\.\d{2})?', cleaned_text)

            if numbers:
                # Parse numbers (remove commas, convert to float)
                parsed_numbers = []
                for num_str in numbers:
                    # Remove commas and convert to float
                    clean_num = num_str.replace(',', '')
                    try:
                        if '.' in clean_num:
                            parsed_numbers.append(float(clean_num))
                        else:
                            parsed_numbers.append(float(clean_num))
                    except ValueError:
                        continue

                if parsed_numbers:
                    if result["operator"] == "between" and len(parsed_numbers) >= 2:
                        # For "between X and Y", use both values
                        result["min_value"] = min(parsed_numbers[:2])
                        result["max_value"] = max(parsed_numbers[:2])
                    else:
                        # For other cases, use the primary value
                        primary_value = parsed_numbers[0]

                        if result["operator"] == "less_than":
                            result["max_value"] = primary_value
                        elif result["operator"] == "greater_than":
                            result["min_value"] = primary_value
                        else:
                            # equals, approximately
                            result["min_value"] = result["max_value"] = primary_value

                            # For approximate values, add a small range
                            if result["operator"] == "approximately":
                                margin = primary_value * 0.1  # 10% margin
                                result["min_value"] = max(0, primary_value - margin)
                                result["max_value"] = primary_value + margin

        except Exception as e:
            logger.error(f"Error parsing price text '{price_text}': {e}")

        return result