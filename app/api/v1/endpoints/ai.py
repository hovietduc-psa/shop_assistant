"""
AI service endpoints.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.ai import (
    IntentRequest,
    IntentResponse,
    EntityRequest,
    EntityResponse,
    SentimentRequest,
    SentimentResponse
)
from app.services.nlu import NLUService
from app.services.llm import LLMService
from app.core.config import settings
from app.utils.exceptions import ExternalServiceError
from loguru import logger

router = APIRouter()

# Initialize services
nlu_service = NLUService()
llm_service = LLMService()


@router.post("/intent", response_model=IntentResponse)
async def classify_intent(
    request: IntentRequest,
    db: Session = Depends(get_db)
):
    """
    Classify user intent using AI.
    """
    try:
        # Use NLU service for intent classification
        result = await nlu_service.classify_intent(
            text=request.text,
            context=request.context,
            use_few_shot=True,
            alternatives_count=3
        )

        return IntentResponse(
            intent=result["intent"],
            confidence=result["confidence"],
            alternatives=result.get("alternatives", []),
            model=result.get("model_used", settings.DEFAULT_LLM_MODEL),
            processing_time=result.get("processing_time", 0.0)
        )

    except ExternalServiceError as e:
        logger.error(f"External service error in intent classification: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        raise HTTPException(status_code=500, detail="Intent classification failed")


@router.post("/entities", response_model=EntityResponse)
async def extract_entities(
    request: EntityRequest,
    db: Session = Depends(get_db)
):
    """
    Extract entities from text using AI.
    """
    try:
        # Use NLU service for entity extraction
        result = await nlu_service.extract_entities(
            text=request.text,
            context={"entity_types": request.entity_types} if request.entity_types else None,
            entity_types=request.entity_types
        )

        return EntityResponse(
            entities=result.get("entities", []),
            model=result.get("model_used", settings.DEFAULT_LLM_MODEL),
            processing_time=result.get("processing_time", 0.0)
        )

    except ExternalServiceError as e:
        logger.error(f"External service error in entity extraction: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        raise HTTPException(status_code=500, detail="Entity extraction failed")


@router.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(
    request: SentimentRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment of text using AI.
    """
    try:
        # Use NLU service for sentiment analysis
        result = await nlu_service.analyze_sentiment(
            text=request.text,
            detailed=request.detailed
        )

        return SentimentResponse(
            sentiment=result["sentiment"],
            confidence=result["confidence"],
            emotions=result.get("emotions"),
            model=result.get("model_used", settings.DEFAULT_LLM_MODEL),
            processing_time=result.get("processing_time", 0.0)
        )

    except ExternalServiceError as e:
        logger.error(f"External service error in sentiment analysis: {e}")
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable")
    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Sentiment analysis failed")


