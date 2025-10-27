"""
Dialogue management service for LLM-driven conversation flow.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
from loguru import logger

from app.services.llm import LLMService
from app.services.nlu import NLUService
from app.services.embedding import EmbeddingService
from app.utils.exceptions import LLMError


class DialogueState(Enum):
    """Dialogue state enumeration."""
    GREETING = "greeting"
    INFORMATION_GATHERING = "information_gathering"
    PROBLEM_SOLVING = "problem_solving"
    TRANSACTION = "transaction"
    SUPPORT = "support"
    POLICY_INQUIRY = "policy_inquiry"
    ESCALATION = "escalation"
    CONCLUSION = "conclusion"
    IDLE = "idle"


class DialogueAction(Enum):
    """Dialogue action enumeration."""
    PROVIDE_INFORMATION = "provide_information"
    ASK_QUESTION = "ask_question"
    CLARIFY = "clarify"
    ACKNOWLEDGE = "acknowledge"
    ESCALATE = "escalate"
    TRANSFER = "transfer"
    END_CONVERSATION = "end_conversation"
    REQUEST_MORE_INFO = "request_more_info"
    OFFER_HELP = "offer_help"


@dataclass
class DialogueContext:
    """Dialogue context information."""
    conversation_id: str
    user_id: Optional[str]
    current_state: DialogueState
    previous_states: List[DialogueState]
    message_count: int
    session_start: datetime
    last_activity: datetime
    context_window: List[Dict[str, Any]]
    extracted_entities: List[Dict[str, Any]]
    user_profile: Dict[str, Any]
    conversation_goals: List[str]
    resolved_topics: List[str]
    pending_questions: List[str]
    sentiment_history: List[str]
    escalation_triggers: List[str]
    metadata: Dict[str, Any]


@dataclass
class DialogueDecision:
    """Dialogue decision result."""
    next_state: DialogueState
    action: DialogueAction
    response_type: str
    should_escalate: bool
    confidence: float
    reasoning: str
    suggested_response: Optional[str]
    follow_up_questions: List[str]


class DialogueManager:
    """Manages dialogue flow and conversation state."""

    def __init__(self):
        self.llm_service = LLMService()
        self.nlu_service = NLUService()
        self.embedding_service = EmbeddingService()

        # Dialogue management prompts
        self.dialogue_prompts = self._load_dialogue_prompts()

        # State transition rules
        self.state_transitions = self._load_state_transitions()

        # Context window settings
        self.max_context_length = 20  # Maximum number of messages in context
        self.max_context_age = timedelta(hours=24)  # Maximum age for context relevance

        # Active conversations cache
        self.active_contexts: Dict[str, DialogueContext] = {}

    def _load_dialogue_prompts(self) -> Dict[str, str]:
        """Load dialogue management prompt templates."""
        return {
            "state_management": """You are an AI dialogue manager for an e-commerce customer service system.

Your task is to analyze the current conversation state and determine the next appropriate action.

Current Dialogue States:
- GREETING: Initial conversation start, user introduction
- INFORMATION_GATHERING: Collecting information about user needs
- PROBLEM_SOLVING: Working to resolve user issues
- TRANSACTION: Handling purchase-related actions
- SUPPORT: Providing technical or account support
- POLICY_INQUIRY: Answering questions about shop policies (refund, shipping, privacy, etc.)
- ESCALATION: Preparing to transfer to human agent
- CONCLUSION: Wrapping up the conversation
- IDLE: Conversation pause or user disengagement

Consider the context, user intent, entities, and conversation history to make your decision.""",

            "response_generation": """You are a helpful AI customer service assistant for an e-commerce platform.

Generate a natural, conversational response that:
1. Addresses the user's current need or question
2. Maintains the appropriate conversation tone
3. Provides helpful information or next steps
4. Encourages continued engagement if appropriate
5. Matches the expected response style for the context

Be conversational, empathetic, and professional.""",

            "escalation_analysis": """You are an AI system that determines when a conversation should be escalated to a human agent.

