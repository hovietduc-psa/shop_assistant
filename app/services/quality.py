"""
Conversation quality assessment and analytics service.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from app.services.llm import LLMService
from app.services.dialogue import DialogueContext, DialogueState
from app.services.memory import ConversationMemoryManager
from app.utils.exceptions import LLMError


class QualityDimension(Enum):
    """Quality assessment dimensions."""
    CLARITY = "clarity"
    HELPFULNESS = "helpfulness"
    EFFICIENCY = "efficiency"
    SATISFACTION = "satisfaction"
    RESOLUTION = "resolution"
    ENGAGEMENT = "engagement"
    PROFESSIONALISM = "professionalism"


@dataclass
class QualityScore:
    """Individual quality dimension score."""
    dimension: QualityDimension
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    reasoning: str
    improvement_suggestions: List[str]


@dataclass
class ConversationQualityReport:
    """Comprehensive conversation quality assessment."""
    conversation_id: str
    overall_score: float
    dimension_scores: List[QualityScore]
    conversation_summary: str
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    metrics: Dict[str, Any]
    assessed_at: datetime
    assessment_method: str


class ConversationQualityAssessor:
    """Assesses conversation quality using LLM analysis."""

    def __init__(self):
        self.llm_service = LLMService()
        self.memory_manager = ConversationMemoryManager()

        # Quality assessment prompts
        self.assessment_prompts = self._load_assessment_prompts()

        # Quality dimensions and their weights
        self.dimension_weights = {
            QualityDimension.CLARITY: 0.15,
            QualityDimension.HELPFULNESS: 0.20,
            QualityDimension.EFFICIENCY: 0.15,
            QualityDimension.SATISFACTION: 0.20,
            QualityDimension.RESOLUTION: 0.15,
            QualityDimension.ENGAGEMENT: 0.10,
            QualityDimension.PROFESSIONALISM: 0.05
        }

        # Benchmark scores for comparison
        self.benchmarks = {
            "overall": 0.75,
            QualityDimension.CLARITY: 0.80,
            QualityDimension.HELPFULNESS: 0.75,
            QualityDimension.EFFICIENCY: 0.70,
            QualityDimension.SATISFACTION: 0.75,
            QualityDimension.RESOLUTION: 0.70,
            QualityDimension.ENGAGEMENT: 0.65,
            QualityDimension.PROFESSIONALISM: 0.85
        }

    def _load_assessment_prompts(self) -> Dict[str, str]:
        """Load quality assessment prompt templates."""
        return {
            "overall_assessment": """You are an expert in customer service quality assessment.

Analyze the following conversation and assess its overall quality. Consider:
1. Communication clarity and understanding
2. Helpfulness and relevance of responses
3. Efficiency in resolving issues
4. Customer satisfaction indicators
5. Problem resolution effectiveness
6. Engagement and conversation flow
7. Professionalism and tone

Provide a detailed assessment with specific examples from the conversation.""",

            "dimension_assessment": """Assess a specific quality dimension of this conversation.

Focus on: {dimension}

Provide:
1. A score between 0.0 (poor) and 1.0 (excellent)
2. Confidence in your assessment (0.0 to 1.0)
3. Reasoning with specific examples
4. 2-3 improvement suggestions

Be objective and constructive in your assessment.""",

            "conversation_summary": """Summarize this conversation for quality assessment purposes.

Include:
1. Main purpose and goals
2. Key topics discussed
3. Resolution status
4. Communication patterns
5. Notable positive and negative moments
6. Overall conversation flow

Keep it concise but comprehensive enough for quality evaluation.""",

            "recommendations": """Based on your quality assessment, provide actionable recommendations for improvement.

Consider:
1. Specific communication improvements
2. Process or workflow changes
3. Training needs
4. System or tool enhancements
5. Best practices to implement

