"""
Agent authentication endpoints.
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, EmailStr
from loguru import logger

from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Agent Authentication"])


class AgentLoginRequest(BaseModel):
    """Agent login request."""
    email: EmailStr
    password: str
    agent_id: Optional[str] = None


class AgentLoginResponse(BaseModel):
    """Agent login response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    agent_info: Dict[str, Any]


class AgentTokenRefresh(BaseModel):
    """Token refresh request."""
    refresh_token: str


class MockAgentAuth:
    """Mock agent authentication service."""

    def __init__(self):
        """Initialize mock auth service."""
        # Mock agent database
        self.agents = {
            "agent@shopassistant.com": {
                "id": "agent_001",
                "email": "agent@shopassistant.com",
                "password_hash": "hashed_password_001",
                "name": "John Agent",
                "role": "senior_agent",
                "department": "customer_support",
                "permissions": ["chat", "escalate", "view_analytics"],
                "is_active": True,
                "last_login": None
            },
            "manager@shopassistant.com": {
                "id": "agent_002",
                "email": "manager@shopassistant.com",
                "password_hash": "hashed_password_002",
                "name": "Jane Manager",
                "role": "team_manager",
                "department": "customer_support",
                "permissions": ["chat", "escalate", "view_analytics", "manage_agents"],
                "is_active": True,
                "last_login": None
            }
        }

        # Active tokens storage
        self.active_tokens = {}
        self.refresh_tokens = {}

    def authenticate_agent(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate agent credentials."""
        agent = self.agents.get(email)
        if not agent:
            return None

        # Mock password verification (in real implementation, use proper hashing)
        if not self._verify_password(password, agent["password_hash"]):
            return None

        if not agent["is_active"]:
            return None

        return agent

    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """Mock password verification."""
        # In real implementation, use bcrypt or similar
        mock_passwords = {
            "hashed_password_001": "password123",
            "hashed_password_002": "manager456"
        }
        return mock_passwords.get(hashed_password) == password

    def generate_tokens(self, agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate access and refresh tokens."""
        # Generate mock tokens (in real implementation, use JWT)
        access_token = f"access_token_{uuid.uuid4().hex}"
        refresh_token = f"refresh_token_{uuid.uuid4().hex}"

        # Store tokens
        self.active_tokens[access_token] = {
            "agent_id": agent_info["id"],
            "email": agent_info["email"],
            "expires_at": datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        }

        self.refresh_tokens[refresh_token] = {
            "agent_id": agent_info["id"],
            "email": agent_info["email"],
            "expires_at": datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        }

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate access token."""
        token_data = self.active_tokens.get(token)
        if not token_data:
            return None

        if datetime.utcnow() > token_data["expires_at"]:
            # Token expired, remove it
            self.active_tokens.pop(token, None)
            return None

        return token_data

    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token."""
        token_data = self.refresh_tokens.get(refresh_token)
        if not token_data:
            return None

        if datetime.utcnow() > token_data["expires_at"]:
            # Refresh token expired
            self.refresh_tokens.pop(refresh_token, None)
            return None

        # Get agent info
        agent = None
        for agent_data in self.agents.values():
            if agent_data["id"] == token_data["agent_id"]:
                agent = agent_data
                break

        if not agent:
            return None

        # Generate new tokens
        return self.generate_tokens(agent)

    def logout(self, access_token: str) -> bool:
        """Logout agent by invalidating tokens."""
        # Remove access token
        token_data = self.active_tokens.pop(access_token, None)
        if not token_data:
            return False

        # Also remove associated refresh tokens
        to_remove = []
        for refresh_token, refresh_data in self.refresh_tokens.items():
            if refresh_data["agent_id"] == token_data["agent_id"]:
                to_remove.append(refresh_token)

        for refresh_token in to_remove:
            self.refresh_tokens.pop(refresh_token, None)

        return True

    def get_agent_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Get agent information from token."""
        token_data = self.validate_token(token)
        if not token_data:
            return None

        for agent in self.agents.values():
            if agent["id"] == token_data["agent_id"]:
                return {
                    "id": agent["id"],
                    "email": agent["email"],
                    "name": agent["name"],
                    "role": agent["role"],
                    "department": agent["department"],
                    "permissions": agent["permissions"]
                }

        return None


# Global auth service
agent_auth = MockAgentAuth()


@router.post("/login", response_model=AgentLoginResponse)
async def agent_login(request: AgentLoginRequest):
    """Authenticate agent and return tokens."""
    try:
        # Authenticate agent
        agent = agent_auth.authenticate_agent(request.email, request.password)
        if not agent:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Update last login
        agent["last_login"] = datetime.utcnow()

        # Generate tokens
        tokens = agent_auth.generate_tokens(agent)

        # Prepare agent info for response
        agent_info = {
            "id": agent["id"],
            "email": agent["email"],
            "name": agent["name"],
            "role": agent["role"],
            "department": agent["department"],
            "permissions": agent["permissions"],
            "last_login": agent["last_login"].isoformat()
        }

        logger.info(f"Agent logged in: {agent['email']} ({agent['id']})")

        return AgentLoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens["expires_in"],
            agent_info=agent_info
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(request: AgentTokenRefresh):
    """Refresh access token."""
    try:
        tokens = agent_auth.refresh_access_token(request.refresh_token)
        if not tokens:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        logger.info("Access token refreshed")

        return {
            "access_token": tokens["access_token"],
            "expires_in": tokens["expires_in"],
            "token_type": "bearer"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.post("/logout")
async def agent_logout(authorization: str = None):
    """Logout agent and invalidate tokens."""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Extract token from "Bearer <token>"
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

        success = agent_auth.logout(token)
        if not success:
            raise HTTPException(status_code=401, detail="Invalid token")

        logger.info("Agent logged out successfully")

        return {"message": "Logged out successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/me")
async def get_current_agent(authorization: str = None):
    """Get current agent information."""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Extract token from "Bearer <token>"
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

        agent_info = agent_auth.get_agent_info(token)
        if not agent_info:
            raise HTTPException(status_code=401, detail="Invalid token")

        return agent_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get agent info error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent information")


@router.get("/verify")
async def verify_token(authorization: str = None):
    """Verify if token is valid."""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Extract token from "Bearer <token>"
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization

        token_data = agent_auth.validate_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {
            "valid": True,
            "agent_id": token_data["agent_id"],
            "email": token_data["email"],
            "expires_at": token_data["expires_at"].isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(status_code=500, detail="Token verification failed")


@router.get("/stats")
async def get_auth_stats():
    """Get authentication statistics."""
    try:
        return {
            "active_agents": len(agent_auth.active_tokens),
            "active_refresh_tokens": len(agent_auth.refresh_tokens),
            "total_registered_agents": len(agent_auth.agents),
            "active_agents_list": [
                {
                    "agent_id": data["agent_id"],
                    "email": data["email"],
                    "expires_at": data["expires_at"].isoformat()
                }
                for data in agent_auth.active_tokens.values()
            ]
        }

    except Exception as e:
        logger.error(f"Auth stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get auth statistics")


# Export the router for import
auth_router = router