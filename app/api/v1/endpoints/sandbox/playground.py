"""
API sandbox playground for interactive testing.
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

from app.core.api.monitoring import get_api_monitor
from app.core.config import settings

router = APIRouter(prefix="/sandbox", tags=["API Sandbox"])


class SandboxSession(BaseModel):
    """Sandbox session information."""
    session_id: str
    created_at: datetime
    last_activity: datetime
    user_id: Optional[str] = None
    api_key: str
    quota_limits: Dict[str, int]
    current_usage: Dict[str, int] = Field(default_factory=dict)
    environment: str = "sandbox"
    isolated_data: bool = True


class APIRequest(BaseModel):
    """API request model for sandbox."""
    method: str = Field(..., description="HTTP method")
    endpoint: str = Field(..., description="API endpoint")
    headers: Dict[str, str] = Field(default_factory=dict, description="Request headers")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body")
    mock_mode: bool = Field(True, description="Use mock responses instead of real API")


class APIResponse(BaseModel):
    """API response model."""
    status_code: int
    headers: Dict[str, str]
    body: Any
    duration_ms: float
    mock_mode: bool
    timestamp: datetime


class MockDataStore:
    """In-memory mock data store for sandbox."""

    def __init__(self):
        """Initialize mock data store."""
        self.data = {
            "products": [
                {
                    "id": "mock_product_1",
                    "title": "Mock Product 1",
                    "price": 29.99,
                    "description": "This is a mock product for testing",
                    "in_stock": True,
                    "category": "electronics"
                },
                {
                    "id": "mock_product_2",
                    "title": "Mock Product 2",
                    "price": 49.99,
                    "description": "Another mock product",
                    "in_stock": False,
                    "category": "clothing"
                }
            ],
            "orders": [
                {
                    "id": "mock_order_1",
                    "status": "completed",
                    "total": 79.98,
                    "created_at": "2024-01-15T10:30:00Z",
                    "customer_id": "mock_customer_1"
                }
            ],
            "customers": [
                {
                    "id": "mock_customer_1",
                    "name": "Test Customer",
                    "email": "test@example.com",
                    "orders_count": 1
                }
            ]
        }
        self.next_ids = {
            "products": 3,
            "orders": 2,
            "customers": 2
        }

    def get_data(self, resource_type: str, resource_id: Optional[str] = None) -> Any:
        """Get mock data."""
        if resource_type not in self.data:
            raise HTTPException(status_code=404, detail=f"Resource type '{resource_type}' not found")

        if resource_id:
            for item in self.data[resource_type]:
                if item.get("id") == resource_id:
                    return item
            raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")

        return self.data[resource_type]

    def create_data(self, resource_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create mock data."""
        if resource_type not in self.data:
            raise HTTPException(status_code=404, detail=f"Resource type '{resource_type}' not found")

        # Generate ID
        resource_id = f"mock_{resource_type}_{self.next_ids[resource_type]}"
        self.next_ids[resource_type] += 1

        # Create resource
        new_resource = {"id": resource_id, **data}
        new_resource["created_at"] = datetime.utcnow().isoformat()
        self.data[resource_type].append(new_resource)

        return new_resource

    def update_data(self, resource_type: str, resource_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update mock data."""
        if resource_type not in self.data:
            raise HTTPException(status_code=404, detail=f"Resource type '{resource_type}' not found")

        for i, item in enumerate(self.data[resource_type]):
            if item.get("id") == resource_id:
                self.data[resource_type][i].update(data)
                self.data[resource_type][i]["updated_at"] = datetime.utcnow().isoformat()
                return self.data[resource_type][i]

        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")

    def delete_data(self, resource_type: str, resource_id: str) -> bool:
        """Delete mock data."""
        if resource_type not in self.data:
            raise HTTPException(status_code=404, detail=f"Resource type '{resource_type}' not found")

        for i, item in enumerate(self.data[resource_type]):
            if item.get("id") == resource_id:
                del self.data[resource_type][i]
                return True

        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")


class SandboxManager:
    """Manages sandbox sessions and operations."""

    def __init__(self):
        """Initialize sandbox manager."""
        self.sessions: Dict[str, SandboxSession] = {}
        self.mock_store = MockDataStore()
        self.default_quota = {
            "requests_per_hour": 100,
            "max_response_size": 1048576,  # 1MB
            "max_concurrent_requests": 5
        }

    def create_session(self, user_id: Optional[str] = None) -> SandboxSession:
        """Create a new sandbox session."""
        session_id = str(uuid.uuid4())
        api_key = f"sandbox_key_{uuid.uuid4().hex[:16]}"

        session = SandboxSession(
            session_id=session_id,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            user_id=user_id,
            api_key=api_key,
            quota_limits=self.default_quota.copy()
        )

        self.sessions[session_id] = session
        logger.info(f"Created sandbox session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SandboxSession]:
        """Get sandbox session."""
        session = self.sessions.get(session_id)
        if session:
            session.last_activity = datetime.utcnow()
        return session

    def execute_request(self, session_id: str, request: APIRequest) -> APIResponse:
        """Execute API request in sandbox."""
        session = self.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sandbox session not found")

        # Check quota
        self._check_quota(session, request)

        start_time = datetime.utcnow()

        try:
            if request.mock_mode:
                response = self._execute_mock_request(request)
            else:
                response = self._execute_real_request(request, session)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Update usage
            session.current_usage["requests_per_hour"] = session.current_usage.get("requests_per_hour", 0) + 1

            return APIResponse(
                status_code=response["status_code"],
                headers=response["headers"],
                body=response["body"],
                duration_ms=duration_ms,
                mock_mode=request.mock_mode,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Sandbox request failed: {e}")

            return APIResponse(
                status_code=500,
                headers={"Content-Type": "application/json"},
                body={"error": str(e), "message": "Sandbox request failed"},
                duration_ms=duration_ms,
                mock_mode=request.mock_mode,
                timestamp=datetime.utcnow()
            )

    def _check_quota(self, session: SandboxSession, request: APIRequest):
        """Check if request is within quota limits."""
        hourly_limit = session.quota_limits.get("requests_per_hour", 100)
        current_usage = session.current_usage.get("requests_per_hour", 0)

        if current_usage >= hourly_limit:
            raise HTTPException(status_code=429, detail="Hourly request quota exceeded")

        # Check response size limit
        if request.body and len(json.dumps(request.body)) > session.quota_limits.get("max_response_size", 1048576):
            raise HTTPException(status_code=413, detail="Request too large")

    def _execute_mock_request(self, request: APIRequest) -> Dict[str, Any]:
        """Execute mock request."""
        # Parse endpoint
        parts = request.endpoint.strip("/").split("/")
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid endpoint format")

        resource_type = parts[1]
        resource_id = parts[2] if len(parts) > 2 else None

        try:
            if request.method.upper() == "GET":
                data = self.mock_store.get_data(resource_type, resource_id)
                return {
                    "status_code": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": data
                }

            elif request.method.upper() == "POST":
                if not request.body:
                    raise HTTPException(status_code=400, detail="Request body required")
                data = self.mock_store.create_data(resource_type, request.body)
                return {
                    "status_code": 201,
                    "headers": {"Content-Type": "application/json"},
                    "body": data
                }

            elif request.method.upper() == "PUT":
                if not resource_id:
                    raise HTTPException(status_code=400, detail="Resource ID required")
                if not request.body:
                    raise HTTPException(status_code=400, detail="Request body required")
                data = self.mock_store.update_data(resource_type, resource_id, request.body)
                return {
                    "status_code": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": data
                }

            elif request.method.upper() == "DELETE":
                if not resource_id:
                    raise HTTPException(status_code=400, detail="Resource ID required")
                self.mock_store.delete_data(resource_type, resource_id)
                return {
                    "status_code": 204,
                    "headers": {},
                    "body": None
                }

            else:
                raise HTTPException(status_code=405, detail="Method not allowed")

        except HTTPException:
            raise
        except Exception as e:
            return {
                "status_code": 500,
                "headers": {"Content-Type": "application/json"},
                "body": {"error": str(e)}
            }

    def _execute_real_request(self, request: APIRequest, session: SandboxSession) -> Dict[str, Any]:
        """Execute real API request (limited in sandbox)."""
        # In a real implementation, this would make actual API calls
        # For security, sandbox mode typically limits real API access
        raise HTTPException(
            status_code=403,
            detail="Real API access is disabled in sandbox mode. Use mock_mode=true instead."
        )

    def cleanup_sessions(self, hours: int = 24):
        """Clean up old sandbox sessions."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        to_remove = []

        for session_id, session in self.sessions.items():
            if session.last_activity < cutoff_time:
                to_remove.append(session_id)

        for session_id in to_remove:
            del self.sessions[session_id]
            logger.info(f"Cleaned up sandbox session: {session_id}")

        return len(to_remove)


# Global sandbox manager
sandbox_manager = SandboxManager()


@router.post("/session/create")
async def create_sandbox_session(user_id: Optional[str] = None):
    """Create a new sandbox session."""
    try:
        session = sandbox_manager.create_session(user_id)
        return {
            "session_id": session.session_id,
            "api_key": session.api_key,
            "quota_limits": session.quota_limits,
            "created_at": session.created_at.isoformat(),
            "environment": session.environment
        }
    except Exception as e:
        logger.error(f"Failed to create sandbox session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create sandbox session")


@router.get("/session/{session_id}")
async def get_sandbox_session(session_id: str):
    """Get sandbox session information."""
    session = sandbox_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sandbox session not found")

    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
        "last_activity": session.last_activity.isoformat(),
        "quota_limits": session.quota_limits,
        "current_usage": session.current_usage,
        "environment": session.environment
    }


