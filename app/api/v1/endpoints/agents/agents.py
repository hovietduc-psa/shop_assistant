"""
Agent management endpoints.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from loguru import logger

router = APIRouter(prefix="/agents", tags=["Agent Management"])


class AgentStatus(str, Enum):
    """Agent status values."""
    AVAILABLE = "available"
    BUSY = "busy"
    AWAY = "away"
    OFFLINE = "offline"
    IN_BREAK = "in_break"


class AgentRole(str, Enum):
    """Agent role values."""
    AGENT = "agent"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class AgentSkill(BaseModel):
    """Agent skill model."""
    name: str
    level: int = Field(..., ge=1, le=5, description="Skill level 1-5")
    category: str = Field(..., description="Skill category")
    certified_at: Optional[datetime] = None


class AgentCreate(BaseModel):
    """Create agent request."""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = None
    role: AgentRole = AgentRole.AGENT
    department: Optional[str] = None
    skills: List[AgentSkill] = Field(default_factory=list)
    max_concurrent_chats: int = Field(5, ge=1, le=20)
    working_hours: Dict[str, Any] = Field(default_factory=lambda: {
        "monday": {"start": "09:00", "end": "17:00"},
        "tuesday": {"start": "09:00", "end": "17:00"},
        "wednesday": {"start": "09:00", "end": "17:00"},
        "thursday": {"start": "09:00", "end": "17:00"},
        "friday": {"start": "09:00", "end": "17:00"},
        "saturday": None,
        "sunday": None
    })
    timezone: str = Field("UTC", description="Agent timezone")


class AgentUpdate(BaseModel):
    """Update agent request."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    phone: Optional[str] = None
    role: Optional[AgentRole] = None
    department: Optional[str] = None
    skills: Optional[List[AgentSkill]] = None
    max_concurrent_chats: Optional[int] = Field(None, ge=1, le=20)
    working_hours: Optional[Dict[str, Any]] = None
    timezone: Optional[str] = None
    status: Optional[str] = None


class Agent(BaseModel):
    """Agent model."""
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str]
    role: AgentRole
    department: Optional[str]
    skills: List[AgentSkill]
    max_concurrent_chats: int
    working_hours: Dict[str, Any]
    timezone: str
    status: AgentStatus
    is_active: bool
    current_chats: int = 0
    total_chats: int = 0
    avg_response_time_seconds: float = 0.0
    customer_satisfaction_score: float = 0.0
    created_at: datetime
    updated_at: datetime
    last_seen: Optional[datetime] = None


class AgentList(BaseModel):
    """Agent list response."""
    agents: List[Agent]
    total_count: int
    page: int
    limit: int
    has_more: bool


class AgentStats(BaseModel):
    """Agent statistics."""
    agent_id: str
    total_chats: int
    avg_response_time_seconds: float
    customer_satisfaction_score: float
    chat_completion_rate: float
    avg_chat_duration_minutes: float
    active_chats: int
    available_hours_today: float
    utilization_rate: float


# Mock data storage (in production, this would be a database)
agents_db: Dict[str, Agent] = {}
agent_stats_db: Dict[str, AgentStats] = {}


@router.post("/", response_model=Agent)
async def create_agent(agent_data: AgentCreate):
    """Create a new agent."""
    try:
        # Check if agent with email already exists
        existing_agent = next(
            (a for a in agents_db.values() if a.email == agent_data.email),
            None
        )
        if existing_agent:
            raise HTTPException(status_code=400, detail="Agent with this email already exists")

        # Generate agent ID
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()

        # Create agent
        agent = Agent(
            id=agent_id,
            email=agent_data.email,
            first_name=agent_data.first_name,
            last_name=agent_data.last_name,
            phone=agent_data.phone,
            role=agent_data.role,
            department=agent_data.department,
            skills=agent_data.skills,
            max_concurrent_chats=agent_data.max_concurrent_chats,
            working_hours=agent_data.working_hours,
            timezone=agent_data.timezone,
            status=AgentStatus.OFFLINE,
            is_active=True,
            created_at=now,
            updated_at=now
        )

        # Store agent
        agents_db[agent_id] = agent

        # Initialize agent stats
        agent_stats_db[agent_id] = AgentStats(
            agent_id=agent_id,
            total_chats=0,
            avg_response_time_seconds=0.0,
            customer_satisfaction_score=0.0,
            chat_completion_rate=0.0,
            avg_chat_duration_minutes=0.0,
            active_chats=0,
            available_hours_today=0.0,
            utilization_rate=0.0
        )

        logger.info(f"Created agent: {agent_id}")
        return agent

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}")
        raise HTTPException(status_code=500, detail="Failed to create agent")


