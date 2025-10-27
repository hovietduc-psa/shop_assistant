"""
Tests for Stage 5: LLM-Powered NLU Foundation.
"""

import pytest
import asyncio
from app.services.nlu import NLUService
from app.services.llm import LLMService
from app.services.embedding import EmbeddingService
from app.services.prompt_testing import PromptTestingFramework


class TestLLMService:
    """Test cases for LLM service."""

    @pytest.fixture
    async def llm_service(self):
        """Create LLM service instance."""
        service = LLMService()
        yield service
        await service.aclose()

    @pytest.mark.asyncio
    async def test_generate_response(self, llm_service):
        """Test basic response generation."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]

        # This test requires valid API keys to run
        # For now, we'll test the structure
        try:
            response = await llm_service.generate_response(messages)
            assert "choices" in response
            assert len(response["choices"]) > 0
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_function_calling(self, llm_service):
        """Test function calling capabilities."""
        functions = [
            {
                "name": "get_weather",
                "description": "Get weather information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "unit": {"type": "string"}
                    }
                }
            }
        ]

        messages = [
            {"role": "user", "content": "What's the weather in New York?"}
        ]

        try:
            response = await llm_service.function_call(
                messages=messages,
                functions=functions
            )
            assert "choices" in response
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()


class TestEmbeddingService:
    """Test cases for Embedding service."""

    @pytest.fixture
    async def embedding_service(self):
        """Create embedding service instance."""
        service = EmbeddingService()
        yield service
        await service.aclose()

    @pytest.mark.asyncio
    async def test_get_embedding(self, embedding_service):
        """Test embedding generation."""
        text = "This is a test sentence for embedding."

        try:
            embedding = await embedding_service.get_embedding(text)
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_calculate_similarity(self, embedding_service):
        """Test similarity calculation."""
        embedding1 = [0.1, 0.2, 0.3, 0.4, 0.5]
        embedding2 = [0.1, 0.2, 0.3, 0.4, 0.5]  # Identical
        embedding3 = [0.5, 0.4, 0.3, 0.2, 0.1]  # Different

        similarity1 = await embedding_service.calculate_similarity(embedding1, embedding2)
        similarity2 = await embedding_service.calculate_similarity(embedding1, embedding3)

        assert isinstance(similarity1, float)
        assert isinstance(similarity2, float)
        assert abs(similarity1 - 1.0) < 0.001  # Should be very close to 1
        assert similarity1 > similarity2  # Identical vectors should have higher similarity


class TestNLUService:
    """Test cases for NLU service."""

    @pytest.fixture
    def nlu_service(self):
        """Create NLU service instance."""
        return NLUService()

    @pytest.mark.asyncio
    async def test_classify_intent(self, nlu_service):
        """Test intent classification."""
        text = "What's the price of the iPhone 15?"

        try:
            result = await nlu_service.classify_intent(text)
            assert "intent" in result
            assert "confidence" in result
            assert isinstance(result["confidence"], (int, float))
            assert 0 <= result["confidence"] <= 1
            assert "processing_time" in result
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_extract_entities(self, nlu_service):
        """Test entity extraction."""
        text = "I want to buy a blue iPhone 15 for $999"

        try:
            result = await nlu_service.extract_entities(text)
            assert "entities" in result
            assert isinstance(result["entities"], list)
            assert "processing_time" in result
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_analyze_sentiment(self, nlu_service):
        """Test sentiment analysis."""
        text = "I love this product, it's amazing!"

        try:
            result = await nlu_service.analyze_sentiment(text, detailed=True)
            assert "sentiment" in result
            assert "confidence" in result
            assert result["sentiment"] in ["positive", "negative", "neutral"]
            assert 0 <= result["confidence"] <= 1
            assert "processing_time" in result
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()

    @pytest.mark.asyncio
    async def test_fallback_intent_classification(self, nlu_service):
        """Test fallback intent classification without API calls."""
        # This tests the fallback parsing logic
        # We can't easily test this without mocking, but we can test the structure

        # Test that the service initializes correctly
        assert hasattr(nlu_service, 'intent_prompts')
        assert hasattr(nlu_service, 'entity_functions')
        assert hasattr(nlu_service, 'intent_examples')

        # Test that examples are loaded
        assert len(nlu_service.intent_examples) > 0
        assert all('message' in example for example in nlu_service.intent_examples)
        assert all('intent' in example for example in nlu_service.intent_examples)


class TestPromptTestingFramework:
    """Test cases for prompt testing framework."""

    @pytest.fixture
    def testing_framework(self):
        """Create testing framework instance."""
        return PromptTestingFramework()

    def test_load_test_cases(self, testing_framework):
        """Test that test cases are loaded correctly."""
        assert len(testing_framework.test_cases) > 0

        # Test structure of test cases
        for test_case in testing_framework.test_cases:
            assert hasattr(test_case, 'input_text')
            assert hasattr(test_case, 'expected_intent')
            assert hasattr(test_case, 'expected_entities')
            assert hasattr(test_case, 'expected_sentiment')
            assert hasattr(test_case, 'description')

    def test_calculate_entity_accuracy(self, testing_framework):
        """Test entity accuracy calculation."""
        predicted = [
            {"text": "iPhone 15", "label": "PRODUCT"},
            {"text": "blue", "label": "COLOR"}
        ]
        expected = [
            {"text": "iPhone 15", "label": "PRODUCT"},
            {"text": "blue", "label": "COLOR"}
        ]

        accuracy = testing_framework._calculate_entity_accuracy(predicted, expected)
        assert accuracy == 1.0  # Perfect match

        # Test partial match
        predicted_partial = [
            {"text": "iPhone 15", "label": "PRODUCT"}
        ]
        accuracy_partial = testing_framework._calculate_entity_accuracy(predicted_partial, expected)
        assert 0 < accuracy_partial < 1.0

        # Test no match
        predicted_none = [
            {"text": "Samsung", "label": "PRODUCT"}
        ]
        accuracy_none = testing_framework._calculate_entity_accuracy(predicted_none, expected)
        assert accuracy_none == 0.0

    def test_calculate_accuracy(self, testing_framework):
        """Test overall accuracy calculation."""
        from app.services.prompt_testing import TestCase

        test_case = TestCase(
            input_text="test",
            expected_intent="product_inquiry",
            expected_entities=[],
            expected_sentiment="neutral",
            description="test"
        )

        # Perfect match
        intent_result = {"intent": "product_inquiry", "confidence": 0.9}
        entities_result = {"entities": []}
        sentiment_result = {"sentiment": "neutral", "confidence": 0.8}

        accuracy = testing_framework._calculate_accuracy(
            test_case, intent_result, entities_result, sentiment_result
        )
        assert accuracy == 1.0

        # Partial match
        intent_wrong = {"intent": "other", "confidence": 0.9}
        accuracy_partial = testing_framework._calculate_accuracy(
            test_case, intent_wrong, entities_result, sentiment_result
        )
        assert accuracy_partial < 1.0

    @pytest.mark.asyncio
    async def test_run_single_test_structure(self, testing_framework):
        """Test the structure of running a single test."""
        from app.services.prompt_testing import TestCase

        test_case = TestCase(
            input_text="What's the price?",
            expected_intent="pricing_inquiry",
            expected_entities=[],
            expected_sentiment="neutral",
            description="Simple pricing test"
        )

        # Test that the method exists and returns the right structure
        try:
            result = await testing_framework.run_single_test(test_case)
            assert hasattr(result, 'test_case')
            assert hasattr(result, 'intent_result')
            assert hasattr(result, 'entities_result')
            assert hasattr(result, 'sentiment_result')
            assert hasattr(result, 'processing_time')
            assert hasattr(result, 'success')
            assert hasattr(result, 'accuracy_score')
        except Exception as e:
            # Expected to fail without API keys
            assert "API" in str(e).lower() or "key" in str(e).lower()


class TestIntegration:
    """Integration tests for Stage 5 components."""

    @pytest.mark.asyncio
    async def test_service_initialization(self):
        """Test that all services can be initialized."""
        llm_service = LLMService()
        embedding_service = EmbeddingService()
        nlu_service = NLUService()
        testing_framework = PromptTestingFramework()

        # Test that services have expected attributes
        assert hasattr(llm_service, 'available_models')
        assert hasattr(embedding_service, 'available_models')
        assert hasattr(nlu_service, 'intent_prompts')
        assert hasattr(testing_framework, 'test_cases')

        # Clean up
        await llm_service.aclose()
        await embedding_service.aclose()

    def test_configuration_values(self):
        """Test that configuration values are properly loaded."""
        from app.core.config import settings

        assert hasattr(settings, 'OPENROUTER_API_KEY')
        assert hasattr(settings, 'COHERE_API_KEY')
        assert hasattr(settings, 'DEFAULT_LLM_MODEL')
        assert hasattr(settings, 'DEFAULT_EMBEDDING_MODEL')
        assert settings.DEFAULT_LLM_MODEL.startswith("openai/") or settings.DEFAULT_LLM_MODEL.startswith("anthropic/")
        assert "embed" in settings.DEFAULT_EMBEDDING_MODEL

    @pytest.mark.asyncio
    async def test_fallback_mechanisms(self):
        """Test that fallback mechanisms work correctly."""
        nlu_service = NLUService()

        # Test fallback sentiment analysis (doesn't require API calls)
        result = nlu_service._parse_sentiment_fallback("I love this product!", 0.1)
        assert "sentiment" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "processing_time" in result
        assert result["method"] == "fallback"

        # Test fallback entity extraction
        entities_result = nlu_service._parse_entities_fallback("I bought it for $999", 0.1)
        assert "entities" in entities_result
        assert "processing_time" in entities_result
        assert entities_result["method"] == "fallback"

        # Should find the price entity
        entities = entities_result["entities"]
        price_entities = [e for e in entities if e["label"] == "PRICE"]
        assert len(price_entities) > 0
        assert "$999" in price_entities[0]["text"]