Provide 3-5 concrete, actionable recommendations."""
        }

    async def assess_conversation_quality(
        self,
        conversation_id: str,
        context: Optional[DialogueContext] = None,
        use_llm_assessment: bool = True
    ) -> ConversationQualityReport:
        """Comprehensive conversation quality assessment."""
        try:
            start_time = time.time()

            # Get conversation data
            if context is None:
                # Load from memory
                memory = await self.memory_manager.load_conversation(conversation_id)
                if not memory:
                    return self._create_empty_report(conversation_id, "Conversation not found")
            else:
                # Build memory from context
                memory = await self._build_memory_from_context(context)

            if use_llm_assessment:
                # LLM-based assessment
                report = await self._llm_quality_assessment(conversation_id, memory)
            else:
                # Rule-based assessment
                report = await self._rule_based_assessment(conversation_id, memory)

            # Add processing time
            report.metrics["assessment_processing_time"] = time.time() - start_time

            return report

        except Exception as e:
            logger.error(f"Quality assessment failed for {conversation_id}: {e}")
            return self._create_empty_report(conversation_id, f"Assessment failed: {str(e)}")

    async def _llm_quality_assessment(
        self,
        conversation_id: str,
        memory: Any
    ) -> ConversationQualityReport:
        """Perform LLM-based quality assessment."""
        try:
            # Generate conversation summary
            summary = await self._generate_conversation_summary(memory)

            # Assess each quality dimension
            dimension_scores = []
            for dimension in QualityDimension:
                score = await self._assess_dimension(memory, dimension)
                dimension_scores.append(score)

            # Calculate overall score
            overall_score = self._calculate_overall_score(dimension_scores)

            # Generate strengths and weaknesses
            strengths_weaknesses = await self._analyze_strengths_weaknesses(memory, dimension_scores)

            # Generate recommendations
            recommendations = await self._generate_recommendations(memory, dimension_scores)

            return ConversationQualityReport(
                conversation_id=conversation_id,
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                conversation_summary=summary,
                strengths=strengths_weaknesses["strengths"],
                weaknesses=strengths_weaknesses["weaknesses"],
                recommendations=recommendations,
                metrics=self._calculate_metrics(memory, dimension_scores),
                assessed_at=datetime.utcnow(),
                assessment_method="llm_based"
            )

        except Exception as e:
            logger.error(f"LLM quality assessment failed: {e}")
            raise

    async def _rule_based_assessment(
        self,
        conversation_id: str,
        memory: Any
    ) -> ConversationQualityReport:
        """Perform rule-based quality assessment."""
        try:
            # Rule-based dimension scoring
            dimension_scores = []

            for dimension in QualityDimension:
                score = self._rule_based_dimension_score(memory, dimension)
                dimension_scores.append(score)

            # Calculate overall score
            overall_score = self._calculate_overall_score(dimension_scores)

            # Generate simple summary
            summary = f"Conversation with {memory.message_count} messages, final state: {memory.final_state.value}"

            # Basic strengths and weaknesses
            strengths, weaknesses = self._rule_based_strengths_weaknesses(memory, dimension_scores)

            # Simple recommendations
            recommendations = self._rule_based_recommendations(memory, dimension_scores)

            return ConversationQualityReport(
                conversation_id=conversation_id,
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                conversation_summary=summary,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                metrics=self._calculate_metrics(memory, dimension_scores),
                assessed_at=datetime.utcnow(),
                assessment_method="rule_based"
            )

        except Exception as e:
            logger.error(f"Rule-based quality assessment failed: {e}")
            raise

    async def _generate_conversation_summary(self, memory: Any) -> str:
        """Generate conversation summary for assessment."""
        try:
            # Build conversation text for summarization
            conversation_text = self._build_conversation_text(memory)

            messages = [
                {"role": "system", "content": self.assessment_prompts["conversation_summary"]},
                {"role": "user", "content": f"Summarize this conversation:\n\n{conversation_text}"}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )

            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                return f"Conversation with {memory.message_count} messages about {memory.topics_discussed}"

        except Exception as e:
            logger.error(f"Conversation summarization failed: {e}")
            return "Summary generation failed"

    async def _assess_dimension(
        self,
        memory: Any,
        dimension: QualityDimension
    ) -> QualityScore:
        """Assess a specific quality dimension."""
        try:
            conversation_text = self._build_conversation_text(memory)

            prompt = self.assessment_prompts["dimension_assessment"].format(
                dimension=dimension.value
            )
            prompt += f"\n\nConversation:\n{conversation_text}"

            messages = [
                {"role": "system", "content": "You are a customer service quality expert. Always provide structured, objective assessments."},
                {"role": "user", "content": prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=400
            )

            if "choices" in response and len(response["choices"]) > 0:
                content = response["choices"][0]["message"]["content"]
                return self._parse_dimension_assessment(content, dimension)
            else:
                return self._get_fallback_dimension_score(dimension)

        except Exception as e:
            logger.error(f"Dimension assessment failed for {dimension.value}: {e}")
            return self._get_fallback_dimension_score(dimension)

    def _parse_dimension_assessment(
        self,
        content: str,
        dimension: QualityDimension
    ) -> QualityScore:
        """Parse LLM response for dimension assessment."""
        try:
            # Try to extract structured information
            lines = content.split('\n')
            score = 0.5
            confidence = 0.5
            reasoning = content
            suggestions = []

            for line in lines:
                if "score:" in line.lower():
                    try:
                        score = float(line.split(":")[-1].strip())
                        score = max(0.0, min(1.0, score))  # Clamp between 0 and 1
                    except ValueError:
                        pass
                elif "confidence:" in line.lower():
                    try:
                        confidence = float(line.split(":")[-1].strip())
                        confidence = max(0.0, min(1.0, confidence))
                    except ValueError:
                        pass
                elif "suggestion" in line.lower() or "improvement" in line.lower():
                    suggestions.append(line.strip())

            return QualityScore(
                dimension=dimension,
                score=score,
                confidence=confidence,
                reasoning=reasoning,
                improvement_suggestions=suggestions[:3]  # Limit to 3 suggestions
            )

        except Exception as e:
            logger.error(f"Failed to parse dimension assessment: {e}")
            return self._get_fallback_dimension_score(dimension)

    def _get_fallback_dimension_score(
        self,
        dimension: QualityDimension
    ) -> QualityScore:
        """Get fallback dimension score based on rules."""
        fallback_scores = {
            QualityDimension.CLARITY: (0.7, "Moderate clarity", ["Use clearer language"]),
            QualityDimension.HELPFULNESS: (0.6, "Somewhat helpful", ["Provide more specific help"]),
            QualityDimension.EFFICIENCY: (0.5, "Average efficiency", ["Work on faster resolution"]),
            QualityDimension.SATISFACTION: (0.6, "Moderate satisfaction", ["Focus on customer needs"]),
            QualityDimension.RESOLUTION: (0.5, "Partial resolution", ["Ensure complete resolution"]),
            QualityDimension.ENGAGEMENT: (0.6, "Moderate engagement", ["Maintain better engagement"]),
            QualityDimension.PROFESSIONALISM: (0.8, "Good professionalism", ["Maintain professional tone"])
        }

        score, reasoning, suggestions = fallback_scores.get(dimension, (0.5, "Unknown dimension", ["Improve overall quality"]))

        return QualityScore(
            dimension=dimension,
            score=score,
            confidence=0.3,  # Low confidence for fallback
            reasoning=reasoning,
            improvement_suggestions=suggestions
        )

    def _rule_based_dimension_score(
        self,
        memory: Any,
        dimension: QualityDimension
    ) -> QualityScore:
        """Calculate dimension score using rules."""
        score = 0.5  # Default score
        reasoning = "Rule-based assessment"
        suggestions = []

        if dimension == QualityDimension.CLARITY:
            # Assess based on message length variability, entity extraction, etc.
            score = min(0.9, 0.5 + len(memory.entities) * 0.1)
            reasoning = f"Score based on {len(memory.entities)} extracted entities"
            if score < 0.7:
                suggestions.append("Improve message clarity and structure")

        elif dimension == QualityDimension.HELPFULNESS:
            # Assess based on resolved topics vs goals
            if memory.topics_discussed and memory.resolved_topics:
                resolution_rate = len(memory.resolved_topics) / len(memory.topics_discussed)
                score = min(0.9, 0.4 + resolution_rate * 0.5)
                reasoning = f"Based on resolution rate: {resolution_rate:.2%}"
            if score < 0.7:
                suggestions.append("Focus on more helpful and actionable responses")

        elif dimension == QualityDimension.EFFICIENCY:
            # Assess based on message count vs resolution
            if memory.message_count > 0:
                efficiency = min(1.0, len(memory.resolved_topics) / memory.message_count)
                score = 0.5 + efficiency * 0.4
                reasoning = f"Based on messages per resolution: {memory.message_count} messages"
            if score < 0.7:
                suggestions.append("Work on faster resolution with fewer messages")

        elif dimension == QualityDimension.SATISFACTION:
            # Assess based on sentiment timeline
            if memory.sentiment_timeline:
                positive_sentiments = [s for _, s in memory.sentiment_timeline if s == "positive"]
                negative_sentiments = [s for _, s in memory.sentiment_timeline if s == "negative"]
                total_sentiments = len(memory.sentiment_timeline)

                if total_sentiments > 0:
                    satisfaction = (len(positive_sentiments) - len(negative_sentiments)) / total_sentiments
                    score = max(0.0, min(1.0, 0.5 + satisfaction * 0.5))
                    reasoning = f"Based on sentiment analysis: {len(positive_sentiments)} positive, {len(negative_sentiments)} negative"
            if score < 0.7:
                suggestions.append("Focus on improving customer satisfaction")

        elif dimension == QualityDimension.RESOLUTION:
            # Assess based on final state and resolved topics
            if memory.final_state == DialogueState.CONCLUSION:
                score = 0.8
                reasoning = "Conversation reached conclusion state"
            elif memory.resolution_status == "completed":
                score = 0.9
                reasoning = "Conversation marked as completed"
            else:
                score = 0.4
                reasoning = "Conversation did not reach completion"
                suggestions.append("Focus on proper conversation resolution")

        elif dimension == QualityDimension.ENGAGEMENT:
            # Assess based on message flow and response patterns
            score = min(0.8, 0.4 + (memory.message_count / 20) * 0.4)
            reasoning = f"Based on conversation length: {memory.message_count} messages"
            if score < 0.7:
                suggestions.append("Improve engagement through better conversation flow")

        elif dimension == QualityDimension.PROFESSIONALISM:
            # Assume good professionalism unless evidence suggests otherwise
            score = 0.85
            reasoning = "Assumed professional conduct"
            suggestions.append("Maintain professional communication standards")

        return QualityScore(
            dimension=dimension,
            score=score,
            confidence=0.4,  # Medium confidence for rule-based
            reasoning=reasoning,
            improvement_suggestions=suggestions
        )

    def _calculate_overall_score(self, dimension_scores: List[QualityScore]) -> float:
        """Calculate overall quality score from dimension scores."""
        weighted_sum = 0.0
        total_weight = 0.0

        for score in dimension_scores:
            weight = self.dimension_weights.get(score.dimension, 0.1)
            weighted_sum += score.score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    async def _analyze_strengths_weaknesses(
        self,
        memory: Any,
        dimension_scores: List[QualityScore]
    ) -> Dict[str, List[str]]:
        """Analyze conversation strengths and weaknesses."""
        strengths = []
        weaknesses = []

        # High-scoring dimensions as strengths
        for score in dimension_scores:
            if score.score >= 0.8:
                strengths.append(f"Strong {score.dimension.value}: {score.reasoning}")
            elif score.score < 0.6:
                weaknesses.append(f"Needs improvement in {score.dimension.value}: {score.reasoning}")

        # Add general strengths and weaknesses
        if memory.resolution_status == "completed":
            strengths.append("Successfully resolved customer issue")
        elif memory.resolution_status == "active":
            weaknesses.append("Conversation not yet resolved")

        if memory.message_count > 10:
            strengths.append("Thorough conversation with adequate detail")
        elif memory.message_count < 3:
            weaknesses.append("Very brief conversation, may need more engagement")

        return {"strengths": strengths, "weaknesses": weaknesses}

    def _rule_based_strengths_weaknesses(
        self,
        memory: Any,
        dimension_scores: List[QualityScore]
    ) -> Tuple[List[str], List[str]]:
        """Rule-based strengths and weaknesses analysis."""
        strengths = []
        weaknesses = []

        for score in dimension_scores:
            if score.score >= 0.8:
                strengths.append(f"Good {score.dimension.value}")
            elif score.score < 0.6:
                weaknesses.append(f"Needs improvement in {score.dimension.value}")

        return strengths, weaknesses

    async def _generate_recommendations(
        self,
        memory: Any,
        dimension_scores: List[QualityScore]
    ) -> List[str]:
        """Generate improvement recommendations."""
        try:
            # Focus on lowest-scoring dimensions
            low_scoring = sorted(dimension_scores, key=lambda x: x.score)[:3]

            recommendations = []
            for score in low_scoring:
                if score.score < 0.7:
                    recommendations.extend(score.improvement_suggestions)

            # Add general recommendations
            if memory.resolution_status != "completed":
                recommendations.append("Ensure all conversations reach proper resolution")

            if len(memory.key_points) == 0:
                recommendations.append("Document key conversation points for future reference")

            return list(set(recommendations[:5]))  # Remove duplicates and limit to 5

        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return ["Focus on improving overall conversation quality"]

    def _rule_based_recommendations(
        self,
        memory: Any,
        dimension_scores: List[QualityScore]
    ) -> List[str]:
        """Rule-based recommendation generation."""
        recommendations = []

        # Recommendations based on low-scoring dimensions
        for score in dimension_scores:
            if score.score < 0.6:
                if score.dimension == QualityDimension.HELPFULNESS:
                    recommendations.append("Provide more specific and actionable help")
                elif score.dimension == QualityDimension.EFFICIENCY:
                    recommendations.append("Work on faster issue resolution")
                elif score.dimension == QualityDimension.RESOLUTION:
                    recommendations.append("Ensure conversations reach proper completion")
                else:
                    recommendations.append(f"Improve {score.dimension.value}")

        # General recommendations
        if memory.message_count > 15:
            recommendations.append("Consider summarizing long conversations")
        elif memory.message_count < 3:
            recommendations.append("Ensure adequate conversation engagement")

        return recommendations[:5]

    def _calculate_metrics(
        self,
        memory: Any,
        dimension_scores: List[QualityScore]
    ) -> Dict[str, Any]:
        """Calculate quality metrics."""
        metrics = {
            "dimension_scores": {
                score.dimension.value: {
                    "score": score.score,
                    "confidence": score.confidence,
                    "benchmark": self.benchmarks.get(score.dimension, 0.7)
                }
                for score in dimension_scores
            },
            "benchmark_comparison": {
                "overall_benchmark": self.benchmarks["overall"],
                "above_benchmark": sum(1 for s in dimension_scores if s.score >= self.benchmarks.get(s.dimension, 0.7)),
                "below_benchmark": sum(1 for s in dimension_scores if s.score < self.benchmarks.get(s.dimension, 0.7))
            },
            "conversation_metrics": {
                "message_count": memory.message_count,
                "topics_discussed": len(memory.topics_discussed),
                "resolved_topics": len(memory.resolved_topics),
                "entities_extracted": len(memory.entities),
                "resolution_rate": len(memory.resolved_topics) / max(len(memory.topics_discussed), 1) if memory.topics_discussed else 0.0
            }
        }

        return metrics

    def _build_conversation_text(self, memory: Any) -> str:
        """Build conversation text from memory."""
        if hasattr(memory, 'memory_segments') and memory.memory_segments:
            # Extract from memory segments
            context_segment = next((s for s in memory.memory_segments if s.segment_type == "context"), None)
            if context_segment:
                recent_messages = context_segment.content.get("recent_messages", [])
                conversation_lines = []
                for msg in recent_messages:
                    conversation_lines.append(f"{msg['role']}: {msg['content']}")
                return "\n".join(conversation_lines)

        # Fallback summary
        return f"Conversation with {memory.message_count} messages about {memory.topics_discussed}"

    async def _build_memory_from_context(self, context: DialogueContext) -> Any:
        """Build memory object from dialogue context."""
        # This would create a memory-like object from the context
        # For now, return a simple representation
        class SimpleMemory:
            def __init__(self, context):
                self.conversation_id = context.conversation_id
                self.message_count = context.message_count
                self.final_state = context.current_state
                self.topics_discussed = context.conversation_goals
                self.resolved_topics = context.resolved_topics
                self.entities = context.extracted_entities
                self.sentiment_timeline = [(datetime.utcnow(), s) for s in context.sentiment_timeline]
                self.resolution_status = "active" if context.current_state != DialogueState.CONCLUSION else "completed"

        return SimpleMemory(context)

    def _create_empty_report(
        self,
        conversation_id: str,
        error_message: str
    ) -> ConversationQualityReport:
        """Create empty report when assessment fails."""
        return ConversationQualityReport(
            conversation_id=conversation_id,
            overall_score=0.0,
            dimension_scores=[],
            conversation_summary=error_message,
            strengths=[],
            weaknesses=[f"Assessment failed: {error_message}"],
            recommendations=["Retry quality assessment"],
            metrics={"error": True},
            assessed_at=datetime.utcnow(),
            assessment_method="failed"
        )

    async def batch_assess_conversations(
        self,
        conversation_ids: List[str],
        max_concurrent: int = 5
    ) -> List[ConversationQualityReport]:
        """Assess multiple conversations in batches."""
        reports = []

        # Process in batches to avoid overwhelming the API
        for i in range(0, len(conversation_ids), max_concurrent):
            batch = conversation_ids[i:i + max_concurrent]

            # Run assessments concurrently
            tasks = [
                self.assess_conversation_quality(conv_id)
                for conv_id in batch
            ]

            batch_reports = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_reports:
                if isinstance(result, Exception):
                    logger.error(f"Batch assessment failed: {result}")
                    # Create error report
                    conv_id = batch[batch_reports.index(result)]
                    reports.append(self._create_empty_report(conv_id, str(result)))
                else:
                    reports.append(result)

        return reports

    async def get_quality_trends(
        self,
        user_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get quality trends over time."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # This would typically query the database for historical assessments
            # For now, return placeholder data
            trends = {
                "period_days": days,
                "total_assessments": 0,
                "average_score": 0.0,
                "score_trend": "stable",
                "dimension_trends": {
                    dimension.value: {"average": 0.0, "trend": "stable"}
                    for dimension in QualityDimension
                },
                "improvement_areas": [],
                "generated_at": datetime.utcnow().isoformat()
            }

            return trends

        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return {"error": str(e), "generated_at": datetime.utcnow().isoformat()}

    async def assess_response(
        self,
        user_message: str,
        assistant_response: str,
        context: Any = None
    ) -> float:
        """Assess the quality of a single response."""
        try:
            # Create a simple assessment prompt
            assessment_prompt = f"""Assess the quality of this customer service response on a scale of 0.0 to 1.0:

Customer Message: "{user_message}"
Assistant Response: "{assistant_response}"

Consider:
- Clarity and helpfulness
- Relevance to the customer's question
- Professionalism and tone
- Accuracy of information

Provide only a single numeric score between 0.0 and 1.0."""

            messages = [
                {"role": "system", "content": "You are a customer service quality assessor. Provide only numeric scores."},
                {"role": "user", "content": assessment_prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=10
            )

            if "choices" in response and len(response["choices"]) > 0:
                score_text = response["choices"][0]["message"]["content"].strip()
                # Extract numeric score
                try:
                    score = float(score_text)
                    return max(0.0, min(1.0, score))  # Ensure score is between 0.0 and 1.0
                except ValueError:
                    # If parsing fails, return a default score
                    return 0.7
            else:
                return 0.7  # Default score if LLM fails

        except Exception as e:
            logger.error(f"Response assessment failed: {e}")
            return 0.7  # Default score on error