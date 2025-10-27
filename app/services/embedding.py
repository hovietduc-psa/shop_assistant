"""
Embedding service for Cohere integration and vector operations.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Union
import httpx
from loguru import logger
from app.core.config import settings
from app.utils.exceptions import ExternalServiceError, LLMError


class EmbeddingService:
    """Service for managing text embeddings using Cohere."""

    def __init__(self):
        self.api_key = settings.COHERE_API_KEY
        self.base_url = settings.COHERE_BASE_URL
        self.default_model = settings.DEFAULT_EMBEDDING_MODEL
        self.timeout = 30.0

        # Available embedding models
        self.available_models = [
            "embed-english-v3.0",
            "embed-english-light-v3.0",
            "embed-multilingual-v3.0",
            "embed-multilingual-light-v3.0",
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

    async def get_embedding(
        self,
        text: str,
        model: Optional[str] = None,
        input_type: str = "search_document",
        truncate: str = "END",
    ) -> List[float]:
        """
        Get embedding for a single text.

        Args:
            text: Text to embed
            model: Embedding model to use
            input_type: Type of input ('search_document', 'search_query', 'classification')
            truncate: How to handle long texts ('NONE', 'START', 'END')

        Returns:
            List of embedding values
        """
        model = model or self.default_model

        try:
            request_data = {
                "texts": [text],
                "model": model,
                "input_type": input_type,
                "truncate": truncate,
            }

            response = await self.client.post("/embed", json=request_data)

            if response.status_code == 200:
                result = response.json()
                if "embeddings" in result and len(result["embeddings"]) > 0:
                    return result["embeddings"][0]
                else:
                    raise LLMError(
                        message="No embeddings returned from Cohere",
                        model_name=model,
                        details={"response": result}
                    )
            else:
                raise ExternalServiceError(
                    message=f"Cohere API error: {response.status_code}",
                    service_name="Cohere",
                    details={"response": response.text}
                )

        except httpx.TimeoutException:
            raise ExternalServiceError(
                message="Cohere API timeout",
                service_name="Cohere"
            )
        except httpx.RequestError as e:
            raise ExternalServiceError(
                message=f"Cohere API request error: {e}",
                service_name="Cohere"
            )
        except Exception as e:
            if isinstance(e, (ExternalServiceError, LLMError)):
                raise
            raise LLMError(
                message=f"Unexpected error in embedding generation: {e}",
                model_name=model
            )

    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        input_type: str = "search_document",
        truncate: str = "END",
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        Get embeddings for multiple texts (batch processing).

        Args:
            texts: List of texts to embed
            model: Embedding model to use
            input_type: Type of input
            truncate: How to handle long texts
            batch_size: Batch size for processing

        Returns:
            List of embedding lists
        """
        model = model or self.default_model
        all_embeddings = []

        # Process in batches to handle large lists
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            try:
                request_data = {
                    "texts": batch_texts,
                    "model": model,
                    "input_type": input_type,
                    "truncate": truncate,
                }

                response = await self.client.post("/embed", json=request_data)

                if response.status_code == 200:
                    result = response.json()
                    if "embeddings" in result:
                        all_embeddings.extend(result["embeddings"])
                    else:
                        raise LLMError(
                            message="No embeddings returned from Cohere",
                            model_name=model,
                            details={"response": result}
                        )
                else:
                    raise ExternalServiceError(
                        message=f"Cohere API error: {response.status_code}",
                        service_name="Cohere",
                        details={"response": response.text}
                    )

            except Exception as e:
                logger.error(f"Batch embedding failed at index {i}: {e}")
                # For failed batches, we could retry or return empty embeddings
                # For now, raise the error
                raise

        return all_embeddings

    async def calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score between -1 and 1
        """
        try:
            import numpy as np

            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)

        except ImportError:
            # Fallback without numpy
            return self._cosine_similarity_no_numpy(embedding1, embedding2)
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0

    def _cosine_similarity_no_numpy(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Calculate cosine similarity without numpy (fallback).

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            Cosine similarity score
        """
        if len(embedding1) != len(embedding2):
            return 0.0

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(embedding1, embedding2))

        # Calculate magnitudes
        norm1 = sum(a * a for a in embedding1) ** 0.5
        norm2 = sum(b * b for b in embedding2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    async def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find most similar embeddings to a query.

        Args:
            query_embedding: Query embedding
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return

        Returns:
            List of dictionaries with similarity scores and indices
        """
        similarities = []

        for i, candidate_embedding in enumerate(candidate_embeddings):
            similarity = await self.calculate_similarity(query_embedding, candidate_embedding)
            similarities.append({
                "index": i,
                "similarity": similarity,
                "embedding": candidate_embedding
            })

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # Return top_k results
        return similarities[:top_k]

    async def validate_api_key(self) -> bool:
        """
        Validate the Cohere API key.

        Returns:
            True if API key is valid
        """
        try:
            # Try to embed a simple test text
            test_embedding = await self.get_embedding("test")
            return len(test_embedding) > 0
        except Exception as e:
            logger.error(f"Cohere API key validation failed: {e}")
            return False

    async def get_model_info(self, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about an embedding model.

        Args:
            model: Model name (defaults to default model)

        Returns:
            Model information dictionary
        """
        model = model or self.default_model

        # This would typically come from Cohere's API documentation
        # For now, return known information
        model_info = {
            "embed-english-v3.0": {
                "dimensions": 1024,
                "max_input_chars": 2048,
                "languages": ["en"],
                "description": "English embedding model"
            },
            "embed-english-light-v3.0": {
                "dimensions": 384,
                "max_input_chars": 2048,
                "languages": ["en"],
                "description": "Light English embedding model"
            },
            "embed-multilingual-v3.0": {
                "dimensions": 1024,
                "max_input_chars": 2048,
                "languages": ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"],
                "description": "Multilingual embedding model"
            },
            "embed-multilingual-light-v3.0": {
                "dimensions": 384,
                "max_input_chars": 2048,
                "languages": ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"],
                "description": "Light multilingual embedding model"
            }
        }

        return model_info.get(model, {
            "dimensions": "unknown",
            "max_input_chars": 2048,
            "languages": ["en"],
            "description": "Unknown model"
        })