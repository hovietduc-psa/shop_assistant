"""
Unit tests for LLM Manager functionality.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime

from app.core.llm.llm_manager import LLMManager
from app.core.llm.prompt_templates import PromptManager


@pytest.mark.unit
class TestLLMManager:
    """Test suite for LLM Manager."""

    @pytest.fixture
    def llm_manager(self):
        """Create LLM manager instance for testing."""
        return LLMManager()

    @pytest.fixture
    def mock_openai_response(self, sample_llm_response):
        """Mock OpenAI API response."""
        return sample_llm_response

    @pytest.fixture
    def mock_openai_embedding_response(self, sample_embedding_response):
        """Mock OpenAI embedding API response."""
        return sample_embedding_response

    async def test_llm_manager_initialization(self, llm_manager):
        """Test LLM manager initialization."""
        assert llm_manager is not None
        assert hasattr(llm_manager, 'client')
        assert hasattr(llm_manager, 'embedding_client')
        assert llm_manager.default_model == "gpt-4"
        assert llm_manager.embedding_model == "text-embedding-ada-002"

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_success(
        self,
        mock_chat_create,
        llm_manager,
        mock_openai_response
    ):
        """Test successful LLM response generation."""
        # Setup mock
        mock_chat_create.return_value = mock_openai_response

        # Execute
        result = await llm_manager.generate_response(
            prompt="Test prompt",
            max_tokens=100,
            temperature=0.7
        )

        # Verify
        assert result is not None
        assert "content" in result
        assert result["content"] == "This is a test response from the LLM."
        assert result["model"] == "gpt-4"

        # Verify API was called correctly
        mock_chat_create.assert_called_once()
        call_args = mock_chat_create.call_args
        assert call_args[1]["model"] == "gpt-4"
        assert call_args[1]["messages"][0]["content"] == "Test prompt"
        assert call_args[1]["max_tokens"] == 100
        assert call_args[1]["temperature"] == 0.7

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_with_system_prompt(
        self,
        mock_chat_create,
        llm_manager,
        mock_openai_response
    ):
        """Test LLM response generation with system prompt."""
        mock_chat_create.return_value = mock_openai_response

        result = await llm_manager.generate_response(
            prompt="User message",
            system_prompt="You are a helpful assistant.",
            max_tokens=50
        )

        assert result is not None
        call_args = mock_chat_create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "User message"

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_rate_limit_error(
        self,
        mock_chat_create,
        llm_manager
    ):
        """Test handling of rate limit errors."""
        # Setup mock to raise rate limit error
        import openai
        mock_chat_create.side_effect = openai.error.RateLimitError(
            "Rate limit exceeded", response=MagicMock(), body={}
        )

        # Execute and verify exception
        with pytest.raises(openai.error.RateLimitError):
            await llm_manager.generate_response(prompt="Test prompt")

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_authentication_error(
        self,
        mock_chat_create,
        llm_manager
    ):
        """Test handling of authentication errors."""
        import openai
        mock_chat_create.side_effect = openai.error.AuthenticationError(
            "Invalid API key", response=MagicMock(), body={}
        )

        with pytest.raises(openai.error.AuthenticationError):
            await llm_manager.generate_response(prompt="Test prompt")

    @patch('app.core.llm.llm_manager.openai.Embedding.acreate')
    async def test_generate_embedding_success(
        self,
        mock_embedding_create,
        llm_manager,
        mock_openai_embedding_response
    ):
        """Test successful embedding generation."""
        mock_embedding_create.return_value = mock_openai_embedding_response

        result = await llm_manager.generate_embedding(
            text="This is a test text for embedding."
        )

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1536  # Standard OpenAI embedding size
        assert all(isinstance(x, float) for x in result)

        # Verify API was called correctly
        mock_embedding_create.assert_called_once()
        call_args = mock_embedding_create.call_args
        assert call_args[1]["model"] == "text-embedding-ada-002"
        assert call_args[1]["input"] == "This is a test text for embedding."

    @patch('app.core.llm.llm_manager.openai.Embedding.acreate')
    async def test_generate_embedding_batch(
        self,
        mock_embedding_create,
        llm_manager,
        mock_openai_embedding_response
    ):
        """Test embedding generation for multiple texts."""
        # Mock response for batch request
        batch_response = {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": [0.1] * 1536,
                    "index": 0
                },
                {
                    "object": "embedding",
                    "embedding": [0.2] * 1536,
                    "index": 1
                }
            ],
            "model": "text-embedding-ada-002",
            "usage": {"prompt_tokens": 16, "total_tokens": 16}
        }
        mock_embedding_create.return_value = batch_response

        texts = ["First text", "Second text"]
        results = await llm_manager.generate_embedding(texts)

        assert len(results) == 2
        assert all(isinstance(result, list) for result in results)
        assert all(len(result) == 1536 for result in results)

    async def test_generate_embedding_empty_input(self, llm_manager):
        """Test embedding generation with empty input."""
        with pytest.raises(ValueError, match="Text input cannot be empty"):
            await llm_manager.generate_embedding(text="")

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_with_retry(
        self,
        mock_chat_create,
        llm_manager,
        mock_openai_response
    ):
        """Test LLM response generation with retry logic."""
        # Setup mock to fail once, then succeed
        import openai
        mock_chat_create.side_effect = [
            openai.error.APIError("Temporary error", response=MagicMock(), body={}),
            mock_openai_response
        ]

        result = await llm_manager.generate_response(
            prompt="Test prompt",
            max_retries=2
        )

        assert result is not None
        assert result["content"] == "This is a test response from the LLM."
        assert mock_chat_create.call_count == 2

    @patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate')
    async def test_generate_response_max_retries_exceeded(
        self,
        mock_chat_create,
        llm_manager
    ):
        """Test LLM response generation when max retries exceeded."""
        import openai
        mock_chat_create.side_effect = openai.error.APIError(
            "Persistent error", response=MagicMock(), body={}
        )

        with pytest.raises(openai.error.APIError):
            await llm_manager.generate_response(
                prompt="Test prompt",
                max_retries=2
            )

        assert mock_chat_create.call_count == 3  # Initial attempt + 2 retries

    async def test_validate_prompt_parameters(self, llm_manager):
        """Test prompt parameter validation."""
        # Test invalid max_tokens
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            await llm_manager.generate_response(
                prompt="Test",
                max_tokens=0
            )

        # Test invalid temperature
        with pytest.raises(ValueError, match="temperature must be between 0 and 1"):
            await llm_manager.generate_response(
                prompt="Test",
                temperature=1.5
            )

        # Test invalid max_retries
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            await llm_manager.generate_response(
                prompt="Test",
                max_retries=-1
            )

    async def test_model_switching(self, llm_manager):
        """Test switching between different models."""
        with patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate') as mock_create:
            mock_create.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "model": "gpt-3.5-turbo"
            }

            # Test with different model
            await llm_manager.generate_response(
                prompt="Test",
                model="gpt-3.5-turbo"
            )

            call_args = mock_create.call_args
            assert call_args[1]["model"] == "gpt-3.5-turbo"

    async def test_response_format_validation(self, llm_manager):
        """Test response format validation."""
        with patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate') as mock_create:
            # Mock response with missing content
            mock_create.return_value = {
                "choices": [{"message": {}}],
                "model": "gpt-4"
            }

            result = await llm_manager.generate_response(prompt="Test")
            assert result is not None
            # Should handle missing content gracefully

    async def test_usage_tracking(self, llm_manager):
        """Test token usage tracking."""
        with patch('app.core.llm.llm_manager.openai.ChatCompletion.acreate') as mock_create:
            mock_create.return_value = {
                "choices": [{"message": {"content": "Response"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 15,
                    "total_tokens": 25
                },
                "model": "gpt-4"
            }

            result = await llm_manager.generate_response(prompt="Test")

            # Verify usage information is included
            assert "usage" in result
            assert result["usage"]["prompt_tokens"] == 10
            assert result["usage"]["completion_tokens"] == 15
            assert result["usage"]["total_tokens"] == 25


@pytest.mark.unit
class TestPromptManager:
    """Test suite for Prompt Manager."""

    @pytest.fixture
    def prompt_manager(self):
        """Create prompt manager instance for testing."""
        return PromptManager()

    def test_prompt_manager_initialization(self, prompt_manager):
        """Test prompt manager initialization."""
        assert prompt_manager is not None
        assert hasattr(prompt_manager, 'prompts')
        assert isinstance(prompt_manager.prompts, dict)

    def test_get_existing_prompt(self, prompt_manager):
        """Test getting an existing prompt."""
        # Add a test prompt
        prompt_manager.prompts["test_prompt"] = "Hello, {name}!"

        result = prompt_manager.get_prompt(
            "test_prompt",
            name="World"
        )

        assert result == "Hello, World!"

    def test_get_nonexistent_prompt(self, prompt_manager):
        """Test getting a non-existent prompt."""
        result = prompt_manager.get_prompt("nonexistent_prompt")

        # Should return the prompt name as fallback
        assert result == "nonexistent_prompt"

    def test_get_prompt_with_missing_variables(self, prompt_manager):
        """Test prompt with missing template variables."""
        prompt_manager.prompts["test_prompt"] = "Hello, {name}! Today is {day}."

        result = prompt_manager.get_prompt(
            "test_prompt",
            name="World"
            # Missing 'day' variable
        )

        # Should handle missing variables gracefully
        assert "Hello, World!" in result

    def test_add_custom_prompt(self, prompt_manager):
        """Test adding custom prompts."""
        custom_prompt = "Custom prompt for {purpose}."
        prompt_manager.add_prompt("custom", custom_prompt)

        result = prompt_manager.get_prompt("custom", purpose="testing")
        assert result == "Custom prompt for testing."

    def test_prompt_caching(self, prompt_manager):
        """Test that prompts are cached properly."""
        prompt_manager.prompts["cached_prompt"] = "This should be cached: {value}."

        # First call
        result1 = prompt_manager.get_prompt("cached_prompt", value=1)

        # Second call with same parameters
        result2 = prompt_manager.get_prompt("cached_prompt", value=1)

        assert result1 == result2
        assert result1 == "This should be cached: 1."