Analyze the conversation context and determine if escalation is necessary based on:
1. User frustration or anger
2. Complex technical issues beyond AI capabilities
3. Account security concerns
4. Legal or policy violations
5. Multiple failed resolution attempts
6. User explicitly requesting human agent

Consider the urgency and complexity of the situation.""",

            "context_summarization": """Summarize the key points of a conversation for future reference.

Include:
1. Main topics discussed
2. User's primary goal or issue
3. Key information shared
4. Current status of resolution
5. Next steps or pending actions
6. Important entities (products, orders, etc.)

Keep it concise but comprehensive enough for context continuation.""",
        }

    def _load_state_transitions(self) -> Dict[DialogueState, List[DialogueState]]:
        """Load valid state transitions."""
        return {
            DialogueState.GREETING: [
                DialogueState.INFORMATION_GATHERING,
                DialogueState.PROBLEM_SOLVING,
                DialogueState.TRANSACTION,
                DialogueState.SUPPORT
            ],
            DialogueState.INFORMATION_GATHERING: [
                DialogueState.PROBLEM_SOLVING,
                DialogueState.TRANSACTION,
                DialogueState.SUPPORT,
                DialogueState.CONCLUSION
            ],
            DialogueState.PROBLEM_SOLVING: [
                DialogueState.INFORMATION_GATHERING,
                DialogueState.TRANSACTION,
                DialogueState.SUPPORT,
                DialogueState.ESCALATION,
                DialogueState.CONCLUSION
            ],
            DialogueState.TRANSACTION: [
                DialogueState.INFORMATION_GATHERING,
                DialogueState.PROBLEM_SOLVING,
                DialogueState.CONCLUSION
            ],
            DialogueState.SUPPORT: [
                DialogueState.INFORMATION_GATHERING,
                DialogueState.PROBLEM_SOLVING,
                DialogueState.ESCALATION,
                DialogueState.CONCLUSION
            ],
            DialogueState.ESCALATION: [
                DialogueState.CONCLUSION
            ],
            DialogueState.CONCLUSION: [
                DialogueState.IDLE,
                DialogueState.GREETING  # If user starts new topic
            ],
            DialogueState.IDLE: [
                DialogueState.GREETING,
                DialogueState.INFORMATION_GATHERING,
                DialogueState.PROBLEM_SOLVING
            ]
        }

    async def get_or_create_context(
        self,
        conversation_id: str,
        user_id: Optional[str] = None
    ) -> DialogueContext:
        """Get existing context or create new one."""
        if conversation_id in self.active_contexts:
            return self.active_contexts[conversation_id]

        # Create new context
        context = DialogueContext(
            conversation_id=conversation_id,
            user_id=user_id,
            current_state=DialogueState.GREETING,
            previous_states=[],
            message_count=0,
            session_start=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            context_window=[],
            extracted_entities=[],
            user_profile={},
            conversation_goals=[],
            resolved_topics=[],
            pending_questions=[],
            sentiment_history=[],
            escalation_triggers=[],
            metadata={}
        )

        self.active_contexts[conversation_id] = context
        return context

    async def update_context(
        self,
        context: DialogueContext,
        user_message: str,
        nlu_results: Dict[str, Any],
        assistant_response: Optional[str] = None
    ) -> DialogueContext:
        """Update dialogue context with new message."""
        # Update basic info
        context.message_count += 1
        context.last_activity = datetime.utcnow()

        # Add to context window
        context.context_window.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
            "message_number": context.message_count
        })

        if assistant_response:
            context.context_window.append({
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.utcnow().isoformat(),
                "message_number": context.message_count
            })

        # Update NLU information
        context.extracted_entities.extend(nlu_results.get("entities", []))
        if "sentiment" in nlu_results:
            context.sentiment_history.append(nlu_results["sentiment"])

        # Trim context window if needed
        await self._trim_context_window(context)

        return context

    async def _trim_context_window(self, context: DialogueContext):
        """Trim context window to maintain size and relevance."""
        # Remove old messages
        if len(context.context_window) > self.max_context_length:
            # Keep the most recent messages
            context.context_window = context.context_window[-self.max_context_length:]

        # Remove very old messages
        cutoff_time = datetime.utcnow() - self.max_context_age
        context.context_window = [
            msg for msg in context.context_window
            if datetime.fromisoformat(msg["timestamp"]) > cutoff_time
        ]

    async def make_dialogue_decision(
        self,
        context: DialogueContext,
        user_message: str,
        nlu_results: Dict[str, Any]
    ) -> DialogueDecision:
        """Make intelligent dialogue decision based on context."""
        try:
            # Build decision prompt
            decision_prompt = self._build_decision_prompt(context, user_message, nlu_results)

            messages = [
                {"role": "system", "content": self.dialogue_prompts["state_management"]},
                {"role": "user", "content": decision_prompt}
            ]

            # Use function calling for structured decision
            decision_functions = [
                {
                    "name": "make_dialogue_decision",
                    "description": "Make a dialogue management decision",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "next_state": {
                                "type": "string",
                                "enum": [state.value for state in DialogueState],
                                "description": "Next dialogue state"
                            },
                            "action": {
                                "type": "string",
                                "enum": [action.value for action in DialogueAction],
                                "description": "Action to take"
                            },
                            "response_type": {
                                "type": "string",
                                "description": "Type of response to generate"
                            },
                            "should_escalate": {
                                "type": "boolean",
                                "description": "Whether to escalate to human agent"
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "Confidence in this decision"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Reasoning behind the decision"
                            },
                            "suggested_response": {
                                "type": "string",
                                "description": "Suggested response template"
                            },
                            "follow_up_questions": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Follow-up questions to ask user"
                            }
                        },
                        "required": ["next_state", "action", "response_type", "should_escalate", "confidence", "reasoning"]
                    }
                }
            ]

            response = await self.llm_service.function_calling(
                messages=messages,
                functions=decision_functions,
                temperature=0.1
            )

            # Parse decision
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                message = choice.get("message", {})

                if "function_call" in message:
                    try:
                        decision_data = json.loads(message["function_call"]["arguments"])

                        # Validate state transition
                        next_state = DialogueState(decision_data["next_state"])
                        if self._is_valid_transition(context.current_state, next_state):
                            return DialogueDecision(
                                next_state=next_state,
                                action=DialogueAction(decision_data["action"]),
                                response_type=decision_data["response_type"],
                                should_escalate=decision_data["should_escalate"],
                                confidence=decision_data["confidence"],
                                reasoning=decision_data["reasoning"],
                                suggested_response=decision_data.get("suggested_response"),
                                follow_up_questions=decision_data.get("follow_up_questions", [])
                            )
                        else:
                            # Invalid transition, fallback to safe state
                            logger.warning(f"Invalid state transition: {context.current_state} -> {next_state}")
                            return self._get_fallback_decision(context)

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse dialogue decision: {e}")
                        return self._get_fallback_decision(context)

            # Fallback if function calling fails
            return self._get_fallback_decision(context)

        except Exception as e:
            logger.error(f"Dialogue decision making failed: {e}")
            return self._get_fallback_decision(context)

    def _build_decision_prompt(
        self,
        context: DialogueContext,
        user_message: str,
        nlu_results: Dict[str, Any]
    ) -> str:
        """Build prompt for dialogue decision making."""
        prompt = f"""