@router.get("/", response_model=AgentList)
async def list_agents(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """List agents with filtering and pagination."""
    try:
        # Filter agents
        filtered_agents = list(agents_db.values())

        if status:
            filtered_agents = [a for a in filtered_agents if a.status == status]

        if role:
            filtered_agents = [a for a in filtered_agents if a.role == role]

        if department:
            filtered_agents = [a for a in filtered_agents if a.department == department]

        if search:
            search_lower = search.lower()
            filtered_agents = [
                a for a in filtered_agents
                if search_lower in a.first_name.lower() or
                   search_lower in a.last_name.lower() or
                   search_lower in a.email.lower()
            ]

        # Sort by last name
        filtered_agents.sort(key=lambda x: x.last_name.lower())

        # Pagination
        total_count = len(filtered_agents)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_agents = filtered_agents[start_idx:end_idx]

        return AgentList(
            agents=paginated_agents,
            total_count=total_count,
            page=page,
            limit=limit,
            has_more=end_idx < total_count
        )

    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    """Get agent by ID."""
    agent = agents_db.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent_data: AgentUpdate):
    """Update agent information."""
    agent = agents_db.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # Update fields
        if agent_data.first_name is not None:
            agent.first_name = agent_data.first_name
        if agent_data.last_name is not None:
            agent.last_name = agent_data.last_name
        if agent_data.phone is not None:
            agent.phone = agent_data.phone
        if agent_data.role is not None:
            agent.role = agent_data.role
        if agent_data.department is not None:
            agent.department = agent_data.department
        if agent_data.skills is not None:
            agent.skills = agent_data.skills
        if agent_data.max_concurrent_chats is not None:
            agent.max_concurrent_chats = agent_data.max_concurrent_chats
        if agent_data.working_hours is not None:
            agent.working_hours = agent_data.working_hours
        if agent_data.timezone is not None:
            agent.timezone = agent_data.timezone
        if agent_data.status is not None:
            agent.status = AgentStatus(agent_data.status)

        agent.updated_at = datetime.utcnow()

        logger.info(f"Updated agent: {agent_id}")
        return agent

    except Exception as e:
        logger.error(f"Error updating agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update agent")


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent."""
    agent = agents_db.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # Soft delete - mark as inactive
        agent.is_active = False
        agent.status = AgentStatus.OFFLINE
        agent.updated_at = datetime.utcnow()

        # Remove from active agents
        del agents_db[agent_id]
        if agent_id in agent_stats_db:
            del agent_stats_db[agent_id]

        logger.info(f"Deleted agent: {agent_id}")
        return {"message": "Agent deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")


@router.post("/{agent_id}/status")
async def update_agent_status(agent_id: str, status: str, background_tasks: BackgroundTasks):
    """Update agent status."""
    agent = agents_db.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        old_status = agent.status
        agent.status = AgentStatus(status)
        agent.last_seen = datetime.utcnow()
        agent.updated_at = datetime.utcnow()

        # Log status change
        logger.info(f"Agent {agent_id} status changed from {old_status} to {status}")

        # Trigger background tasks for status change
        if status == AgentStatus.AVAILABLE and old_status != AgentStatus.AVAILABLE:
            background_tasks.add_task(notify_agent_available, agent_id)
        elif status == AgentStatus.OFFLINE and old_status != AgentStatus.OFFLINE:
            background_tasks.add_task(notify_agent_offline, agent_id)

        return {"message": f"Agent status updated to {status}"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")
    except Exception as e:
        logger.error(f"Error updating agent status {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update agent status")


@router.get("/{agent_id}/stats", response_model=AgentStats)
async def get_agent_stats(agent_id: str, days: int = Query(30, ge=1, le=90)):
    """Get agent performance statistics."""
    stats = agent_stats_db.get(agent_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        # In a real implementation, this would calculate stats from actual data
        # For now, return the mock stats
        return stats

    except Exception as e:
        logger.error(f"Error getting agent stats {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent stats")


@router.get("/available", response_model=List[Agent])
async def get_available_agents(department: Optional[str] = None, skill: Optional[str] = None):
    """Get list of available agents."""
    try:
        available_agents = [
            agent for agent in agents_db.values()
            if (agent.status == AgentStatus.AVAILABLE and
                agent.is_active and
                agent.current_chats < agent.max_concurrent_chats)
        ]

        # Filter by department
        if department:
            available_agents = [
                a for a in available_agents
                if a.department == department
            ]

        # Filter by skill
        if skill:
            available_agents = [
                a for a in available_agents
                if any(s.name.lower() == skill.lower() for s in a.skills)
            ]

        # Sort by availability (least current chats first)
        available_agents.sort(key=lambda x: x.current_chats)

        return available_agents

    except Exception as e:
        logger.error(f"Error getting available agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to get available agents")


@router.get("/departments", response_model=List[str])
async def get_departments():
    """Get list of all departments."""
    try:
        departments = set()
        for agent in agents_db.values():
            if agent.department:
                departments.add(agent.department)
        return sorted(list(departments))

    except Exception as e:
        logger.error(f"Error getting departments: {e}")
        raise HTTPException(status_code=500, detail="Failed to get departments")


@router.get("/skills", response_model=List[str])
async def get_skills():
    """Get list of all skills."""
    try:
        skills = set()
        for agent in agents_db.values():
            for skill in agent.skills:
                skills.add(skill.name)
        return sorted(list(skills))

    except Exception as e:
        logger.error(f"Error getting skills: {e}")
        raise HTTPException(status_code=500, detail="Failed to get skills")


# Background task functions
async def notify_agent_available(agent_id: str):
    """Background task to notify when agent becomes available."""
    logger.info(f"Notification: Agent {agent_id} is now available")
    # In a real implementation, this would send notifications to routing system


async def notify_agent_offline(agent_id: str):
    """Background task to notify when agent goes offline."""
    logger.info(f"Notification: Agent {agent_id} is now offline")
    # In a real implementation, this would update routing system


# Initialize some mock data for testing
def _init_mock_data():
    """Initialize mock agent data for testing."""
    if not agents_db:
        # Create mock agents
        mock_agents = [
            {
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": AgentRole.AGENT,
                "department": "Sales",
                "skills": [
                    AgentSkill(name="Product Knowledge", level=4, category="Technical"),
                    AgentSkill(name="Customer Service", level=5, category="Service")
                ]
            },
            {
                "email": "jane.smith@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "role": AgentRole.SUPERVISOR,
                "department": "Support",
                "skills": [
                    AgentSkill(name="Technical Support", level=5, category="Technical"),
                    AgentSkill(name="Problem Solving", level=4, category="Analytical")
                ]
            },
            {
                "email": "bob.wilson@example.com",
                "first_name": "Bob",
                "last_name": "Wilson",
                "role": AgentRole.AGENT,
                "department": "Support",
                "skills": [
                    AgentSkill(name="Chat Support", level=3, category="Communication"),
                    AgentSkill(name="Product Knowledge", level=4, category="Technical")
                ]
            }
        ]

        for agent_data in mock_agents:
            agent_create = AgentCreate(**agent_data)
            # Create agent directly without await since this is sync initialization
            agent_id = f"agent_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()

            agent = Agent(
                id=agent_id,
                email=agent_create.email,
                first_name=agent_create.first_name,
                last_name=agent_create.last_name,
                phone=agent_create.phone,
                role=agent_create.role,
                department=agent_create.department,
                skills=agent_create.skills,
                max_concurrent_chats=agent_create.max_concurrent_chats,
                working_hours=agent_create.working_hours,
                timezone=agent_create.timezone,
                status=AgentStatus.AVAILABLE,
                is_active=True,
                created_at=now,
                updated_at=now
            )

            agents_db[agent_id] = agent
            agent_stats_db[agent_id] = AgentStats(
                agent_id=agent_id,
                total_chats=0,
                avg_response_time_seconds=0.0,
                customer_satisfaction_score=0.0,
                chat_completion_rate=0.0,
                avg_chat_duration_minutes=0.0,
                active_chats=0,
                available_hours_today=0.0,
                utilization_rate=0.0
            )


# Initialize mock data
_init_mock_data()

# Export the router for import
agents_router = router