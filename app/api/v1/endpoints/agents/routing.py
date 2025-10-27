"""
Conversation routing and assignment endpoints.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

router = APIRouter(prefix="/routing", tags=["Conversation Routing"])


class AssignmentStrategy(str, Enum):
    """Assignment strategy types."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    SKILL_BASED = "skill_based"
    PRIORITY = "priority"
    MANUAL = "manual"


class ConversationPriority(str, Enum):
    """Conversation priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RoutingRule(BaseModel):
    """Routing rule model."""
    id: str
    name: str
    conditions: Dict[str, Any]
    actions: Dict[str, Any]
    priority: int = 1
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class AssignmentRequest(BaseModel):
    """Assignment request model."""
    conversation_id: str
    strategy: AssignmentStrategy = AssignmentStrategy.LEAST_LOADED
    requirements: Optional[Dict[str, Any]] = None
    preferred_agent_id: Optional[str] = None
    exclude_agent_ids: List[str] = Field(default_factory=list)
    priority: ConversationPriority = ConversationPriority.NORMAL


class Assignment(BaseModel):
    """Assignment model."""
    id: str
    conversation_id: str
    agent_id: str
    assigned_at: datetime
    assigned_by: str  # System or supervisor ID
    strategy: AssignmentStrategy
    priority: ConversationPriority
    status: str  # active, completed, transferred
    transferred_to: Optional[str] = None
    notes: Optional[str] = None


class QueueItem(BaseModel):
    """Queue item model."""
    id: str
    conversation_id: str
    customer_id: Optional[str]
    priority: ConversationPriority
    wait_time_seconds: int
    requirements: Dict[str, Any] = Field(default_factory=dict)
    queued_at: datetime
    estimated_wait_time: Optional[int] = None


class QueueStats(BaseModel):
    """Queue statistics."""
    total_waiting: int
    avg_wait_time_minutes: float
    longest_wait_time_minutes: float
    agents_available: int
    service_level_agreement: float
    priority_breakdown: Dict[str, int]


# Mock data storage (in production, this would be a database)
assignments_db: Dict[str, Assignment] = {}
routing_rules_db: Dict[str, RoutingRule] = {}
queue_db: Dict[str, QueueItem] = {}


@router.post("/assign", response_model=Assignment)
async def assign_conversation(request: AssignmentRequest, background_tasks: BackgroundTasks):
    """Assign a conversation to an agent."""
    try:
        # Check if conversation is already assigned
        existing_assignment = next(
            (a for a in assignments_db.values()
             if a.conversation_id == request.conversation_id and a.status == "active"),
            None
        )
        if existing_assignment:
            raise HTTPException(
                status_code=400,
                detail="Conversation is already assigned"
            )

        # Find suitable agent
        agent_id = await _find_suitable_agent(request)

        if not agent_id:
            # Add to queue
            queue_item = QueueItem(
                id=f"queue_{uuid.uuid4().hex[:12]}",
                conversation_id=request.conversation_id,
                customer_id=request.requirements.get("customer_id") if request.requirements else None,
                priority=request.priority,
                wait_time_seconds=0,
                requirements=request.requirements or {},
                queued_at=datetime.utcnow()
            )
            queue_db[queue_item.id] = queue_item

            raise HTTPException(
                status_code=404,
                detail=f"No suitable agents available. Conversation added to queue."
            )

        # Create assignment
        assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
        assignment = Assignment(
            id=assignment_id,
            conversation_id=request.conversation_id,
            agent_id=agent_id,
            assigned_at=datetime.utcnow(),
            assigned_by="system",
            strategy=request.strategy,
            priority=request.priority,
            status="active"
        )

        assignments_db[assignment_id] = assignment

        # Update agent status and load
        background_tasks.add_task(update_agent_load, agent_id, 1)

        logger.info(f"Assigned conversation {request.conversation_id} to agent {agent_id}")
        return assignment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign conversation")


@router.put("/transfer/{assignment_id}")
async def transfer_conversation(
    assignment_id: str,
    new_agent_id: str,
    background_tasks: BackgroundTasks,
    reason: Optional[str] = None
):
    """Transfer a conversation to another agent."""
    assignment = assignments_db.get(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.status != "active":
        raise HTTPException(status_code=400, detail="Conversation is not active")

    try:
        old_agent_id = assignment.agent_id
        assignment.agent_id = new_agent_id
        assignment.transferred_to = new_agent_id
        assignment.notes = reason
        assignment.status = "transferred"

        # Create new assignment for the new agent
        new_assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
        new_assignment = Assignment(
            id=new_assignment_id,
            conversation_id=assignment.conversation_id,
            agent_id=new_agent_id,
            assigned_at=datetime.utcnow(),
            assigned_by="transfer",
            strategy=AssignmentStrategy.MANUAL,
            priority=assignment.priority,
            status="active",
            notes=f"Transferred from agent {old_agent_id}. Reason: {reason}"
        )

        assignments_db[new_assignment_id] = new_assignment

        # Update agent loads
        background_tasks.add_task(update_agent_load, old_agent_id, -1)
        background_tasks.add_task(update_agent_load, new_agent_id, 1)

        logger.info(f"Transferred conversation {assignment.conversation_id} from {old_agent_id} to {new_agent_id}")
        return {"message": "Conversation transferred successfully"}

    except Exception as e:
        logger.error(f"Error transferring conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to transfer conversation")


@router.post("/complete/{assignment_id}")
async def complete_assignment(assignment_id: str, background_tasks: BackgroundTasks):
    """Mark an assignment as completed."""
    assignment = assignments_db.get(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment.status != "active":
        raise HTTPException(status_code=400, detail="Assignment is not active")

    try:
        assignment.status = "completed"

        # Update agent load
        background_tasks.add_task(update_agent_load, assignment.agent_id, -1)

        logger.info(f"Completed assignment {assignment_id}")
        return {"message": "Assignment completed successfully"}

    except Exception as e:
        logger.error(f"Error completing assignment: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete assignment")


@router.get("/queue", response_model=List[QueueItem])
async def get_queue(
    priority: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """Get current conversation queue."""
    try:
        # Filter queue items
        queue_items = list(queue_db.values())

        if priority:
            queue_items = [q for q in queue_items if q.priority == priority]

        # Sort by priority and wait time
        priority_order = {
            ConversationPriority.URGENT: 0,
            ConversationPriority.HIGH: 1,
            ConversationPriority.NORMAL: 2,
            ConversationPriority.LOW: 3
        }

        queue_items.sort(key=lambda x: (
            priority_order.get(x.priority, 2),
            x.wait_time_seconds
        ))

        return queue_items[:limit]

    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue")


@router.get("/queue/stats", response_model=QueueStats)
async def get_queue_stats():
    """Get queue statistics."""
    try:
        queue_items = list(queue_db.values())

        if not queue_items:
            return QueueStats(
                total_waiting=0,
                avg_wait_time_minutes=0.0,
                longest_wait_time_minutes=0.0,
                agents_available=0,
                service_level_agreement=100.0,
                priority_breakdown={}
            )

        # Calculate statistics
        total_waiting = len(queue_items)
        total_wait_time = sum(q.wait_time_seconds for q in queue_items)
        avg_wait_time = total_wait_time / len(queue_items) / 60
        longest_wait_time = max(q.wait_time_seconds for q in queue_items) / 60

        # Count by priority
        priority_breakdown = {}
        for item in queue_items:
            priority_breakdown[item.priority] = priority_breakdown.get(item.priority, 0) + 1

        # Get available agents (mock implementation)
        agents_available = await _get_available_agents_count()

        # Calculate SLA (Service Level Agreement)
        sla_target = 180  # 3 minutes
        served_within_sla = len([q for q in queue_items if q.wait_time_seconds <= sla_target])
        service_level_agreement = (served_within_sla / total_waiting) * 100 if total_waiting > 0 else 100

        return QueueStats(
            total_waiting=total_waiting,
            avg_wait_time_minutes=round(avg_wait_time, 2),
            longest_wait_time_minutes=round(longest_wait_time, 2),
            agents_available=agents_available,
            service_level_agreement=round(service_level_agreement, 2),
            priority_breakdown=priority_breakdown
        )

    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get queue stats")


@router.get("/assignments", response_model=List[Assignment])
async def get_assignments(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """Get assignments with filtering."""
    try:
        assignments = list(assignments_db.values())

        # Filter by agent
        if agent_id:
            assignments = [a for a in assignments if a.agent_id == agent_id]

        # Filter by status
        if status:
            assignments = [a for a in assignments if a.status == status]

        # Sort by assignment time (newest first)
        assignments.sort(key=lambda x: x.assigned_at, reverse=True)

        return assignments[:limit]

    except Exception as e:
        logger.error(f"Error getting assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get assignments")


@router.post("/rules", response_model=RoutingRule)
async def create_routing_rule(rule_data: Dict[str, Any]):
    """Create a new routing rule."""
    try:
        import uuid
        rule_id = f"rule_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        rule = RoutingRule(
            id=rule_id,
            name=rule_data["name"],
            conditions=rule_data["conditions"],
            actions=rule_data["actions"],
            priority=rule_data.get("priority", 1),
            enabled=rule_data.get("enabled", True),
            created_at=now,
            updated_at=now
        )

        routing_rules_db[rule_id] = rule

        logger.info(f"Created routing rule: {rule_id}")
        return rule

    except Exception as e:
        logger.error(f"Error creating routing rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create routing rule")


@router.get("/rules", response_model=list[RoutingRule])
async def get_routing_rules():
    """Get all routing rules."""
    try:
        rules = list(routing_rules_db.values())
        rules.sort(key=lambda x: x.priority)
        return rules

    except Exception as e:
        logger.error(f"Error getting routing rules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get routing rules")


@router.delete("/rules/{rule_id}")
async def delete_routing_rule(rule_id: str):
    """Delete a routing rule."""
    if rule_id not in routing_rules_db:
        raise HTTPException(status_code=404, detail="Routing rule not found")

    try:
        del routing_rules_db[rule_id]
        logger.info(f"Deleted routing rule: {rule_id}")
        return {"message": "Routing rule deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting routing rule: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete routing rule")


@router.post("/process-queue", response_model=dict)
async def process_queue(background_tasks: BackgroundTasks):
    """Manually process the conversation queue."""
    try:
        processed_count = 0
        queue_items = list(queue_db.values())

        # Sort by priority and wait time
        priority_order = {
            ConversationPriority.URGENT: 0,
            ConversationPriority.HIGH: 1,
            ConversationPriority.NORMAL: 2,
            ConversationPriority.LOW: 3
        }

        queue_items.sort(key=lambda x: (
            priority_order.get(x.priority, 2),
            x.wait_time_seconds
        ))

        # Process queue items
        for item in queue_items:
            try:
                # Create assignment request
                assignment_request = AssignmentRequest(
                    conversation_id=item.conversation_id,
                    strategy=AssignmentStrategy.LEAST_LOADED,
                    requirements=item.requirements,
                    priority=item.priority
                )

                # Try to assign
                agent_id = await _find_suitable_agent(assignment_request)
                if agent_id:
                    # Create assignment
                    assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
                    assignment = Assignment(
                        id=assignment_id,
                        conversation_id=item.conversation_id,
                        agent_id=agent_id,
                        assigned_at=datetime.utcnow(),
                        assigned_by="queue_processor",
                        strategy=assignment_request.strategy,
                        priority=assignment_request.priority,
                        status="active"
                    )

                    assignments_db[assignment_id] = assignment

                    # Remove from queue
                    del queue_db[item.id]

                    # Update agent load
                    background_tasks.add_task(update_agent_load, agent_id, 1)

                    processed_count += 1
                    logger.info(f"Processed queue item: {item.conversation_id} assigned to {agent_id}")

            except Exception as e:
                logger.error(f"Error processing queue item {item.id}: {e}")

        return {
            "message": f"Processed {processed_count} items from queue",
            "processed_count": processed_count,
            "remaining_in_queue": len(queue_db)
        }

    except Exception as e:
        logger.error(f"Error processing queue: {e}")
        raise HTTPException(status_code=500, detail="Failed to process queue")


# Helper functions
async def _find_suitable_agent(request: AssignmentRequest) -> Optional[str]:
    """Find a suitable agent for the assignment."""
    from .agents import agents_db, AgentStatus

    # Get all available agents
    available_agents = [
        agent for agent in agents_db.values()
        if (agent.status == AgentStatus.AVAILABLE and
            agent.is_active and
            agent.current_chats < agent.max_concurrent_chats and
            agent.id not in request.exclude_agent_ids)
    ]

    if not available_agents:
        return None

    # Check for preferred agent
    if request.preferred_agent_id:
        preferred_agent = next(
            (a for a in available_agents if a.id == request.preferred_agent_id),
            None
        )
        if preferred_agent:
            return preferred_agent.id

    # Apply assignment strategy
    if request.strategy == AssignmentStrategy.ROUND_ROBIN:
        # Simple round-robin (first available)
        return available_agents[0].id

    elif request.strategy == AssignmentStrategy.LEAST_LOADED:
        # Agent with least current chats
        return min(available_agents, key=lambda x: x.current_chats).id

    elif request.strategy == AssignmentStrategy.SKILL_BASED:
        # Find agent with required skills
        if request.requirements and "required_skills" in request.requirements:
            required_skills = request.requirements["required_skills"]
            for agent in available_agents:
                agent_skills = [s.name.lower() for s in agent.skills]
                if all(skill.lower() in agent_skills for skill in required_skills):
                    return agent.id

        # Fallback to least loaded
        return min(available_agents, key=lambda x: x.current_chats).id

    # Default to least loaded
    return min(available_agents, key=lambda x: x.current_chats).id


async def _get_available_agents_count() -> int:
    """Get count of available agents."""
    from .agents import agents_db, AgentStatus

    return len([
        agent for agent in agents_db.values()
        if agent.status == AgentStatus.AVAILABLE and agent.is_active
    ])


async def update_agent_load(agent_id: str, delta: int):
    """Update agent's current chat load."""
    from .agents import agents_db

    agent = agents_db.get(agent_id)
    if agent:
        agent.current_chats = max(0, agent.current_chats + delta)
        logger.debug(f"Updated agent {agent_id} load by {delta} (current: {agent.current_chats})")


# Export the router for import
routing_router = router