Current Context:
- Current State: {context.current_state.value}
- Message Count: {context.message_count}
- Session Duration: {(datetime.utcnow() - context.session_start).total_seconds():.0f} seconds

User Message: "{user_message}"

NLU Analysis:
- Intent: {nlu_results.get('intent', 'unknown')}
- Entities: {nlu_results.get('entities', [])}
- Sentiment: {nlu_results.get('sentiment', 'neutral')}
- Confidence: {nlu_results.get('confidence', 0.0)}

Recent Conversation History:
"""

        # Add recent conversation context
        recent_messages = context.context_window[-6:]  # Last 6 messages
        for msg in recent_messages:
            prompt += f"- {msg['role']}: {msg['content'][:100]}...\n"

        prompt += f"""
Conversation Goals: {context.conversation_goals}
Resolved Topics: {context.resolved_topics}
Pending Questions: {context.pending_questions}

Make a decision about the next action and state. Consider the user's intent, sentiment, and the conversation flow.
"""

        return prompt

    def _is_valid_transition(self, current_state: DialogueState, next_state: DialogueState) -> bool:
        """Check if state transition is valid."""
        valid_transitions = self.state_transitions.get(current_state, [])
        return next_state in valid_transitions

    def _get_fallback_decision(self, context: DialogueContext) -> DialogueDecision:
        """Get fallback decision for error cases."""
        # Simple rule-based fallback
        if context.message_count == 1:
            return DialogueDecision(
                next_state=DialogueState.INFORMATION_GATHERING,
                action=DialogueAction.ASK_QUESTION,
                response_type="greeting_followup",
                should_escalate=False,
                confidence=0.5,
                reasoning="Fallback decision for new conversation",
                suggested_response="I'd be happy to help you! Could you tell me more about what you need?",
                follow_up_questions=[]
            )
        else:
            return DialogueDecision(
                next_state=context.current_state,
                action=DialogueAction.ACKNOWLEDGE,
                response_type="acknowledgment",
                should_escalate=False,
                confidence=0.3,
                reasoning="Fallback decision, maintaining current state",
                suggested_response="I understand. Let me help you with that.",
                follow_up_questions=[]
            )

    async def generate_response(
        self,
        context: DialogueContext,
        decision: DialogueDecision,
        user_message: str
    ) -> str:
        """Generate contextual response based on decision."""
        try:
            # Build response generation prompt
            response_prompt = self._build_response_prompt(context, decision, user_message)

            messages = [
                {"role": "system", "content": self.dialogue_prompts["response_generation"]},
                {"role": "user", "content": response_prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=400
            )

            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0]["message"]["content"]
            else:
                return decision.suggested_response or "I'm here to help you with that."

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return decision.suggested_response or "I'm here to help you with that."

    def _build_response_prompt(
        self,
        context: DialogueContext,
        decision: DialogueDecision,
        user_message: str
    ) -> str:
        """Build prompt for response generation."""
        prompt = f"""