@router.post("/classify-text")
async def classify_text(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Comprehensive text analysis using multiple AI services.
    """
    text = request.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # Run all analyses in parallel
        results = await asyncio.gather(
            nlu_service.classify_intent(text=text),
            nlu_service.extract_entities(text=text),
            nlu_service.analyze_sentiment(text=text, detailed=True),
            return_exceptions=True
        )

        # Process results
        intent_result = results[0] if not isinstance(results[0], Exception) else {"intent": "other", "confidence": 0.0}
        entities_result = results[1] if not isinstance(results[1], Exception) else {"entities": []}
        sentiment_result = results[2] if not isinstance(results[2], Exception) else {"sentiment": "neutral", "confidence": 0.0}

        return {
            "text": text,
            "intent": intent_result,
            "entities": entities_result.get("entities", []),
            "sentiment": sentiment_result,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "processing_summary": {
                "intent_processing_time": intent_result.get("processing_time", 0.0),
                "entities_processing_time": entities_result.get("processing_time", 0.0),
                "sentiment_processing_time": sentiment_result.get("processing_time", 0.0),
                "total_processing_time": sum([
                    intent_result.get("processing_time", 0.0),
                    entities_result.get("processing_time", 0.0),
                    sentiment_result.get("processing_time", 0.0)
                ])
            }
        }

    except Exception as e:
        logger.error(f"Comprehensive text analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Text analysis failed")


@router.post("/models/validate")
async def validate_ai_models():
    """
    Validate AI model connections and API keys.
    """
    validation_results = {}

    try:
        # Validate OpenRouter
        openrouter_valid = await llm_service.validate_api_key()
        validation_results["openrouter"] = {
            "status": "valid" if openrouter_valid else "invalid",
            "message": "API key is working" if openrouter_valid else "API key validation failed"
        }
    except Exception as e:
        validation_results["openrouter"] = {
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }

    try:
        # Validate Cohere
        async with nlu_service.embedding_service as embedding_service:
            cohere_valid = await embedding_service.validate_api_key()
            validation_results["cohere"] = {
                "status": "valid" if cohere_valid else "invalid",
                "message": "API key is working" if cohere_valid else "API key validation failed"
            }
    except Exception as e:
        validation_results["cohere"] = {
            "status": "error",
            "message": f"Validation error: {str(e)}"
        }

    # Overall status
    all_valid = all(result["status"] == "valid" for result in validation_results.values())
    validation_results["overall"] = {
        "status": "healthy" if all_valid else "degraded",
        "message": "All AI services operational" if all_valid else "Some AI services have issues"
    }

    return validation_results


@router.get("/models/available")
async def get_available_models():
    """
    Get list of available AI models.
    """
    try:
        # Get available OpenRouter models
        openrouter_models = await llm_service.get_available_models()

        return {
            "openrouter_models": openrouter_models,
            "embedding_models": nlu_service.embedding_service.available_models,
            "default_llm_model": settings.DEFAULT_LLM_MODEL,
            "default_embedding_model": settings.DEFAULT_EMBEDDING_MODEL,
            "retrieved_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get available models: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model information")


@router.post("/test/prompt")
async def test_prompt(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Test a custom prompt with the LLM.
    """
    prompt = request.get("prompt", "")
    model = request.get("model", settings.DEFAULT_LLM_MODEL)
    temperature = request.get("temperature", 0.7)
    max_tokens = request.get("max_tokens", 500)

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        messages = [
            {"role": "user", "content": prompt}
        ]

        response = await llm_service.generate_response(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )

        if "choices" in response and len(response["choices"]) > 0:
            content = response["choices"][0]["message"]["content"]
            return {
                "prompt": prompt,
                "response": content,
                "model": response.get("model", model),
                "usage": response.get("usage", {}),
                "test_timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="No response generated")

    except Exception as e:
        logger.error(f"Prompt test failed: {e}")
        raise HTTPException(status_code=500, detail="Prompt test failed")


# Import asyncio for parallel processing
import asyncio


@router.post("/test/prompts")
async def test_prompts(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Run prompt testing and optimization.
    """
    try:
        from app.services.prompt_testing import PromptTestingFramework

        testing_framework = PromptTestingFramework()

        test_type = request.get("test_type", "full_suite")
        models = request.get("models", [settings.DEFAULT_LLM_MODEL])

        if test_type == "full_suite":
            results = await testing_framework.run_test_suite()
        elif test_type == "model_comparison":
            results = await testing_framework.compare_models(models)
        elif test_type == "prompt_optimization":
            # This would require more detailed implementation
            results = {"message": "Prompt optimization not yet implemented"}
        else:
            raise HTTPException(status_code=400, detail="Invalid test type")

        return results

    except Exception as e:
        logger.error(f"Prompt testing failed: {e}")
        raise HTTPException(status_code=500, detail="Prompt testing failed")


@router.post("/recommendations")
async def get_recommendations(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Get product recommendations using AI.
    """
    # TODO: Implement actual recommendation system
    return {
        "recommendations": [
            {
                "product_id": "prod_1",
                "name": "iPhone 15 Pro",
                "score": 0.92,
                "reason": "Based on your interest in smartphones"
            }
        ],
        "model": settings.DEFAULT_LLM_MODEL,
        "processing_time": 0.8
    }


@router.post("/summarize")
async def summarize_text(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Summarize text using AI.
    """
    text = request.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant that summarizes text concisely and accurately. Provide a clear, brief summary of the main points."
            },
            {
                "role": "user",
                "content": f"Please summarize this text: {text}"
            }
        ]

        response = await llm_service.generate_response(
            messages=messages,
            temperature=0.3,
            max_tokens=200
        )

        if "choices" in response and len(response["choices"]) > 0:
            summary = response["choices"][0]["message"]["content"]
            return {
                "summary": summary,
                "original_length": len(text),
                "model": response.get("model", settings.DEFAULT_LLM_MODEL),
                "processing_time": response.get("processing_time", 0.0)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate summary")

    except Exception as e:
        logger.error(f"Text summarization failed: {e}")
        raise HTTPException(status_code=500, detail="Text summarization failed")