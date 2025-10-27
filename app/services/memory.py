"""
Conversation memory management service for storing and retrieving conversation history.
"""

import json
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from loguru import logger

from app.services.dialogue import DialogueContext, DialogueState
from app.services.embedding import EmbeddingService
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.conversation import Conversation, Message, ConversationStatus, MessageSender
from app.models.user import User
from app.utils.exceptions import DatabaseError


def is_valid_uuid(conversation_id: str) -> bool:
    """Check if conversation_id is a valid UUID format."""
    try:
        uuid.UUID(conversation_id)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


@dataclass
class MemorySegment:
    """Memory segment for conversation storage."""
    conversation_id: str
    segment_type: str  # "summary", "key_points", "entities", "context"
    content: Dict[str, Any]
    timestamp: datetime
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConversationMemory:
    """Complete conversation memory structure."""
    conversation_id: str
    user_id: Optional[str]
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int
    final_state: DialogueState
    summary: Optional[str]
    key_points: List[str]
    entities: List[Dict[str, Any]]
    sentiment_timeline: List[Tuple[datetime, str]]
    topics_discussed: List[str]
    resolution_status: str
    metadata: Dict[str, Any]
    memory_segments: List[MemorySegment]


class ConversationMemoryManager:
    """Manages conversation memory and persistence."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.active_memories: Dict[str, ConversationMemory] = {}
        self.max_active_memories = 1000  # Limit active memory cache
        self.cleanup_interval = timedelta(hours=1)
        self.last_cleanup = datetime.utcnow()
        self._system_user_id = None  # Cache system user ID

    async def _get_or_create_system_user(self, db_session) -> uuid.UUID:
        """Get or create a system user for anonymous conversations."""
        if self._system_user_id:
            return self._system_user_id

        # Try to find existing system user
        system_user = db_session.query(User).filter(
            User.email == "system@anonymous.com"
        ).first()

        if system_user:
            self._system_user_id = system_user.id
            return system_user.id

        # Create system user
        system_user_id = uuid.uuid4()
        system_user = User(
            id=system_user_id,
            username="system_user",
            email="system@anonymous.com",
            full_name="System User",
            hashed_password="no_password",  # System user doesn't need password
            is_active=True,
            is_verified=True,
            is_superuser=False,
            roles=["system"],
            preferences={"anonymous": True},
            user_metadata={"type": "system", "auto_created": True}
        )

        db_session.add(system_user)
        db_session.flush()  # Get the ID without committing

        self._system_user_id = system_user.id
        logger.info(f"Created system user for anonymous conversations: {system_user.id}")
        return system_user.id

    async def save_conversation(
        self,
        context: DialogueContext,
        db_session: Optional[Any] = None
    ) -> bool:
        """Save conversation to persistent storage. v2"""
        try:
            logger.info(f"Starting save_conversation for {context.conversation_id}")

            # Handle test conversation IDs gracefully
            if not is_valid_uuid(context.conversation_id):
                logger.warning(f"Skipping database save for test conversation ID: {context.conversation_id}")
                return True

            if db_session is None:
                db_session = SessionLocal()

            # Create or update conversation record
            logger.debug("Creating/updating conversation record")
            conversation = db_session.query(Conversation).filter(
                Conversation.id == context.conversation_id
            ).first()

            if not conversation:
                logger.debug("Creating new conversation record")
                # Handle None user_id by providing a default
                user_id = context.user_id
                logger.debug(f"Original user_id from context: {user_id} (type: {type(user_id)})")

                if user_id is None:
                    # Use system user for anonymous conversations
                    user_id = await self._get_or_create_system_user(db_session)
                    logger.info(f"No user_id provided for conversation {context.conversation_id}, using system user: {user_id}")

                logger.debug(f"Final user_id for database: {user_id} (type: {type(user_id)})")
                conversation = Conversation(
                    id=context.conversation_id,
                    user_id=user_id,
                    status=ConversationStatus.ACTIVE,
                    title=self._generate_conversation_title(context),
                    created_at=context.session_start,
                    updated_at=datetime.utcnow()
                )
                db_session.add(conversation)
            else:
                logger.debug("Updating existing conversation record")
                conversation.updated_at = datetime.utcnow()
                conversation.status = ConversationStatus.ACTIVE

            # Save messages if they don't exist
            logger.debug("About to call _save_messages")
            await self._save_messages(context, conversation, db_session)
            logger.debug("_save_messages completed successfully")

            # Create memory segments
            logger.debug("About to create memory segments")
            memory_segments = await self._create_memory_segments(context)
            logger.debug("Memory segments created successfully")

            # Save to database
            logger.debug("About to commit to database")
            db_session.commit()
            logger.debug("Database commit successful")

            # Update active memory cache
            logger.debug("About to update active memory")
            await self._update_active_memory(context, memory_segments)
            logger.debug("Active memory updated successfully")

            # Cleanup old entries
            logger.debug("About to cleanup if needed")
            await self._cleanup_if_needed()
            logger.debug("Cleanup completed successfully")

            logger.info(f"Successfully saved conversation {context.conversation_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save conversation {context.conversation_id}: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            if db_session:
                db_session.rollback()
            return False

    async def load_conversation(
        self,
        conversation_id: str,
        db_session: Optional[Any] = None
    ) -> Optional[ConversationMemory]:
        """Load conversation from storage."""
        try:
            # Check active memory first
            if conversation_id in self.active_memories:
                return self.active_memories[conversation_id]

            if db_session is None:
                db_session = SessionLocal()

            # Load from database
            conversation = db_session.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation:
                return None

            # Load messages
            messages = db_session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()

            # Build memory structure
            memory = await self._build_conversation_memory(conversation, messages)

            # Cache in active memory
            self.active_memories[conversation_id] = memory

            return memory

        except Exception as e:
            logger.error(f"Failed to load conversation {conversation_id}: {e}")
            return None

    async def _save_messages(
        self,
        context: DialogueContext,
        conversation: Conversation,
        db_session: Any
    ):
        """Save conversation messages to database."""
        # Get existing messages
        existing_messages = db_session.query(Message).filter(
            Message.conversation_id == conversation.id
        ).all()
        existing_message_ids = {msg.id for msg in existing_messages}

        # Save new messages from context
        logger.info(f"Processing {len(context.context_window)} messages in context window for saving")
        for idx, msg_data in enumerate(context.context_window):
            logger.debug(f"Message {idx}: role={msg_data.get('role')}, has_message_number={'message_number' in msg_data}")
            if msg_data["role"] in ["user", "assistant"]:
                # Generate proper UUID for message ID
                # Use message_number if available, otherwise use index as fallback
                message_number = msg_data.get('message_number', idx + 1)
                msg_id = str(uuid.uuid4())
                logger.debug(f"Generated message ID: {msg_id} for message_number: {message_number}")

                if msg_id not in existing_message_ids:
                    message = Message(
                        id=msg_id,
                        conversation_id=conversation.id,
                        sender=MessageSender.USER if msg_data["role"] == "user" else MessageSender.ASSISTANT,
                        content=msg_data["content"],
                        created_at=datetime.fromisoformat(msg_data["timestamp"])
                    )

                    # Add NLU metadata if available
                    extracted_entities = getattr(context, 'extracted_entities', [])
                    if msg_data["role"] == "user" and len(extracted_entities) > 0:
                        # Find relevant entities for this message
                        # This is simplified - in practice, you'd track entities per message
                        message.entities = extracted_entities[:5]  # Limit to 5 entities

                    db_session.add(message)

    async def _create_memory_segments(
        self,
        context: DialogueContext
    ) -> List[MemorySegment]:
        """Create memory segments for efficient retrieval. v2"""
        segments = []

        # Summary segment
        if context.message_count > 0:
            # Handle both DialogueContext and StreamlinedDialogueContext
            try:
                previous_states = context.previous_states
            except AttributeError:
                previous_states = []

            try:
                current_state = context.current_state
            except AttributeError:
                current_state = None

            # Create state flow if available
            state_flow = []
            if previous_states and current_state:
                state_flow = [state.value for state in previous_states + [current_state]]
            elif current_state:
                state_flow = [current_state.value] if hasattr(current_state, 'value') else [str(current_state)]
            else:
                state_flow = ["active"]  # Default state

            summary_content = {
                "state_flow": state_flow,
                "message_count": context.message_count,
                "duration_minutes": (datetime.utcnow() - context.session_start).total_seconds() / 60,
                "goals": getattr(context, 'conversation_goals', []),
                "resolved_topics": getattr(context, 'resolved_topics', [])
            }

            segments.append(MemorySegment(
                conversation_id=context.conversation_id,
                segment_type="summary",
                content=summary_content,
                timestamp=datetime.utcnow()
            ))

        # Key points segment
        if context.conversation_goals or context.resolved_topics:
            key_points_content = {
                "goals": context.conversation_goals,
                "resolved": context.resolved_topics,
                "pending": context.pending_questions
            }

            segments.append(MemorySegment(
                conversation_id=context.conversation_id,
                segment_type="key_points",
                content=key_points_content,
                timestamp=datetime.utcnow()
            ))

        # Entities segment
        extracted_entities = getattr(context, 'extracted_entities', [])
        if extracted_entities:
            entities_content = {
                "entities": extracted_entities,
                "entity_types": list(set(e.get("label") for e in extracted_entities))
            }

            segments.append(MemorySegment(
                conversation_id=context.conversation_id,
                segment_type="entities",
                content=entities_content,
                timestamp=datetime.utcnow()
            ))

        # Context segment (recent conversation)
        if len(context.context_window) > 0:
            context_content = {
                "recent_messages": context.context_window[-5:],  # Last 5 messages
                "sentiment_trend": context.sentiment_history[-10:],  # Last 10 sentiments
                "escalation_triggers": context.escalation_triggers
            }

            segments.append(MemorySegment(
                conversation_id=context.conversation_id,
                segment_type="context",
                content=context_content,
                timestamp=datetime.utcnow()
            ))

        # Generate embeddings for semantic search
        # FEATURE DISABLED: Embedding generation has been temporarily disabled
        # for segment in segments:
        #     try:
        #         text_content = json.dumps(segment.content, default=str)
        #         segment.embedding = await self.embedding_service.get_embedding(text_content)
        #     except Exception as e:
        #         logger.warning(f"Failed to generate embedding for segment {segment.segment_type}: {e}")
        logger.info("Embedding generation for memory segments is disabled")

        return segments

    async def _update_active_memory(
        self,
        context: DialogueContext,
        memory_segments: List[MemorySegment]
    ):
        """Update active memory cache."""
        memory = ConversationMemory(
            conversation_id=context.conversation_id,
            user_id=context.user_id,
            title=None,  # Will be generated later
            created_at=context.session_start,
            updated_at=datetime.utcnow(),
            message_count=context.message_count,
            final_state=getattr(context, 'current_state', None),
            summary=None,  # Will be generated later
            key_points=context.conversation_goals + context.resolved_topics,
            entities=getattr(context, 'extracted_entities', []),
            sentiment_timeline=[],  # Would be built from context
            topics_discussed=context.conversation_goals,
            resolution_status="active",
            metadata=context.metadata,
            memory_segments=memory_segments
        )

        self.active_memories[context.conversation_id] = memory

    def _generate_conversation_title(self, context: DialogueContext) -> str:
        """Generate a title for the conversation."""
        if context.conversation_goals:
            return f"Discussion about {context.conversation_goals[0]}"
        elif getattr(context, 'extracted_entities', []):
            extracted_entities = getattr(context, 'extracted_entities', [])
            product_entities = [e for e in extracted_entities if e.get("label") == "PRODUCT"]
            if product_entities:
                return f"About {product_entities[0].get('text', 'product')}"
        return f"Conversation {context.conversation_id[:8]}"

    async def search_similar_conversations(
        self,
        query_text: str,
        limit: int = 5,
        user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar conversations using semantic search.
        FEATURE DISABLED: Similar conversation search has been temporarily disabled."""
        logger.info("Similar conversation search feature is disabled")
        # Return empty results since the feature is disabled
        return []

    async def get_conversation_insights(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """Get insights about a conversation."""
        try:
            memory = await self.load_conversation(conversation_id)
            if not memory:
                return {"error": "Conversation not found"}

            insights = {
                "conversation_id": conversation_id,
                "basic_stats": {
                    "message_count": memory.message_count,
                    "duration_hours": (memory.updated_at - memory.created_at).total_seconds() / 3600,
                    "final_state": memory.final_state.value,
                    "resolution_status": memory.resolution_status
                },
                "content_analysis": {
                    "topics_discussed": memory.topics_discussed,
                    "key_entities": memory.entities,
                    "key_points": memory.key_points
                },
                "sentiment_analysis": {
                    "sentiment_timeline": memory.sentiment_timeline,
                    "sentiment_distribution": self._analyze_sentiment_distribution(memory.sentiment_timeline)
                },
                "engagement_metrics": {
                    "avg_messages_per_topic": len(memory.topics_discussed) / max(len(memory.key_points), 1),
                    "entity_density": len(memory.entities) / max(memory.message_count, 1),
                    "resolution_rate": len(memory.resolved_topics) / max(len(memory.topics_discussed), 1)
                }
            }

            return insights

        except Exception as e:
            logger.error(f"Failed to get conversation insights: {e}")
            return {"error": str(e)}

    def _analyze_sentiment_distribution(self, sentiment_timeline: List[Tuple[datetime, str]]) -> Dict[str, Any]:
        """Analyze sentiment distribution from timeline."""
        if not sentiment_timeline:
            return {"distribution": {}, "trend": "stable"}

        # Count sentiments
        sentiment_counts = {}
        for _, sentiment in sentiment_timeline:
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

        total = len(sentiment_timeline)
        distribution = {
            sentiment: count / total for sentiment, count in sentiment_counts.items()
        }

        # Analyze trend
        if len(sentiment_timeline) >= 3:
            recent_sentiments = [s for _, s in sentiment_timeline[-3:]]
            if all(s == "positive" for s in recent_sentiments):
                trend = "improving"
            elif all(s == "negative" for s in recent_sentiments):
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "distribution": distribution,
            "trend": trend
        }

    async def _build_conversation_memory(
        self,
        conversation: Conversation,
        messages: List[Any]
    ) -> ConversationMemory:
        """Build conversation memory from database records."""
        # Extract entities from messages
        entities = []
        for msg in messages:
            if hasattr(msg, 'entities') and msg.entities:
                entities.extend(msg.entities)

        # Build sentiment timeline
        sentiment_timeline = []
        for msg in messages:
            if hasattr(msg, 'sentiment'):
                sentiment_timeline.append((msg.created_at, msg.sentiment))

        # Determine final state
        final_state = DialogueState.CONCLUSION
        if conversation.status == ConversationStatus.ACTIVE:
            final_state = DialogueState.INFORMATION_GATHERING

        return ConversationMemory(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=len(messages),
            final_state=final_state,
            summary=None,  # Would need to be generated
            key_points=[],  # Would need to be extracted
            entities=entities,
            sentiment_timeline=sentiment_timeline,
            topics_discussed=[],  # Would need to be analyzed
            resolution_status="completed" if conversation.status == ConversationStatus.COMPLETED else "active",
            metadata={},
            memory_segments=[]  # Would need to be loaded separately
        )

    async def _cleanup_if_needed(self):
        """Clean up old entries if needed."""
        now = datetime.utcnow()
        if now - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_old_memories()
            self.last_cleanup = now

    async def _cleanup_old_memories(self):
        """Clean up old conversation memories."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        to_remove = []
        for conv_id, memory in self.active_memories.items():
            if memory.updated_at < cutoff_time:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            del self.active_memories[conv_id]
            logger.info(f"Cleaned up old memory: {conv_id}")

        # Limit active memories if still too many
        if len(self.active_memories) > self.max_active_memories:
            # Sort by last updated and remove oldest
            sorted_memories = sorted(
                self.active_memories.items(),
                key=lambda x: x[1].updated_at
            )
            to_remove = [conv_id for conv_id, _ in sorted_memories[:len(self.active_memories) - self.max_active_memories]]

            for conv_id in to_remove:
                del self.active_memories[conv_id]

    async def get_user_conversation_history(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get user's conversation history."""
        try:
            db_session = SessionLocal()
            conversations = db_session.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.updated_at.desc()).offset(offset).limit(limit).all()

            history = []
            for conv in conversations:
                history.append({
                    "conversation_id": conv.id,
                    "title": conv.title,
                    "status": conv.status.value,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "message_count": db_session.query(Message).filter(
                        Message.conversation_id == conv.id
                    ).count()
                })

            db_session.close()
            return history

        except Exception as e:
            logger.error(f"Failed to get user conversation history: {e}")
            return []