@router.post("/session/{session_id}/execute")
async def execute_sandbox_request(session_id: str, request: APIRequest):
    """Execute an API request in the sandbox."""
    try:
        response = sandbox_manager.execute_request(session_id, request)
        return response.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute sandbox request: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute request")


@router.get("/session/{session_id}/mock-data")
async def get_mock_data(session_id: str, resource_type: Optional[str] = None):
    """Get available mock data."""
    session = sandbox_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sandbox session not found")

    if resource_type:
        try:
            data = sandbox_manager.mock_store.get_data(resource_type)
            return {"resource_type": resource_type, "data": data}
        except HTTPException as e:
            raise e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Return all available data types
        return {
            "available_resources": list(sandbox_manager.mock_store.data.keys()),
            "data": sandbox_manager.mock_store.data
        }


@router.post("/session/{session_id}/mock-data/{resource_type}")
async def create_mock_data(session_id: str, resource_type: str, data: Dict[str, Any]):
    """Create mock data in sandbox."""
    session = sandbox_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sandbox session not found")

    try:
        created_data = sandbox_manager.mock_store.create_data(resource_type, data)
        return created_data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/docs")
async def get_sandbox_docs():
    """Get sandbox documentation."""
    return {
        "title": "API Sandbox Documentation",
        "description": "Interactive testing environment for the Shop Assistant AI API",
        "features": [
            "Mock API responses for testing",
            "Isolated test environment",
            "Request quota management",
            "Session-based testing",
            "Real-time request/response inspection"
        ],
        "usage": {
            "create_session": "POST /sandbox/session/create - Create a new sandbox session",
            "execute_request": "POST /sandbox/session/{session_id}/execute - Execute API request",
            "get_session": "GET /sandbox/session/{session_id} - Get session info",
            "mock_data": "GET /sandbox/session/{session_id}/mock-data - Get mock data"
        },
        "example_requests": {
            "get_products": {
                "method": "GET",
                "endpoint": "/api/v1/shopify/products/search",
                "mock_mode": True,
                "body": {
                    "query": "test",
                    "limit": 10
                }
            },
            "create_order": {
                "method": "POST",
                "endpoint": "/api/v1/orders",
                "mock_mode": True,
                "body": {
                    "customer_id": "mock_customer_1",
                    "items": [
                        {"product_id": "mock_product_1", "quantity": 2}
                    ]
                }
            }
        },
        "limitations": [
            "Real API access is disabled for security",
            "Request quotas apply per session",
            "Sessions expire after 24 hours of inactivity",
            "Mock data is isolated per session"
        ]
    }


@router.post("/cleanup")
async def cleanup_sessions(background_tasks: BackgroundTasks):
    """Trigger cleanup of old sandbox sessions."""
    background_tasks.add_task(sandbox_manager.cleanup_sessions)
    return {"message": "Session cleanup task triggered"}


# Export the router for import
playground_router = router