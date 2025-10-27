"""
Load testing API endpoints.
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

from app.testing.load_testing import (
    LoadTestConfig,
    LoadTestScenario,
    LoadTestRunner,
    PredefinedScenarios,
    get_load_test_runner,
    generate_load_report
)

router = APIRouter()


class LoadTestRequest(BaseModel):
    """Load test request model."""
    name: str = Field(..., description="Test name")
    base_url: str = Field(..., description="Base URL for testing")
    endpoint: str = Field(..., description="API endpoint to test")
    method: str = Field("GET", regex="^(GET|POST|PUT|DELETE)$", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(None, description="Request headers")
    body: Optional[Dict[str, Any]] = Field(None, description="Request body for POST/PUT")
    concurrent_users: int = Field(10, ge=1, le=1000, description="Number of concurrent users")
    duration_seconds: int = Field(60, ge=10, le=3600, description="Test duration in seconds")
    ramp_up_seconds: int = Field(10, ge=0, le=300, description="Ramp-up time in seconds")
    requests_per_second: Optional[int] = Field(None, ge=1, le=1000, description="Target requests per second")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Request timeout in seconds")
    think_time_seconds: float = Field(0.0, ge=0.0, le=60.0, description="Think time between requests")


class ScenarioTestRequest(BaseModel):
    """Scenario-based load test request model."""
    scenario_name: str = Field(..., description="Name of predefined scenario")
    base_url: str = Field(..., description="Base URL for testing")
    concurrent_users: int = Field(10, ge=1, le=1000, description="Number of concurrent users")
    duration_seconds: int = Field(60, ge=10, le=3600, description="Test duration in seconds")
    ramp_up_seconds: int = Field(10, ge=0, le=300, description="Ramp-up time in seconds")


@router.post("/load-test/start", response_model=Dict[str, Any])
async def start_load_test(
    request: LoadTestRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a new load test.

    Args:
        request: Load test configuration
        background_tasks: FastAPI background tasks

    Returns:
        Load test information and test ID
    """
    try:
        # Create load test configuration
        config = LoadTestConfig(
            name=request.name,
            base_url=request.base_url,
            endpoint=request.endpoint,
            method=request.method,
            headers=request.headers,
            body=request.body,
            concurrent_users=request.concurrent_users,
            duration_seconds=request.duration_seconds,
            ramp_up_seconds=request.ramp_up_seconds,
            requests_per_second=request.requests_per_second,
            timeout_seconds=request.timeout_seconds,
            think_time_seconds=request.think_time_seconds
        )

        # Get load test runner
        runner = get_load_test_runner()

        # Start load test in background
        background_tasks.add_task(runner.run_load_test, config)

        return {
            "message": "Load test started successfully",
            "test_name": request.name,
            "test_config": {
                "endpoint": request.endpoint,
                "method": request.method,
                "concurrent_users": request.concurrent_users,
                "duration_seconds": request.duration_seconds,
                "ramp_up_seconds": request.ramp_up_seconds
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to start load test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start load test: {str(e)}")


@router.post("/load-test/scenario", response_model=Dict[str, Any])
async def start_scenario_test(
    request: ScenarioTestRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a predefined scenario load test.

    Args:
        request: Scenario test configuration
        background_tasks: FastAPI background tasks

    Returns:
        Load test information and test ID
    """
    try:
        # Get predefined scenario
        scenario_map = {
            "chat_api": PredefinedScenarios.chat_api_scenario,
            "nlu_api": PredefinedScenarios.nlu_api_scenario,
            "health_check": PredefinedScenarios.health_check_scenario
        }

        if request.scenario_name not in scenario_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scenario: {request.scenario_name}. Available scenarios: {list(scenario_map.keys())}"
            )

        # Create scenario
        scenario = scenario_map[request.scenario_name](request.base_url)

        # Get load test runner
        runner = get_load_test_runner()

        # Start scenario test in background
        background_tasks.add_task(
            runner.run_scenario_test,
            scenario,
            request.concurrent_users,
            request.duration_seconds,
            request.ramp_up_seconds
        )

        return {
            "message": f"Scenario load test '{request.scenario_name}' started successfully",
            "scenario_name": request.scenario_name,
            "test_config": {
                "concurrent_users": request.concurrent_users,
                "duration_seconds": request.duration_seconds,
                "ramp_up_seconds": request.ramp_up_seconds,
                "requests_in_scenario": len(scenario.requests)
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start scenario test: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scenario test: {str(e)}")


@router.get("/load-test/active", response_model=List[Dict[str, Any]])
async def get_active_load_tests():
    """
    Get all currently active load tests.

    Returns:
        List of active load test information
    """
    try:
        runner = get_load_test_runner()
        active_tests = runner.get_active_tests()

        return [
            {
                "test_id": test.test_id,
                "name": test.config.name,
                "status": test.status.value,
                "start_time": test.start_time.isoformat(),
                "endpoint": test.config.endpoint,
                "method": test.config.method,
                "concurrent_users": test.config.concurrent_users,
                "total_requests": test.total_requests,
                "successful_requests": test.successful_requests,
                "failed_requests": test.failed_requests,
                "current_response_time": (
                    statistics.mean(test.response_times[-10:]) if test.response_times else 0
                )
            }
            for test in active_tests
        ]

    except Exception as e:
        logger.error(f"Failed to get active load tests: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active load tests")


@router.get("/load-test/history", response_model=List[Dict[str, Any]])
async def get_load_test_history(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results")
):
    """
    Get load test history.

    Args:
        limit: Maximum number of test results to return

    Returns:
        List of historical load test information
    """
    try:
        runner = get_load_test_runner()
        test_history = runner.get_test_history(limit)

        return [
            {
                "test_id": test.test_id,
                "name": test.config.name,
                "status": test.status.value,
                "start_time": test.start_time.isoformat(),
                "end_time": test.end_time.isoformat() if test.end_time else None,
                "duration_seconds": (
                    (test.end_time - test.start_time).total_seconds()
                    if test.end_time else 0
                ),
                "endpoint": test.config.endpoint,
                "method": test.config.method,
                "concurrent_users": test.config.concurrent_users,
                "total_requests": test.total_requests,
                "successful_requests": test.successful_requests,
                "failed_requests": test.failed_requests,
                "success_rate": (
                    (test.successful_requests / test.total_requests * 100)
                    if test.total_requests > 0 else 0
                ),
                "throughput_rps": test.throughput,
                "average_response_time": test.average_response_time,
                "p95_response_time": test.p95_response_time
            }
            for test in test_history
        ]

    except Exception as e:
        logger.error(f"Failed to get load test history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve load test history")


@router.get("/load-test/{test_id}", response_model=Dict[str, Any])
async def get_load_test_result(test_id: str):
    """
    Get detailed results for a specific load test.

    Args:
        test_id: Load test ID

    Returns:
        Detailed load test results
    """
    try:
        runner = get_load_test_runner()
        result = runner.get_test_result(test_id)

        if not result:
            raise HTTPException(status_code=404, detail="Load test not found")

        return generate_load_report(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get load test result: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve load test result")


@router.post("/load-test/{test_id}/cancel", response_model=Dict[str, Any])
async def cancel_load_test(test_id: str):
    """
    Cancel an active load test.

    Args:
        test_id: Load test ID to cancel

    Returns:
        Cancellation confirmation
    """
    try:
        runner = get_load_test_runner()
        success = runner.cancel_test(test_id)

        if not success:
            raise HTTPException(status_code=404, detail="Active load test not found")

        return {
            "message": "Load test cancelled successfully",
            "test_id": test_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel load test: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel load test")


@router.get("/load-test/scenarios", response_model=Dict[str, Any])
async def get_predefined_scenarios():
    """
    Get available predefined load test scenarios.

    Returns:
        List of available scenarios and their descriptions
    """
    try:
        scenarios = {
            "chat_api": {
                "name": "Chat API Load Test",
                "description": "Tests the chat API endpoints with realistic user interactions",
                "endpoints": [
                    "/api/v1/chat/message (70%)",
                    "/api/v1/chat/history (20%)",
                    "/api/v1/chat/conversations (10%)"
                ]
            },
            "nlu_api": {
                "name": "NLU API Load Test",
                "description": "Tests the natural language understanding endpoints",
                "endpoints": [
                    "/api/v1/nlu/classify-intent (40%)",
                    "/api/v1/nlu/extract-entities (30%)",
                    "/api/v1/nlu/analyze-sentiment (30%)"
                ]
            },
            "health_check": {
                "name": "Health Check Load Test",
                "description": "Tests the health check endpoints for monitoring",
                "endpoints": [
                    "/health (60%)",
                    "/health/detailed (40%)"
                ]
            }
        }

        return {
            "available_scenarios": scenarios,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get predefined scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve scenarios")


@router.get("/load-test/dashboard", response_model=Dict[str, Any])
async def get_load_test_dashboard():
    """
    Get load testing dashboard data.

    Returns:
        Dashboard summary of load testing activity
    """
    try:
        runner = get_load_test_runner()
        active_tests = runner.get_active_tests()
        recent_tests = runner.get_test_history(10)

        # Calculate summary statistics
        total_requests = sum(test.total_requests for test in recent_tests)
        total_successful = sum(test.successful_requests for test in recent_tests)
        avg_success_rate = (
            (total_successful / total_requests * 100)
            if total_requests > 0 else 0
        )

        # Get average response times
        avg_response_times = [
            test.average_response_time for test in recent_tests
            if test.average_response_time > 0
        ]
        avg_response_time = (
            sum(avg_response_times) / len(avg_response_times)
            if avg_response_times else 0
        )

        # Get throughput data
        throughputs = [
            test.throughput for test in recent_tests
            if test.throughput > 0
        ]
        avg_throughput = (
            sum(throughputs) / len(throughputs)
            if throughputs else 0
        )

        return {
            "summary": {
                "active_tests": len(active_tests),
                "recent_tests": len(recent_tests),
                "total_requests_last_10": total_requests,
                "avg_success_rate_percent": round(avg_success_rate, 2),
                "avg_response_time_seconds": round(avg_response_time, 3),
                "avg_throughput_rps": round(avg_throughput, 2)
            },
            "active_tests": [
                {
                    "test_id": test.test_id,
                    "name": test.config.name,
                    "start_time": test.start_time.isoformat(),
                    "concurrent_users": test.config.concurrent_users,
                    "requests_so_far": test.total_requests,
                    "success_rate": (
                        (test.successful_requests / test.total_requests * 100)
                        if test.total_requests > 0 else 0
                    )
                }
                for test in active_tests
            ],
            "recent_test_summary": [
                {
                    "test_id": test.test_id,
                    "name": test.config.name,
                    "status": test.status.value,
                    "end_time": test.end_time.isoformat() if test.end_time else None,
                    "success_rate": (
                        (test.successful_requests / test.total_requests * 100)
                        if test.total_requests > 0 else 0
                    ),
                    "throughput_rps": test.throughput,
                    "avg_response_time": test.average_response_time
                }
                for test in recent_tests[:5]
            ],
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get load test dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")


# Import statistics for calculation
import statistics