Generate a response for this conversation:

Current State: {context.current_state.value}
Next Action: {decision.action.value}
Response Type: {decision.response_type}

User said: "{user_message}"

Conversation Context:
- Goals: {context.conversation_goals}
- Resolved: {context.resolved_topics}
- Sentiment trend: {context.sentiment_history[-5:] if context.sentiment_history else 'neutral'}

Guidance:
{decision.reasoning}

Follow-up questions to consider: {decision.follow_up_questions}

Generate a natural, helpful response that fits the context and advances the conversation.
"""

        return prompt

    async def analyze_escalation_need(
        self,
        context: DialogueContext,
        user_message: str,
        nlu_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze if escalation to human agent is needed."""
        try:
            escalation_prompt = f"""
Analyze if this conversation should be escalated to a human agent.

Context:
- Current State: {context.current_state.value}
- Message Count: {context.message_count}
- Previous Escalations: {len(context.escalation_triggers)}
- Sentiment History: {context.sentiment_history}

Current Message: "{user_message}"
NLU Sentiment: {nlu_results.get('sentiment', 'unknown')}
NLU Confidence: {nlu_results.get('confidence', 0.0)}

Recent Messages:
"""

            # Add recent messages for context
            recent_messages = context.context_window[-5:]
            for msg in recent_messages:
                prompt += f"- {msg['role']}: {msg['content'][:100]}...\n"

            escalation_prompt += """

Return JSON with:
{
    "should_escalate": boolean,
    "urgency": "low|medium|high|urgent",
    "reason": "explanation",
    "suggested_agent_type": "technical|billing|general|supervisor",
    "customer_sentiment": "positive|neutral|negative|angry",
    "escalation_score": 0.0-1.0
}
"""

            messages = [
                {"role": "system", "content": self.dialogue_prompts["escalation_analysis"]},
                {"role": "user", "content": escalation_prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=300
            )

            if "choices" in response and len(response["choices"]) > 0:
                try:
                    return json.loads(response["choices"][0]["message"]["content"])
                except json.JSONDecodeError:
                    logger.error("Failed to parse escalation analysis")
                    return self._get_fallback_escalation_analysis(context, nlu_results)

            return self._get_fallback_escalation_analysis(context, nlu_results)

        except Exception as e:
            logger.error(f"Escalation analysis failed: {e}")
            return self._get_fallback_escalation_analysis(context, nlu_results)

    def _get_fallback_escalation_analysis(
        self,
        context: DialogueContext,
        nlu_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback escalation analysis based on rules."""
        # Rule-based escalation triggers
        escalation_score = 0.0
        reasons = []

        # High message count
        if context.message_count > 10:
            escalation_score += 0.2
            reasons.append("Long conversation")

        # Negative sentiment
        negative_sentiments = [s for s in context.sentiment_history if s == "negative"]
        if len(negative_sentiments) >= 3:
            escalation_score += 0.4
            reasons.append("Multiple negative sentiments")

        # Current negative sentiment
        if nlu_results.get("sentiment") == "negative":
            escalation_score += 0.3
            reasons.append("Current negative sentiment")

        # Already in escalation state
        if context.current_state == DialogueState.ESCALATION:
            escalation_score += 0.5
            reasons.append("Already in escalation state")

        return {
            "should_escalate": escalation_score >= 0.7,
            "urgency": "high" if escalation_score >= 0.7 else "medium" if escalation_score >= 0.4 else "low",
            "reason": "; ".join(reasons) if reasons else "No strong escalation indicators",
            "suggested_agent_type": "general",
            "customer_sentiment": nlu_results.get("sentiment", "neutral"),
            "escalation_score": escalation_score
        }

    async def summarize_conversation(
        self,
        context: DialogueContext
    ) -> Dict[str, Any]:
        """Generate conversation summary for persistence."""
        try:
            summary_prompt = f"""
Summarize this conversation:

Conversation ID: {context.conversation_id}
Duration: {(datetime.utcnow() - context.session_start).total_seconds():.0f} seconds
Messages: {context.message_count}
States: {[state.value for state in context.previous_states + [context.current_state]]}

Conversation Goals: {context.conversation_goals}
Resolved Topics: {context.resolved_topics}
Key Entities: {context.extracted_entities}

Recent messages:
"""

            # Add recent messages for context
            recent_messages = context.context_window[-10:]
            for i, msg in enumerate(recent_messages):
                prompt += f"{i+1}. {msg['role']}: {msg['content']}\n"

            summary_prompt += "\nGenerate a concise but comprehensive summary."

            messages = [
                {"role": "system", "content": self.dialogue_prompts["context_summarization"]},
                {"role": "user", "content": summary_prompt}
            ]

            response = await self.llm_service.generate_response(
                messages=messages,
                temperature=0.3,
                max_tokens=500
            )

            if "choices" in response and len(response["choices"]) > 0:
                summary = response["choices"][0]["message"]["content"]
            else:
                summary = "Conversation summary unavailable"

            return {
                "conversation_id": context.conversation_id,
                "summary": summary,
                "message_count": context.message_count,
                "duration_seconds": (datetime.utcnow() - context.session_start).total_seconds(),
                "final_state": context.current_state.value,
                "resolved_topics": context.resolved_topics,
                "key_entities": context.extracted_entities,
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Conversation summarization failed: {e}")
            return {
                "conversation_id": context.conversation_id,
                "summary": "Summary generation failed",
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat()
            }

    def cleanup_context(self, conversation_id: str):
        """Remove conversation context from active cache."""
        if conversation_id in self.active_contexts:
            del self.active_contexts[conversation_id]

    def get_active_contexts(self) -> Dict[str, DialogueContext]:
        """Get all active conversation contexts."""
        return self.active_contexts.copy()

    def cleanup_old_contexts(self, max_age_hours: int = 24):
        """Clean up old conversation contexts."""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

        to_remove = []
        for conv_id, context in self.active_contexts.items():
            if context.last_activity < cutoff_time:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            self.cleanup_context(conv_id)
            logger.info(f"Cleaned up old context: {conv_id}")

        return len(to_remove)

    async def handle_policy_inquiry(
        self,
        context: DialogueContext,
        user_message: str,
        policy_service=None,
        customer_context: Optional[Dict[str, Any]] = None,
        order_context: Optional[Dict[str, Any]] = None,
        product_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle policy-related inquiries using the policy service."""
        try:
            logger.info(f"Handling policy inquiry: {user_message[:100]}...")

            if not policy_service:
                logger.warning("Policy service not available, returning fallback response")
                return {
                    "response": "I'm not able to access our policy information right now. Please contact our customer service team for assistance with policy questions.",
                    "state_change": DialogueState.SUPPORT,
                    "confidence": 0.1,
                    "policy_type": None
                }

            # Use the policy service to answer the question
            policy_response = await policy_service.answer_policy_question(
                question=user_message,
                customer_context=customer_context,
                order_context=order_context,
                product_context=product_context
            )

            # Update context with policy inquiry information
            if "policy" not in context.conversation_goals:
                context.conversation_goals.append("policy")

            if user_message not in context.pending_questions:
                context.pending_questions.append(user_message)

            # Create response based on policy service answer
            if policy_response.answer_to_question:
                response = policy_response.answer_to_question
                confidence = policy_response.confidence_score or 0.7
            else:
                response = f"Based on our {policy_response.policy_type} policy, here's what I can tell you: {policy_response.policy_content[:300]}..."
                confidence = 0.5

            # Add helpful follow-up if confidence is low
            if confidence < 0.7:
                response += "\n\nWould you like me to connect you with a human agent who can provide more detailed information about our policies?"

            return {
                "response": response,
                "state_change": DialogueState.POLICY_INQUIRY,
                "confidence": confidence,
                "policy_type": policy_response.policy_type,
                "policy_url": policy_response.additional_info.get("policy_url") if policy_response.additional_info else None,
                "action_items": policy_response.additional_info.get("action_items", []) if policy_response.additional_info else []
            }

        except Exception as e:
            logger.error(f"Error handling policy inquiry: {e}")
            return {
                "response": "I'm having trouble accessing our policy information. Let me connect you with a human agent who can help you with policy questions.",
                "state_change": DialogueState.ESCALATION,
                "confidence": 0.0,
                "policy_type": None
            }

    def should_transition_to_policy_inquiry(
        self,
        user_message: str,
        nlu_results: Dict[str, Any]
    ) -> bool:
        """Determine if conversation should transition to policy inquiry state."""
        try:
            # Check if intent is policy_inquiry
            if nlu_results.get("intent") == "policy_inquiry":
                return True

            # Check for policy-related keywords
            policy_keywords = [
                "policy", "refund", "return", "exchange", "shipping", "delivery",
                "privacy", "terms", "conditions", "legal", "disclaimer", "cancellation",
                "money back", "guarantee", "warranty", "data protection"
            ]

            message_lower = user_message.lower()
            keyword_matches = sum(1 for keyword in policy_keywords if keyword in message_lower)

            # If there are multiple policy keywords, transition to policy inquiry
            return keyword_matches >= 1

        except Exception as e:
            logger.error(f"Error determining policy inquiry transition: {e}")
            return False