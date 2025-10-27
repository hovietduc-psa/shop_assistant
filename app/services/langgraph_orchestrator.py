"""
LangGraph orchestrator for Shop Assistant AI.
Main workflow coordinator that replaces the current multi-step process.
"""

import time
import asyncio
from typing import Dict, Any, Optional
from loguru import logger

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Phase 3 imports
from app.services.langgraph_checkpoint import HybridCheckpointSaver
from app.services.langgraph_cache import LangGraphCache, ResponseCache
from app.services.langgraph_monitoring import langgraph_monitor

# Conditional routing function for intelligent workflow decisions
def _should_use_parallel_workflow(state: ConversationState) -> str:
    """
    Intelligent routing decision based on conversation complexity and urgency.

    Args:
        state: Current conversation state

    Returns:
        String indicating which workflow path to take
    """
    user_message = state.get("user_message", "").lower()
    entities = state.get("entities", [])

    # High complexity indicators
    complexity_indicators = [
        "between", "range", "multiple", "several", "compare",
        "recommendation", "suggestion", "advice", "help me choose"
    ]

    # Urgency indicators
    urgency_indicators = [
        "urgent", "asap", "immediately", "right now", "emergency",
        "frustrated", "angry", "disappointed", "unhappy"
    ]

    # Multiple tool indicators
    multiple_tool_indicators = [
        "and", "also", "plus", "additionally", "as well as",
        "what about", "how about", "tell me about"
    ]

    # Calculate complexity score
    complexity_score = 0
    for indicator in complexity_indicators:
        if indicator in user_message:
            complexity_score += 1

    # Calculate urgency score
    urgency_score = 0
    for indicator in urgency_indicators:
        if indicator in user_message:
            urgency_score += 1

    # Multiple entities indicate need for parallel processing
    entity_score = min(len(entities) // 2, 3)  # Cap at 3 points

    # Multiple tools needed
    tool_score = 0
    for indicator in multiple_tool_indicators:
        if indicator in user_message:
            tool_score += 1

    total_score = complexity_score + urgency_score + entity_score + tool_score

    # Decision threshold: use parallel workflow if score >= 2
    if total_score >= 2:
        return "parallel"
    else:
        return "simple"

from app.services.langgraph_state import (
    ConversationState,
    create_initial_state,
    update_state_timestamp,
    calculate_processing_metrics
)
from app.services.langgraph_nodes import LangGraphNodes
from app.core.config import settings


class LangGraphOrchestrator:
    """
    Main LangGraph orchestrator that coordinates the conversation workflow.

    This orchestrator replaces the current sequential processing with a stateful,
    efficient workflow using LangGraph's state management and conditional routing.
    """

    def __init__(self, phase: int = 3, enable_intelligent_routing: bool = False, enable_persistence: bool = True):
        self.phase = phase  # Phase 1: consolidated, Phase 2: parallel processing, Phase 3: persistent + advanced features
        self.enable_intelligent_routing = enable_intelligent_routing
        self.enable_persistence = enable_persistence
        self.nodes = LangGraphNodes()

        # Build workflow based on phase and routing options
        if enable_intelligent_routing and phase >= 2:
            self.workflow = self._build_intelligent_workflow()
        elif phase >= 2:
            self.workflow = self._build_phase2_workflow()
        else:
            self.workflow = self._build_workflow()

        self.compiled_workflow = None

        # Phase 3: Initialize persistent checkpointing and caching
        if enable_persistence and phase >= 3:
            self.checkpointer = HybridCheckpointSaver()
            self.cache = LangGraphCache()
            self.response_cache = ResponseCache(self.cache)
            logger.info("Phase 3: Persistent checkpointing and caching enabled")
        else:
            # Phase 1-2: Use memory checkpointing
            self.checkpointer = MemorySaver()
            self.cache = None
            self.response_cache = None
            logger.info(f"Phase {phase}: Memory checkpointing enabled")

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow for conversation processing.

        Returns:
            Configured StateGraph workflow
        """
        # Create the workflow graph
        workflow = StateGraph(ConversationState)

        # Add workflow nodes
        workflow.add_node("comprehensive_analysis", self.nodes.comprehensive_analysis_node)
        workflow.add_node("execute_tools", self.nodes.execute_tools_node)
        workflow.add_node("generate_response", self.nodes.generate_response_node)

        # Define workflow edges
        workflow.add_edge("comprehensive_analysis", "execute_tools")
        workflow.add_edge("execute_tools", "generate_response")
        workflow.add_edge("generate_response", END)

        # Set the entry point
        workflow.set_entry_point("comprehensive_analysis")

        return workflow

    def _build_phase2_workflow(self) -> StateGraph:
        """
        Build the Phase 2 LangGraph workflow with parallel processing.

        Phase 2 improvements:
        - Parallel entity extraction (regex, LLM, patterns)
        - Enhanced tool decision using merged entities
        - Parallel tool execution for independent tools

        Returns:
            Configured StateGraph workflow with parallel processing
        """
        # Create the workflow graph
        workflow = StateGraph(ConversationState)

        # Add Phase 2 workflow nodes
        workflow.add_node("parallel_entity_extraction", self.nodes.parallel_entity_extraction_node)
        workflow.add_node("enhanced_tool_decision", self.nodes.enhanced_tool_decision_node)
        workflow.add_node("parallel_tool_execution", self.nodes.parallel_tool_execution_node)
        workflow.add_node("generate_response", self.nodes.generate_response_node)

        # Define Phase 2 workflow edges (parallel processing flow)
        workflow.add_edge("parallel_entity_extraction", "enhanced_tool_decision")
        workflow.add_edge("enhanced_tool_decision", "parallel_tool_execution")
        workflow.add_edge("parallel_tool_execution", "generate_response")
        workflow.add_edge("generate_response", END)

        # Set the entry point
        workflow.set_entry_point("parallel_entity_extraction")

        return workflow

    def _build_intelligent_workflow(self) -> StateGraph:
        """
        Build the intelligent workflow with conditional routing.

        This workflow analyzes the conversation complexity and routes
        to either simple or parallel processing paths based on needs.

        Returns:
            Configured StateGraph workflow with intelligent routing
        """
        # Create the workflow graph
        workflow = StateGraph(ConversationState)

        # Add initial analysis node (simple entity extraction for routing decision)
        workflow.add_node("routing_analysis", self.nodes._routing_analysis_node)

        # Simple path nodes (for basic requests)
        workflow.add_node("simple_analysis", self.nodes.comprehensive_analysis_node)
        workflow.add_node("simple_execution", self.nodes.execute_tools_node)

        # Parallel path nodes (for complex requests)
        workflow.add_node("parallel_analysis", self.nodes.parallel_entity_extraction_node)
        workflow.add_node("enhanced_decision", self.nodes.enhanced_tool_decision_node)
        workflow.add_node("parallel_execution", self.nodes.parallel_tool_execution_node)

        # Common final node
        workflow.add_node("generate_response", self.nodes.generate_response_node)

        # Add conditional edges from routing analysis
        workflow.add_conditional_edges(
            "routing_analysis",
            _should_use_parallel_workflow,
            {
                "simple": "simple_analysis",
                "parallel": "parallel_analysis"
            }
        )

        # Simple path edges
        workflow.add_edge("simple_analysis", "simple_execution")
        workflow.add_edge("simple_execution", "generate_response")

        # Parallel path edges
        workflow.add_edge("parallel_analysis", "enhanced_decision")
        workflow.add_edge("enhanced_decision", "parallel_execution")
        workflow.add_edge("parallel_execution", "generate_response")

        # Final edge
        workflow.add_edge("generate_response", END)

        # Set the entry point
        workflow.set_entry_point("routing_analysis")

        return workflow

    def _calculate_complexity_score(self, user_message: str, entities: List[Dict[str, Any]]) -> int:
        """
        Calculate complexity score for routing decisions.

        Args:
            user_message: The user's message
            entities: Extracted entities

        Returns:
            Complexity score (higher = more complex)
        """
        user_message_lower = user_message.lower()

        # Complexity indicators
        complexity_indicators = [
            "between", "range", "multiple", "several", "compare",
            "recommendation", "suggestion", "advice", "help me choose"
        ]

        # Urgency indicators
        urgency_indicators = [
            "urgent", "asap", "immediately", "right now", "emergency",
            "frustrated", "angry", "disappointed", "unhappy"
        ]

        # Multiple tool indicators
        multiple_tool_indicators = [
            "and", "also", "plus", "additionally", "as well as",
            "what about", "how about", "tell me about"
        ]

        # Calculate scores
        complexity_score = sum(1 for indicator in complexity_indicators if indicator in user_message_lower)
        urgency_score = sum(1 for indicator in urgency_indicators if indicator in user_message_lower)
        tool_score = sum(1 for indicator in multiple_tool_indicators if indicator in user_message_lower)
        entity_score = min(len(entities) // 2, 3)  # Cap at 3 points

        return complexity_score + urgency_score + tool_score + entity_score

    async def _record_performance_metrics(self,
                                       processing_time: float,
                                       path_taken: str,
                                       result: Optional[Dict[str, Any]],
                                       cache_hit: bool,
                                       conversation_id: Optional[str] = None,
                                       error_type: Optional[str] = None):
        """
        Record performance metrics for monitoring.

        Args:
            processing_time: Processing time in seconds
            path_taken: Path taken (simple/parallel/error)
            result: Processing result
            cache_hit: Whether response was from cache
            conversation_id: Conversation ID
            error_type: Type of error if failed
        """
        try:
            # Extract metrics from result
            success = result is not None and result.get("success", True) if result else False
            tools_used = result.get("tool_calls_used", []) if result else []
            entities_count = len(result.get("entities", [])) if result else 0
            llm_calls_count = result.get("llm_calls_count", 0) if result else 0
            response_length = len(result.get("response", "")) if result else 0

            # Record to monitor
            langgraph_monitor.record_metric(
                processing_time=processing_time,
                phase=f"phase{self.phase}",
                path_taken=path_taken,
                tools_used=tools_used,
                entities_count=entities_count,
                llm_calls_count=llm_calls_count,
                success=success,
                error_type=error_type,
                response_length=response_length,
                cache_hit=cache_hit,
                thread_id=conversation_id or "default"
            )

        except Exception as e:
            logger.error(f"Failed to record performance metrics: {e}")

    async def process_message(
        self,
        user_message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a user message through the LangGraph workflow with Phase 3 enhancements.

        Args:
            user_message: The user's message
            conversation_context: Additional context for the conversation
            conversation_id: Optional conversation ID for state persistence

        Returns:
            Processing result with response and metadata
        """
        start_time = time.time()
        cache_hit = False
        path_taken = "unknown"

        try:
            logger.info(f"Processing message with LangGraph Phase {self.phase}: {user_message[:100]}...")

            # Phase 3: Check cache first
            if self.response_cache and conversation_id:
                # For caching, we need entities which we don't have yet
                # In a real implementation, you might cache based on message hash
                pass  # Skip caching for now since we need processing results first

            # Create initial state
            state = create_initial_state(user_message)

            # Add conversation context if provided
            if conversation_context:
                state["context_window"] = [conversation_context]

            # Compile workflow if not already compiled
            if self.compiled_workflow is None:
                self.compiled_workflow = self.workflow.compile(checkpointer=self.checkpointer)

            # Configure workflow execution
            config = {
                "configurable": {
                    "thread_id": conversation_id or "default",
                }
            }

            # Execute workflow
            result = await self.compiled_workflow.ainvoke(state, config=config)

            # Calculate final metrics
            total_time = time.time() - start_time
            result["processing_time"] = total_time
            result["updated_at"] = time.time()

            # Determine path taken for monitoring
            if self.enable_intelligent_routing and self.phase >= 2:
                # In intelligent routing, path is determined by complexity
                complexity_score = self._calculate_complexity_score(user_message, result.get("entities", []))
                path_taken = "parallel" if complexity_score >= 2 else "simple"
            elif self.phase >= 2:
                path_taken = "parallel"
            else:
                path_taken = "simple"

            # Phase 3: Cache response
            if self.response_cache and result.get("success", True):
                try:
                    await self.response_cache.cache_response(
                        user_message=user_message,
                        response_data=result,
                        entities=result.get("entities", []),
                        tools_used=result.get("tool_calls_used", []),
                        workflow_phase=f"phase{self.phase}",
                        ttl=1800  # 30 minutes
                    )
                except Exception as e:
                    logger.error(f"Failed to cache response: {e}")

            # Phase 3: Record performance metrics
            await self._record_performance_metrics(
                processing_time=total_time,
                path_taken=path_taken,
                result=result,
                cache_hit=cache_hit,
                conversation_id=conversation_id
            )

            # Build response object with Phase 3 enhancements
            response = self._build_response_object(result)
            response["metadata"]["path_taken"] = path_taken
            response["metadata"]["cached"] = cache_hit

            logger.info(f"LangGraph Phase {self.phase} processing completed in {total_time:.2f}s (path: {path_taken})")
            return response

        except Exception as e:
            logger.error(f"LangGraph processing failed: {e}")

            # Phase 3: Record error metrics
            await self._record_performance_metrics(
                processing_time=time.time() - start_time,
                path_taken="error",
                result=None,
                cache_hit=False,
                conversation_id=conversation_id,
                error_type=str(e)
            )

            return self._build_error_response(user_message, str(e), time.time() - start_time)

    def _build_response_object(self, state: ConversationState) -> Dict[str, Any]:
        """
        Build the response object from the final state.

        Args:
            state: Final conversation state

        Returns:
            Formatted response object
        """
        # Extract metadata for the response
        metadata = {
            "model": settings.DEFAULT_LLM_MODEL,
            "tool_calls_used": [result["tool_name"] for result in state.get("tool_results", []) if result.get("success", False)],
            "tool_results": state.get("tool_results", []),
            "reasoning": state.get("tool_reasoning", ""),
            "processing_time": state.get("processing_time", 0.0),
            "llm_calls_count": state.get("llm_calls_count", 0),
            "confidence": state.get("confidence", 0.0),
            "requires_clarification": state.get("requires_clarification", False),
            "suggested_follow_up": state.get("suggested_follow_up", []),
            "escalation_needed": state.get("escalation_needed", False),
            "escalation_reason": state.get("escalation_reason"),
            "entities_extracted": state.get("entities", []),
            "from_cache": state.get("from_cache", False),
            "workflow_method": f"langgraph_phase{self.phase}"
        }

        return {
            "success": True,
            "response": state.get("response", "I'm sorry, I couldn't generate a response."),
            "metadata": metadata
        }

    def _build_error_response(
        self,
        user_message: str,
        error: str,
        processing_time: float
    ) -> Dict[str, Any]:
        """
        Build an error response object.

        Args:
            user_message: The original user message
            error: Error message
            processing_time: Time spent processing

        Returns:
            Error response object
        """
        return {
            "success": False,
            "response": "I'm sorry, I encountered an error while processing your request. Please try again or contact our support team for assistance.",
            "metadata": {
                "error": error,
                "processing_time": processing_time,
                "llm_calls_count": 0,
                "tool_calls_used": [],
                "confidence": 0.1,
                "workflow_method": f"langgraph_phase{self.phase}"
            }
        }

    async def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get the current status of the LangGraph workflow.

        Returns:
            Workflow status information
        """
        # Determine features based on phase
        features = [
            "response_generation",
            "basic_error_handling"
        ]

        if self.phase >= 1:
            features.append("comprehensive_analysis")  # Combined entity extraction + tool selection

        if self.phase >= 2:
            if self.enable_intelligent_routing:
                features.extend([
                    "intelligent_routing",        # Conditional workflow routing
                    "routing_analysis",           # Quick analysis for routing decisions
                    "parallel_entity_extraction", # Parallel regex, LLM, patterns
                    "enhanced_tool_decision",     # Better tool selection using merged entities
                    "parallel_tool_execution"     # Parallel execution of independent tools
                ])
            else:
                features.extend([
                    "parallel_entity_extraction", # Parallel regex, LLM, patterns
                    "enhanced_tool_decision",     # Better tool selection using merged entities
                    "parallel_tool_execution"     # Parallel execution of independent tools
                ])
        else:
            features.append("sequential_tool_execution")

      # Determine entry point based on configuration
        if self.enable_intelligent_routing and self.phase >= 2:
            entry_point = "routing_analysis"
        elif self.phase >= 2:
            entry_point = "parallel_entity_extraction"
        else:
            entry_point = "comprehensive_analysis"

        return {
            "status": "active",
            "nodes_count": len(self.workflow.nodes),
            "entry_point": entry_point,
            "checkpointer": "memory",  # Phase 1-2 uses memory, Phase 3 will use persistent
            "version": f"phase{self.phase}" + ("_intelligent" if self.enable_intelligent_routing else ""),
            "features": features
        }

    def add_custom_node(self, name: str, node_func):
        """
        Add a custom node to the workflow (for future extensibility).

        Args:
            name: Name of the node
            node_func: Node function
        """
        self.workflow.add_node(name, node_func)
        logger.info(f"Added custom node: {name}")

    def get_workflow_graph_info(self) -> Dict[str, Any]:
        """
        Get information about the workflow graph structure.

        Returns:
            Workflow graph information
        """
        return {
            "nodes": list(self.workflow.nodes.keys()),
            "entry_point": self.workflow.entry_point,
            "edges": [
                {"from": edge[0], "to": edge[1]}
                for edge in self.workflow.edges
            ],
            "compiled": self.compiled_workflow is not None
        }


class LangGraphOrchestratorFactory:
    """
    Factory for creating LangGraph orchestrator instances.
    Provides configuration management and dependency injection.
    """

    @staticmethod
    def create_orchestrator(
        phase: int = 3,
        checkpoint_backend: str = "hybrid",
        enable_persistence: bool = True,
        enable_intelligent_routing: bool = False,
        custom_nodes: Optional[Dict[str, Any]] = None
    ) -> LangGraphOrchestrator:
        """
        Create a configured LangGraph orchestrator.

        Args:
            phase: Phase level (1=consolidated, 2=parallel processing, 3=persistent+advanced)
            checkpoint_backend: Backend for state checkpointing (memory, hybrid, sqlite)
            enable_persistence: Whether to enable persistent state
            enable_intelligent_routing: Whether to enable intelligent workflow routing
            custom_nodes: Additional custom nodes to add

        Returns:
            Configured LangGraphOrchestrator instance
        """
        orchestrator = LangGraphOrchestrator(
            phase=phase,
            enable_intelligent_routing=enable_intelligent_routing,
            enable_persistence=enable_persistence
        )

        # Add custom nodes if provided
        if custom_nodes:
            for name, node_func in custom_nodes.items():
                orchestrator.add_custom_node(name, node_func)

        # Build feature description
        features = []
        if phase >= 1:
            features.append("consolidated_analysis")
        if phase >= 2:
            features.append("parallel_processing")
        if phase >= 3:
            features.extend(["persistent_state", "advanced_caching", "performance_monitoring"])
        if enable_intelligent_routing:
            features.append("intelligent_routing")

        logger.info(f"Created LangGraph orchestrator phase {phase} with features: {', '.join(features)}")
        return orchestrator

    @staticmethod
    def create_development_orchestrator() -> LangGraphOrchestrator:
        """
        Create an orchestrator optimized for development.

        Returns:
            Development-optimized LangGraphOrchestrator
        """
        return LangGraphOrchestratorFactory.create_orchestrator(
            phase=3,
            enable_intelligent_routing=True,
            enable_persistence=True
        )

    @staticmethod
    def create_production_orchestrator() -> LangGraphOrchestrator:
        """
        Create an orchestrator optimized for production.

        Returns:
            Production-optimized LangGraphOrchestrator
        """
        return LangGraphOrchestratorFactory.create_orchestrator(
            phase=3,
            enable_intelligent_routing=True,
            enable_persistence=True
        )

    async def get_system_health(self) -> Dict[str, Any]:
        """
        Get comprehensive system health information for Phase 3 monitoring.

        Returns:
            System health information including cache and checkpoint stats
        """
        health_info = {
            "orchestrator": {
                "phase": self.phase,
                "intelligent_routing": self.enable_intelligent_routing,
                "persistence_enabled": self.enable_persistence,
                "workflow_nodes": len(self.workflow.nodes) if self.workflow else 0,
                "compiled": self.compiled_workflow is not None
            }
        }

        # Phase 3: Add cache and checkpoint stats
        if self.phase >= 3 and self.cache:
            try:
                cache_stats = self.cache.get_stats()
                health_info["cache"] = cache_stats

                # Get database stats if using persistent storage
                if hasattr(self.checkpointer, 'sqlite_saver'):
                    db_stats = self.checkpointer.sqlite_saver.get_database_stats()
                    health_info["database"] = db_stats

                # Get memory cache stats if using hybrid checkpointing
                if hasattr(self.checkpointer, 'memory_saver'):
                    memory_stats = self.checkpointer.memory_saver.get_cache_stats()
                    health_info["memory_cache"] = memory_stats

            except Exception as e:
                health_info["cache"] = {"error": str(e)}

        # Get monitoring stats
        try:
            monitoring_stats = langgraph_monitor.get_stats(time_window=3600)  # Last hour
            health_info["monitoring"] = {
                "last_hour": monitoring_stats.__dict__,
                "recommendations": langgraph_monitor.get_optimization_recommendations()
            }
        except Exception as e:
            health_info["monitoring"] = {"error": str(e)}

        return health_info

    async def cleanup_system(self, days_old: int = 7) -> Dict[str, Any]:
        """
        Clean up old data to prevent system bloat.

        Args:
            days_old: Age in days of data to delete

        Returns:
            Cleanup results
        """
        cleanup_results = {}

        try:
            # Phase 3: Clean up old checkpoints
            if self.phase >= 3 and hasattr(self.checkpointer, 'sqlite_saver'):
                old_checkpoints = self.checkpointer.sqlite_saver.cleanup_old_checkpoints(days_old)
                cleanup_results["old_checkpoints_removed"] = old_checkpoints

            # Clean up memory cache
            if self.cache:
                memory_usage = self.cache.get_memory_usage()
                if memory_usage["estimated_size_mb"] > 100:  # If over 100MB
                    await self.cache.cleanup_expired()
                    cleanup_results["memory_cache_cleaned"] = True

            cleanup_results["success"] = True
            logger.info(f"System cleanup completed: {cleanup_results}")

        except Exception as e:
            cleanup_results["error"] = str(e)
            logger.error(f"System cleanup failed: {e}")

        return cleanup_results

    async def get_performance_report(self, time_window: int = 3600) -> Dict[str, Any]:
        """
        Get detailed performance report.

        Args:
            time_window: Time window in seconds

        Returns:
            Detailed performance report
        """
        try:
            # Get basic stats
            stats = langgraph_monitor.get_stats(time_window)

            # Get orchestrator-specific info
            orchestrator_info = {
                "phase": self.phase,
                "intelligent_routing": self.enable_intelligent_routing,
                "persistence": self.enable_persistence,
                "nodes": len(self.workflow.nodes) if self.workflow else 0
            }

            # Get system health
            health = await self.get_system_health()

            return {
                "timestamp": time.time(),
                "time_window_seconds": time_window,
                "orchestrator": orchestrator_info,
                "performance": stats.__dict__,
                "system_health": health,
                "recommendations": langgraph_monitor.get_optimization_recommendations()
            }

        except Exception as e:
            return {
                "error": str(e),
                "timestamp": time.time(),
                "time_window_seconds": time_window
            }

    def add_custom_node(self, name: str, node_func):
        """
        Add a custom node to the workflow (for future extensibility).

        Args:
            name: Name of the node
            node_func: Node function
        """
        self.workflow.add_node(name, node_func)
        logger.info(f"Added custom node: {name}")

    @staticmethod
    def create_development_orchestrator() -> LangGraphOrchestrator:
        """
        Create an orchestrator optimized for development.

        Returns:
            Development-optimized LangGraphOrchestrator
        """
        return LangGraphOrchestratorFactory.create_orchestrator(
            checkpoint_backend="memory",
            enable_persistence=False
        )

    @staticmethod
    def create_production_orchestrator() -> LangGraphOrchestrator:
        """
        Create an orchestrator optimized for production.

        Returns:
            Production-optimized LangGraphOrchestrator
        """
        # In Phase 3, this will use persistent checkpointing
        return LangGraphOrchestratorFactory.create_orchestrator(
            checkpoint_backend="sqlite",  # To be implemented in Phase 3
            enable_persistence=True
        )