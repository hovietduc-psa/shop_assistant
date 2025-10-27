"""
Enhanced conversation analytics service for tracking conversation metrics,
user behavior, and system performance.
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from loguru import logger

from app.models.analytics import (
    ConversationAnalytics,
    UserActivity,
    SystemMetrics
)
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services.cache_service import cache_analytics_summary, CacheTTL


class ConversationAnalyticsService:
    """Service for collecting and analyzing conversation data."""

    def __init__(self):
        self.start_time = datetime.utcnow()

    async def track_conversation_start(
        self,
        conversation_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationAnalytics:
        """Track the start of a new conversation."""
        try:
            # Handle test conversation IDs gracefully
            try:
                conversation_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
            except (ValueError, AttributeError, TypeError):
                # Check for common test patterns to reduce warning noise
                test_patterns = ['test', 'demo', 'sample', 'debug', 'mock']
                is_test_conversation = any(
                    pattern in str(conversation_id).lower() for pattern in test_patterns
                )

                if not is_test_conversation:
                    logger.warning(f"Invalid conversation ID format for analytics tracking: {conversation_id}")

                # Create a dummy UUID for test conversations to prevent errors
                conversation_uuid = uuid.uuid4()

            analytics = ConversationAnalytics(
                conversation_id=conversation_uuid,
                total_messages=0,
                total_user_messages=0,
                total_assistant_messages=0,
                analytics_metadata=metadata or {}
            )

            # Track user activity
            if user_id:
                await self.track_user_activity(
                    user_id=user_id,
                    activity_type="conversation_started",
                    activity_description=f"Started conversation {conversation_id}",
                    session_id=session_id,
                    metadata={"conversation_id": conversation_id}
                )

            logger.info(f"Started tracking conversation {conversation_id}")
            return analytics

        except Exception as e:
            logger.error(f"Error tracking conversation start: {e}")
            raise

    async def track_message(
        self,
        conversation_id: str,
        message_content: str,
        message_type: str,  # "user" or "assistant"
        processing_time: Optional[float] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        quality_score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> None:
        """Track a message in the conversation."""
        try:
            # Get or create conversation analytics
            analytics = await self.get_conversation_analytics(conversation_id, db)

            if not analytics:
                # Create new analytics record
                analytics = await self.track_conversation_start(conversation_id, metadata=metadata)
                if db:
                    db.add(analytics)
                    db.commit()

            # Update message counts
            analytics.total_messages += 1
            if message_type == "user":
                analytics.total_user_messages += 1
            else:
                analytics.total_assistant_messages += 1

            # Update processing time
            if processing_time:
                if analytics.average_response_time == 0:
                    analytics.average_response_time = processing_time
                else:
                    # Calculate rolling average
                    total_time = analytics.average_response_time * (analytics.total_assistant_messages - 1) + processing_time
                    analytics.average_response_time = total_time / analytics.total_assistant_messages

            # Extract topics and intents (simplified implementation)
            if message_type == "user":
                topics = await self.extract_topics(message_content)
                intents = await self.extract_intents(message_content)
                sentiment = await self.analyze_sentiment(message_content)

                # Update analytics
                if topics:
                    analytics.main_topics = list(set(analytics.main_topics + topics))
                if intents:
                    analytics.intents_detected = list(set(analytics.intents_detected + intents))
                if sentiment:
                    analytics.sentiment_overall = sentiment

            # Track tool usage
            if tool_calls:
                analytics.analytics_metadata["tool_usage"] = analytics.analytics_metadata.get("tool_usage", [])
                analytics.analytics_metadata["tool_usage"].extend(tool_calls)

            # Update quality score
            if quality_score:
                analytics.quality_score = quality_score

            analytics.updated_at = datetime.utcnow()

            if db:
                db.commit()

            # Track system metrics
            await self.track_system_metric(
                metric_name="messages_processed",
                metric_type="counter",
                category="conversation",
                value=1,
                dimensions={
                    "message_type": message_type,
                    "conversation_id": conversation_id
                }
            )

            logger.debug(f"Tracked {message_type} message in conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error tracking message: {e}")

    async def track_conversation_end(
        self,
        conversation_id: str,
        resolution_status: str = "pending",
        user_satisfaction: Optional[int] = None,
        escalation_count: int = 0,
        human_intervention_required: bool = False,
        db: Session = None
    ) -> None:
        """Track the end of a conversation."""
        try:
            analytics = await self.get_conversation_analytics(conversation_id, db)

            if not analytics:
                logger.warning(f"No analytics found for conversation {conversation_id}")
                return

            # Calculate conversation duration
            analytics.total_duration = int((datetime.utcnow() - analytics.created_at).total_seconds())

            # Update resolution metrics
            analytics.resolution_status = resolution_status
            analytics.user_satisfaction = user_satisfaction
            analytics.escalation_count = escalation_count
            analytics.human_intervention_required = human_intervention_required

            # Calculate automation success rate
            if human_intervention_required:
                analytics.automation_success_rate = max(0, (analytics.total_messages - escalation_count) / analytics.total_messages)
            else:
                analytics.automation_success_rate = 1.0

            # Calculate business metrics
            analytics.conversion_potential = await self.calculate_conversion_potential(analytics, db)
            analytics.lead_generation_score = await self.calculate_lead_score(analytics, db)
            analytics.customer_effort_score = await self.calculate_customer_effort_score(analytics, db)

            analytics.analyzed_at = datetime.utcnow()

            if db:
                db.commit()

            # Track system metrics
            await self.track_system_metric(
                metric_name="conversation_completed",
                metric_type="counter",
                category="conversation",
                value=1,
                dimensions={
                    "resolution_status": resolution_status,
                    "escalation_required": str(human_intervention_required),
                    "duration_seconds": analytics.total_duration
                }
            )

            logger.info(f"Completed tracking for conversation {conversation_id}")

        except Exception as e:
            logger.error(f"Error tracking conversation end: {e}")

    async def track_user_activity(
        self,
        user_id: str,
        activity_type: str,
        activity_description: Optional[str] = None,
        session_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        response_time: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> UserActivity:
        """Track user activity for analytics."""
        try:
            activity = UserActivity(
                user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
                activity_type=activity_type,
                activity_description=activity_description,
                session_id=session_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                ip_address=ip_address,
                user_agent=user_agent,
                activity_metadata=metadata or {}
            )

            if db:
                db.add(activity)
                db.commit()

            # Track system metrics
            await self.track_system_metric(
                metric_name="user_activity",
                metric_type="counter",
                category="user",
                value=1,
                dimensions={
                    "activity_type": activity_type,
                    "user_id": str(user_id)
                }
            )

            return activity

        except Exception as e:
            logger.error(f"Error tracking user activity: {e}")
            raise

    async def track_system_metric(
        self,
        metric_name: str,
        metric_type: str,
        category: str,
        value: float,
        unit: Optional[str] = None,
        dimensions: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> SystemMetrics:
        """Track system performance metrics."""
        try:
            metric = SystemMetrics(
                metric_name=metric_name,
                metric_type=metric_type,
                category=category,
                value=value,
                unit=unit,
                dimensions=dimensions or {},
                tags=tags or [],
                system_metadata=metadata or {}
            )

            if db:
                db.add(metric)
                db.commit()

            return metric

        except Exception as e:
            logger.error(f"Error tracking system metric: {e}")
            raise

    async def get_conversation_analytics(
        self,
        conversation_id: str,
        db: Session
    ) -> Optional[ConversationAnalytics]:
        """Get analytics for a specific conversation."""
        try:
            if not db:
                return None

            # Handle test conversation IDs gracefully
            try:
                conversation_uuid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
            except (ValueError, AttributeError, TypeError):
                # Check for common test patterns to reduce warning noise
                test_patterns = ['test', 'demo', 'sample', 'debug', 'mock']
                is_test_conversation = any(
                    pattern in str(conversation_id).lower() for pattern in test_patterns
                )

                if not is_test_conversation:
                    logger.warning(f"Invalid conversation ID format for analytics: {conversation_id}")

                return None

            return db.query(ConversationAnalytics).filter(
                ConversationAnalytics.conversation_id == conversation_uuid
            ).first()

        except Exception as e:
            logger.error(f"Error getting conversation analytics: {e}")
            return None

    @cache_analytics_summary(ttl=CacheTTL.SHORT)
    async def get_conversation_metrics_summary(
        self,
        days: int = 7,
        db: Session = None
    ) -> Dict[str, Any]:
        """Get summary metrics for conversations in the specified period."""
        try:
            if not db:
                return {}

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get basic metrics
            total_conversations = db.query(ConversationAnalytics).filter(
                ConversationAnalytics.created_at >= cutoff_date
            ).count()

            resolved_conversations = db.query(ConversationAnalytics).filter(
                and_(
                    ConversationAnalytics.created_at >= cutoff_date,
                    ConversationAnalytics.resolution_status == "resolved"
                )
            ).count()

            # Calculate averages
            avg_messages = db.query(func.avg(ConversationAnalytics.total_messages)).filter(
                ConversationAnalytics.created_at >= cutoff_date
            ).scalar() or 0

            avg_response_time = db.query(func.avg(ConversationAnalytics.average_response_time)).filter(
                ConversationAnalytics.created_at >= cutoff_date
            ).scalar() or 0

            avg_satisfaction = db.query(func.avg(ConversationAnalytics.user_satisfaction)).filter(
                and_(
                    ConversationAnalytics.created_at >= cutoff_date,
                    ConversationAnalytics.user_satisfaction.isnot(None)
                )
            ).scalar() or 0

            # Get top topics
            top_topics = await self.get_top_topics(days, db)

            # Get resolution trends
            resolution_trends = await self.get_resolution_trends(days, db)

            return {
                "period_days": days,
                "total_conversations": total_conversations,
                "resolved_conversations": resolved_conversations,
                "resolution_rate": (resolved_conversations / total_conversations * 100) if total_conversations > 0 else 0,
                "average_messages_per_conversation": round(avg_messages, 2),
                "average_response_time_seconds": round(avg_response_time, 2),
                "average_user_satisfaction": round(avg_satisfaction, 2),
                "top_topics": top_topics,
                "resolution_trends": resolution_trends
            }

        except Exception as e:
            logger.error(f"Error getting conversation metrics summary: {e}")
            return {}

    async def extract_topics(self, message: str) -> List[str]:
        """Extract topics from message content."""
        # Simplified topic extraction based on keywords
        topic_keywords = {
            "shipping": ["shipping", "delivery", "ship", "deliver", "tracking", "track"],
            "returns": ["return", "refund", "exchange", "money back"],
            "products": ["product", "item", "buy", "purchase", "price", "cost"],
            "orders": ["order", "purchase", "buy", "payment", "checkout"],
            "account": ["account", "login", "password", "profile", "settings"],
            "policy": ["policy", "rules", "terms", "conditions", "guidelines"]
        }

        topics = []
        message_lower = message.lower()

        for topic, keywords in topic_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                topics.append(topic)

        return topics

    async def extract_intents(self, message: str) -> List[str]:
        """Extract intents from message content."""
        intent_keywords = {
            "search": ["find", "search", "looking for", "show me"],
            "question": ["what", "how", "when", "where", "why", "can you"],
            "complaint": ["problem", "issue", "wrong", "broken", "complaint"],
            "compliment": ["great", "good", "excellent", "perfect", "love"],
            "help": ["help", "assist", "support", "need help"]
        }

        intents = []
        message_lower = message.lower()

        for intent, keywords in intent_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                intents.append(intent)

        return intents

    async def analyze_sentiment(self, message: str) -> str:
        """Analyze sentiment of message content."""
        # Simplified sentiment analysis based on keywords
        positive_words = ["good", "great", "excellent", "perfect", "love", "happy", "satisfied"]
        negative_words = ["bad", "terrible", "awful", "hate", "unhappy", "angry", "frustrated", "disappointed"]

        message_lower = message.lower()

        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    async def calculate_conversion_potential(
        self,
        analytics: ConversationAnalytics,
        db: Session
    ) -> float:
        """Calculate conversion potential score (0-1)."""
        try:
            score = 0.0

            # Base score on conversation length and engagement
            if analytics.total_messages > 3:
                score += 0.2

            # Product-related topics increase potential
            product_topics = ["products", "orders", "shipping"]
            if any(topic in analytics.main_topics for topic in product_topics):
                score += 0.3

            # Positive sentiment increases potential
            if analytics.sentiment_overall == "positive":
                score += 0.2

            # Higher satisfaction scores increase potential
            if analytics.user_satisfaction and analytics.user_satisfaction >= 4:
                score += 0.3

            return min(score, 1.0)

        except Exception as e:
            logger.error(f"Error calculating conversion potential: {e}")
            return 0.0

    async def calculate_lead_score(
        self,
        analytics: ConversationAnalytics,
        db: Session
    ) -> float:
        """Calculate lead generation score (0-1)."""
        try:
            score = 0.0

            # High engagement indicates lead potential
            if analytics.total_messages > 5:
                score += 0.2

            # Business-related intents indicate lead potential
            business_intents = ["search", "question"]
            if any(intent in analytics.intents_detected for intent in business_intents):
                score += 0.3

            # No human intervention suggests automation success
            if not analytics.human_intervention_required:
                score += 0.2

            # Quick resolution indicates customer satisfaction
            if analytics.total_duration < 300:  # Less than 5 minutes
                score += 0.3

            return min(score, 1.0)

        except Exception as e:
            logger.error(f"Error calculating lead score: {e}")
            return 0.0

    async def calculate_customer_effort_score(
        self,
        analytics: ConversationAnalytics,
        db: Session
    ) -> float:
        """Calculate customer effort score (0-5, lower is better)."""
        try:
            score = 5.0  # Start with best score

            # More messages indicate higher effort
            if analytics.total_messages > 10:
                score -= 1.0
            elif analytics.total_messages > 20:
                score -= 2.0

            # Long duration indicates higher effort
            if analytics.total_duration > 600:  # More than 10 minutes
                score -= 1.0
            elif analytics.total_duration > 1800:  # More than 30 minutes
                score -= 2.0

            # Human intervention indicates higher effort
            if analytics.human_intervention_required:
                score -= 1.0

            # Escalation indicates higher effort
            if analytics.escalation_count > 0:
                score -= analytics.escalation_count * 0.5

            return max(score, 0.0)

        except Exception as e:
            logger.error(f"Error calculating customer effort score: {e}")
            return 3.0

    async def get_top_topics(self, days: int, db: Session) -> List[Dict[str, Any]]:
        """Get top topics discussed in conversations."""
        try:
            if not db:
                return []

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Get all conversations with their topics
            conversations = db.query(ConversationAnalytics).filter(
                ConversationAnalytics.created_at >= cutoff_date
            ).all()

            # Count topic occurrences
            topic_counts = {}
            for conv in conversations:
                for topic in conv.main_topics:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1

            # Sort and return top topics
            sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

            return [
                {"topic": topic, "count": count, "percentage": (count / len(conversations)) * 100}
                for topic, count in sorted_topics[:10]
            ]

        except Exception as e:
            logger.error(f"Error getting top topics: {e}")
            return []

    async def get_resolution_trends(self, days: int, db: Session) -> Dict[str, float]:
        """Get resolution trends over time."""
        try:
            if not db:
                return {}

            trends = {}
            for i in range(min(days, 30)):  # Limit to 30 days
                day = datetime.utcnow() - timedelta(days=i)
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                total = db.query(ConversationAnalytics).filter(
                    and_(
                        ConversationAnalytics.created_at >= day_start,
                        ConversationAnalytics.created_at < day_end
                    )
                ).count()

                resolved = db.query(ConversationAnalytics).filter(
                    and_(
                        ConversationAnalytics.created_at >= day_start,
                        ConversationAnalytics.created_at < day_end,
                        ConversationAnalytics.resolution_status == "resolved"
                    )
                ).count()

                day_str = day.strftime("%Y-%m-%d")
                trends[day_str] = (resolved / total * 100) if total > 0 else 0

            return trends

        except Exception as e:
            logger.error(f"Error getting resolution trends: {e}")
            return {}


# Global instance
conversation_analytics_service = ConversationAnalyticsService()