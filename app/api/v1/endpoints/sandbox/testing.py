"""
Sandbox testing utilities and endpoints.
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger

router = APIRouter(prefix="/testing", tags=["Sandbox Testing"])


class TestCase(BaseModel):
    """Test case model."""
    name: str
    description: str
    method: str
    endpoint: str
    headers: Dict[str, str] = {}
    params: Dict[str, Any] = {}
    body: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    expected_response: Optional[Dict[str, Any]] = None
    timeout_ms: int = 5000


class TestSuite(BaseModel):
    """Test suite model."""
    name: str
    description: str
    test_cases: List[TestCase]
    setup_data: Dict[str, Any] = {}
    teardown_data: Dict[str, Any] = {}


class TestResult(BaseModel):
    """Test result model."""
    test_name: str
    status: str  # "passed", "failed", "skipped", "error"
    duration_ms: float
    status_code: Optional[int] = None
    response_body: Optional[Any] = None
    error_message: Optional[str] = None
    timestamp: datetime


class TestRun(BaseModel):
    """Test run model."""
    run_id: str
    suite_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: List[TestResult] = []
    summary: Dict[str, int] = {}  # passed, failed, skipped, error


class SandboxTestRunner:
    """Sandbox test runner for API testing."""

    def __init__(self):
        """Initialize test runner."""
        self.test_suites: Dict[str, TestSuite] = {}
        self.test_runs: Dict[str, TestRun] = {}
        self.mock_responses = {
            "GET:/api/v1/products/search": {
                "status_code": 200,
                "body": {
                    "products": [
                        {"id": "test_1", "title": "Test Product 1", "price": 29.99},
                        {"id": "test_2", "title": "Test Product 2", "price": 49.99}
                    ],
                    "total": 2
                }
            },
            "POST:/api/v1/chat/message": {
                "status_code": 200,
                "body": {
                    "message": "Hello! This is a test response from the sandbox.",
                    "conversation_id": "test_conv_123"
                }
            },
            "GET:/api/v1/health": {
                "status_code": 200,
                "body": {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
            }
        }

    def add_test_suite(self, suite: TestSuite) -> str:
        """Add a test suite."""
        self.test_suites[suite.name] = suite
        logger.info(f"Added test suite: {suite.name}")
        return suite.name

    def run_test_case(self, test_case: TestCase, session_data: Dict[str, Any] = None) -> TestResult:
        """Run a single test case."""
        start_time = time.time()
        test_key = f"{test_case.method}:{test_case.endpoint}"

        try:
            # Get mock response
            mock_response = self.mock_responses.get(test_key)
            if not mock_response:
                # Default mock response
                mock_response = {
                    "status_code": 200,
                    "body": {"message": f"Mock response for {test_key}"}
                }

            # Check status code
            if mock_response["status_code"] == test_case.expected_status:
                status = "passed"
            else:
                status = "failed"

            # Check response body if expected
            if test_case.expected_response and mock_response["body"]:
                # Simple comparison (in real implementation, use deep comparison)
                if str(mock_response["body"]) == str(test_case.expected_response):
                    pass  # status remains "passed" or "failed" based on status code
                else:
                    status = "failed"

            duration_ms = (time.time() - start_time) * 1000

            return TestResult(
                test_name=test_case.name,
                status=status,
                duration_ms=duration_ms,
                status_code=mock_response["status_code"],
                response_body=mock_response["body"],
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Test case {test_case.name} failed with error: {e}")

            return TestResult(
                test_name=test_case.name,
                status="error",
                duration_ms=duration_ms,
                error_message=str(e),
                timestamp=datetime.utcnow()
            )

    def run_test_suite(self, suite_name: str, session_data: Dict[str, Any] = None) -> TestRun:
        """Run a complete test suite."""
        suite = self.test_suites.get(suite_name)
        if not suite:
            raise HTTPException(status_code=404, detail=f"Test suite '{suite_name}' not found")

        run_id = str(uuid.uuid4())
        test_run = TestRun(
            run_id=run_id,
            suite_name=suite_name,
            started_at=datetime.utcnow(),
            results=[]
        )

        logger.info(f"Starting test run: {run_id} for suite: {suite_name}")

        # Run all test cases
        for test_case in suite.test_cases:
            result = self.run_test_case(test_case, session_data)
            test_run.results.append(result)

        # Calculate summary
        summary = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        for result in test_run.results:
            summary[result.status] = summary.get(result.status, 0) + 1

        test_run.summary = summary
        test_run.completed_at = datetime.utcnow()

        # Store test run
        self.test_runs[run_id] = test_run

        logger.info(f"Test run completed: {run_id} - {summary}")

        return test_run

    def get_test_run(self, run_id: str) -> Optional[TestRun]:
        """Get test run results."""
        return self.test_runs.get(run_id)

    def get_test_suites(self) -> List[Dict[str, Any]]:
        """Get all test suites."""
        return [
            {
                "name": suite.name,
                "description": suite.description,
                "test_cases_count": len(suite.test_cases)
            }
            for suite in self.test_suites.values()
        ]


# Global test runner
test_runner = SandboxTestRunner()

# Initialize with default test suite
default_suite = TestSuite(
    name="Basic API Tests",
    description="Basic API functionality tests",
    test_cases=[
        TestCase(
            name="Health Check",
            description="Test health endpoint",
            method="GET",
            endpoint="/api/v1/health",
            expected_status=200
        ),
        TestCase(
            name="Product Search",
            description="Test product search endpoint",
            method="GET",
            endpoint="/api/v1/products/search",
            params={"query": "test", "limit": 10},
            expected_status=200
        ),
        TestCase(
            name="Chat Message",
            description="Test chat message endpoint",
            method="POST",
            endpoint="/api/v1/chat/message",
            body={"message": "Hello, this is a test", "conversation_id": "test_conv"},
            expected_status=200
        )
    ]
)
test_runner.add_test_suite(default_suite)


@router.post("/suites", response_model=Dict[str, str])
async def create_test_suite(suite: TestSuite):
    """Create a new test suite."""
    try:
        suite_name = test_runner.add_test_suite(suite)
        return {
            "message": "Test suite created successfully",
            "suite_name": suite_name
        }
    except Exception as e:
        logger.error(f"Failed to create test suite: {e}")
        raise HTTPException(status_code=500, detail="Failed to create test suite")


@router.get("/suites", response_model=List[Dict[str, Any]])
async def get_test_suites():
    """Get all test suites."""
    try:
        return test_runner.get_test_suites()
    except Exception as e:
        logger.error(f"Failed to get test suites: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test suites")


@router.post("/run/{suite_name}", response_model=Dict[str, Any])
async def run_test_suite(suite_name: str, session_data: Optional[Dict[str, Any]] = None):
    """Run a test suite."""
    try:
        test_run = test_runner.run_test_suite(suite_name, session_data)
        return {
            "run_id": test_run.run_id,
            "suite_name": test_run.suite_name,
            "started_at": test_run.started_at.isoformat(),
            "summary": test_run.summary,
            "results_count": len(test_run.results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run test suite {suite_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to run test suite")


@router.get("/run/{run_id}", response_model=Dict[str, Any])
async def get_test_run_results(run_id: str):
    """Get test run results."""
    try:
        test_run = test_runner.get_test_run(run_id)
        if not test_run:
            raise HTTPException(status_code=404, detail="Test run not found")

        return {
            "run_id": test_run.run_id,
            "suite_name": test_run.suite_name,
            "started_at": test_run.started_at.isoformat(),
            "completed_at": test_run.completed_at.isoformat() if test_run.completed_at else None,
            "summary": test_run.summary,
            "results": [
                {
                    "test_name": result.test_name,
                    "status": result.status,
                    "duration_ms": result.duration_ms,
                    "status_code": result.status_code,
                    "error_message": result.error_message,
                    "timestamp": result.timestamp.isoformat()
                }
                for result in test_run.results
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test run results {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test run results")


@router.get("/runs", response_model=List[Dict[str, Any]])
async def get_test_runs(limit: int = 50):
    """Get recent test runs."""
    try:
        runs = list(test_runner.test_runs.values())
        runs.sort(key=lambda x: x.started_at, reverse=True)
        runs = runs[:limit]

        return [
            {
                "run_id": run.run_id,
                "suite_name": run.suite_name,
                "started_at": run.started_at.isoformat(),
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "summary": run.summary,
                "results_count": len(run.results)
            }
            for run in runs
        ]
    except Exception as e:
        logger.error(f"Failed to get test runs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test runs")


@router.post("/validate/{suite_name}")
async def validate_test_suite(suite_name: str):
    """Validate a test suite without running it."""
    try:
        suite = test_runner.test_suites.get(suite_name)
        if not suite:
            raise HTTPException(status_code=404, detail=f"Test suite '{suite_name}' not found")

        validation_errors = []
        for i, test_case in enumerate(suite.test_cases):
            if not test_case.name.strip():
                validation_errors.append(f"Test case {i+1}: Name is required")
            if not test_case.method.strip():
                validation_errors.append(f"Test case {i+1}: Method is required")
            if not test_case.endpoint.strip():
                validation_errors.append(f"Test case {i+1}: Endpoint is required")

        return {
            "suite_name": suite_name,
            "is_valid": len(validation_errors) == 0,
            "test_cases_count": len(suite.test_cases),
            "validation_errors": validation_errors
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate test suite {suite_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate test suite")


@router.get("/stats")
async def get_testing_stats():
    """Get testing statistics."""
    try:
        total_suites = len(test_runner.test_suites)
        total_runs = len(test_runner.test_runs)
        total_tests = sum(len(run.results) for run in test_runner.test_runs.values())

        # Calculate success rate
        total_passed = sum(run.summary.get("passed", 0) for run in test_runner.test_runs.values())
        total_tests_run = sum(sum(run.summary.values()) for run in test_runner.test_runs.values())
        success_rate = (total_passed / total_tests_run * 100) if total_tests_run > 0 else 0

        return {
            "total_suites": total_suites,
            "total_runs": total_runs,
            "total_tests": total_tests,
            "success_rate_percent": round(success_rate, 2),
            "available_mock_endpoints": len(test_runner.mock_responses)
        }
    except Exception as e:
        logger.error(f"Failed to get testing stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get testing stats")


# Export the router for import
testing_router = router