"""
LLM service for OpenRouter integration and model management.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import httpx
from loguru import logger
from app.core.config import settings
from app.utils.exceptions import LLMError, ExternalServiceError


class LLMService:
    """Service for managing LLM interactions through OpenRouter."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.default_model = settings.DEFAULT_LLM_MODEL
        self.timeout = 30.0

        # Available models for fallback
        self.available_models = [
            "openai/gpt-4",
            "openai/gpt-4-turbo-preview",
            "anthropic/claude-3-opus",
            "anthropic/claude-3-sonnet",
            "anthropic/claude-3-haiku",
        ]

        # Initialize HTTP client
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://shop-assistant-ai.com",
                    "X-Title": "Shop Assistant AI",
                }
            )
        return self._client

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        fallback_models: Optional[List[str]] = None,
    ) -> Union[Dict[str, Any], str]:
        """
        Generate a response from the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model to use (defaults to configured default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter
            stream: Whether to stream the response
            fallback_models: List of fallback models to try

        Returns:
            Response dictionary or streamed content
        """
        model = model or self.default_model
        fallback_models = fallback_models or self.available_models

        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            request_data["max_tokens"] = max_tokens
        if top_p:
            request_data["top_p"] = top_p

        # Try primary model first
        for attempt_model in [model] + fallback_models:
            if attempt_model == model:
                logger.info(f"Attempting LLM request with primary model: {attempt_model}")
            else:
                logger.warning(f"Falling back to model: {attempt_model}")

            try:
                request_data["model"] = attempt_model
                response = await self.client.post("/chat/completions", json=request_data)

                if response.status_code == 200:
                    if stream:
                        return self._handle_stream_response(response)
                    else:
                        return response.json()
                else:
                    logger.error(f"LLM API error with {attempt_model}: {response.status_code} - {response.text}")
                    continue

            except httpx.TimeoutException:
                logger.error(f"Timeout with model {attempt_model}")
                continue
            except httpx.RequestError as e:
                logger.error(f"Request error with model {attempt_model}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error with model {attempt_model}: {e}")
                continue

        # All models failed
        raise LLMError(
            message="All LLM models failed to generate response",
            model_name=model,
            details={"attempted_models": [model] + fallback_models}
        )

    def _handle_stream_response(self, response):
        """Handle streaming response."""
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    async def function_calling(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        function_call: Union[str, Dict[str, Any]] = "auto",
        model: Optional[str] = None,
        temperature: float = 0.1,
        fallback_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response with function calling capabilities.

        Args:
            messages: List of message dictionaries
            functions: List of function definitions
            function_call: Function calling mode
            model: Model to use
            temperature: Sampling temperature
            fallback_models: List of fallback models

        Returns:
            Response with function call results
        """
        model = model or self.default_model
        fallback_models = fallback_models or self.available_models

        # Convert functions to tools format for OpenRouter/OpenAI compatibility
        tools = []
        if functions:
            for func in functions:
                tool = {
                    "type": "function",
                    "function": func
                }
                tools.append(tool)

        # Try OpenRouter/OpenAI tools format first, fallback to deprecated functions format
        request_data_openrouter = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": function_call if function_call != "auto" else "auto",
            "temperature": temperature,
        }

        # Fallback to deprecated OpenAI functions format for older models
        request_data_openai = {
            "model": model,
            "messages": messages,
            "functions": functions,
            "function_call": function_call,
            "temperature": temperature,
        }

        # Log the request for debugging
        logger.info(f"Attempting tool calling with OpenRouter format: {json.dumps(request_data_openrouter, indent=2)}")

        for attempt_model in [model] + fallback_models:
            try:
                request_data_openrouter["model"] = attempt_model
                logger.info(f"Attempting OpenRouter format with {attempt_model}")
                response = await self.client.post("/chat/completions", json=request_data_openrouter)

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"OpenRouter format successful with {attempt_model}")
                    return result
                else:
                    logger.error(f"OpenRouter format failed with {attempt_model}: {response.status_code}")
                    # Try fallback to standard OpenAI format
                    logger.info(f"Attempting fallback OpenAI format with {attempt_model}")
                    fallback_response = await self.client.post("/chat/completions", json=request_data_openai)
                    if fallback_response.status_code == 200:
                        fallback_result = fallback_response.json()
                        logger.info(f"OpenAI fallback successful with {attempt_model}")
                        return fallback_result
                    else:
                        logger.error(f"OpenAI fallback also failed with {attempt_model}: {fallback_response.status_code}")

            except Exception as e:
                logger.error(f"Tool calling error with {attempt_model}: {e}")
                continue

        raise LLMError(
            message="Tool calling failed with all models",
            model_name=model,
            details={"attempted_models": [model] + fallback_models}
        )

    async def get_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> List[float]:
        """
        Get text embedding using Cohere.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            List of embedding values
        """
        # This will be implemented in the EmbeddingService
        from app.services.embedding import EmbeddingService
        embedding_service = EmbeddingService()
        return await embedding_service.get_embedding(text, model)

    async def validate_api_key(self) -> bool:
        """
        Validate the OpenRouter API key.

        Returns:
            True if API key is valid
        """
        try:
            response = await self.client.get("/models")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False

    async def get_available_models(self) -> List[str]:
        """
        Get list of available models from OpenRouter.

        Returns:
            List of model names
        """
        try:
            response = await self.client.get("/models")
            if response.status_code == 200:
                models_data = response.json()
                return [model["id"] for model in models_data.get("data", [])]
            else:
                return self.available_models
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return self.available_models

    async def analyze_confidence(
        self,
        prompt: str,
        response: str,
        context: Optional[str] = None,
    ) -> float:
        """
        Analyze confidence level of an LLM response.

        Args:
            prompt: Original prompt
            response: LLM response
            context: Additional context

        Returns:
            Confidence score between 0 and 1
        """
        confidence_prompt = f"""
        Analyze the confidence level of the following AI response based on the given prompt.

        Prompt: {prompt}
        Response: {response}
        {f'Context: {context}' if context else ''}

        Rate the confidence on a scale of 0.0 to 1.0, where:
        - 0.0 = Very low confidence, response is uncertain or likely incorrect
        - 0.5 = Moderate confidence, response might be correct but has uncertainty
        - 1.0 = High confidence, response is very likely correct

        Consider:
        1. Clarity and specificity of the response
        2. Presence of hedging language ("might", "probably", "I think")
        3. Consistency with the prompt
        4. Completeness of the answer

        Return only a single number between 0.0 and 1.0.
        """

        try:
            messages = [
                {"role": "system", "content": "You are an AI confidence analyzer. Return only numerical confidence scores."},
                {"role": "user", "content": confidence_prompt}
            ]

            result = await self.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=10,
            )

            if "choices" in result and len(result["choices"]) > 0:
                confidence_text = result["choices"][0]["message"]["content"].strip()
                try:
                    confidence = float(confidence_text)
                    return max(0.0, min(1.0, confidence))  # Clamp between 0 and 1
                except ValueError:
                    logger.warning(f"Could not parse confidence score: {confidence_text}")
                    return 0.5  # Default to moderate confidence

            return 0.5

        except Exception as e:
            logger.error(f"Confidence analysis failed: {e}")
            return 0.5  # Default to moderate confidence