"""
API load testing framework.
"""

import asyncio
import time
import json
import statistics
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
from concurrent.futures import ThreadPoolExecutor
import uuid
from loguru import logger

from app.core.config import settings


class LoadTestStatus(Enum):
    """Load test status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LoadTestConfig:
    """Load test configuration."""
    name: str
    base_url: str
    endpoint: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    concurrent_users: int = 10
    duration_seconds: int = 60
    ramp_up_seconds: int = 10
    requests_per_second: Optional[int] = None
    timeout_seconds: int = 30
    think_time_seconds: float = 0.0
    follow_redirects: bool = True
    verify_ssl: bool = True


@dataclass
class LoadTestResult:
    """Individual load test result."""
    test_id: str
    config: LoadTestConfig
    status: LoadTestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = None
    status_codes: Dict[int, int] = None
    errors: List[str] = None
    throughput: float = 0.0
    average_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.status_codes is None:
            self.status_codes = {}
        if self.errors is None:
            self.errors = []


class LoadTestScenario:
    """Load test scenario with multiple requests."""

    def __init__(self, name: str):
        self.name = name
        self.requests: List[LoadTestConfig] = []
        self.weights: List[float] = []  # Weight for each request type

    def add_request(self, config: LoadTestConfig, weight: float = 1.0):
        """Add a request to the scenario."""
        self.requests.append(config)
        self.weights.append(weight)

    def get_random_request(self) -> LoadTestConfig:
        """Get a random request based on weights."""
        if not self.requests:
            raise ValueError("No requests defined in scenario")

        total_weight = sum(self.weights)
        if total_weight == 0:
            return random.choice(self.requests)

        rand_val = random.uniform(0, total_weight)
        current_weight = 0

        for request, weight in zip(self.requests, self.weights):
            current_weight += weight
            if rand_val <= current_weight:
                return request

        return self.requests[-1]


class LoadTestRunner:
    """Load test execution engine."""

    def __init__(self):
        self.active_tests: Dict[str, LoadTestResult] = {}
        self.test_history: List[LoadTestResult] = []

    async def run_load_test(self, config: LoadTestConfig) -> LoadTestResult:
        """Run a single load test."""
        test_id = str(uuid.uuid4())
        result = LoadTestResult(
            test_id=test_id,
            config=config,
            status=LoadTestStatus.RUNNING,
            start_time=datetime.utcnow()
        )

        self.active_tests[test_id] = result

        try:
            logger.info(f"Starting load test: {config.name} (ID: {test_id})")

            # Prepare HTTP client
            async with httpx.AsyncClient(
                timeout=config.timeout_seconds,
                follow_redirects=config.follow_redirects,
                verify=config.verify_ssl
            ) as client:
                # Calculate user start times for ramp-up
                user_start_times = self._calculate_user_start_times(
                    config.concurrent_users,
                    config.ramp_up_seconds
                )

                # Create user tasks
                user_tasks = []
                for user_id, start_delay in enumerate(user_start_times):
                    task = self._run_user_session(
                        client, config, user_id, start_delay, result
                    )
                    user_tasks.append(task)

                # Wait for all users to complete
                await asyncio.gather(*user_tasks, return_exceptions=True)

            # Calculate final statistics
            self._calculate_statistics(result)

            result.status = LoadTestStatus.COMPLETED
            result.end_time = datetime.utcnow()

            logger.info(f"Load test completed: {config.name} (ID: {test_id})")

        except Exception as e:
            logger.error(f"Load test failed: {config.name} - {str(e)}")
            result.status = LoadTestStatus.FAILED
            result.end_time = datetime.utcnow()
            result.errors.append(str(e))

        finally:
            # Move from active to history
            if test_id in self.active_tests:
                del self.active_tests[test_id]
            self.test_history.append(result)

        return result

    async def run_scenario_test(
        self,
        scenario: LoadTestScenario,
        concurrent_users: int = 10,
        duration_seconds: int = 60,
        ramp_up_seconds: int = 10
    ) -> LoadTestResult:
        """Run a load test with a scenario containing multiple request types."""
        test_id = str(uuid.uuid4())
        config = LoadTestConfig(
            name=f"Scenario: {scenario.name}",
            base_url="",
            endpoint="",
            concurrent_users=concurrent_users,
            duration_seconds=duration_seconds,
            ramp_up_seconds=ramp_up_seconds
        )

        result = LoadTestResult(
            test_id=test_id,
            config=config,
            status=LoadTestStatus.RUNNING,
            start_time=datetime.utcnow()
        )

        self.active_tests[test_id] = result

        try:
            logger.info(f"Starting scenario test: {scenario.name} (ID: {test_id})")

            async with httpx.AsyncClient(timeout=30) as client:
                # Calculate user start times
                user_start_times = self._calculate_user_start_times(
                    concurrent_users,
                    ramp_up_seconds
                )

                # Create user tasks
                user_tasks = []
                for user_id, start_delay in enumerate(user_start_times):
                    task = self._run_scenario_user_session(
                        client, scenario, user_id, start_delay, duration_seconds, result
                    )
                    user_tasks.append(task)

                # Wait for all users to complete
                await asyncio.gather(*user_tasks, return_exceptions=True)

            # Calculate final statistics
            self._calculate_statistics(result)

            result.status = LoadTestStatus.COMPLETED
            result.end_time = datetime.utcnow()

            logger.info(f"Scenario test completed: {scenario.name} (ID: {test_id})")

        except Exception as e:
            logger.error(f"Scenario test failed: {scenario.name} - {str(e)}")
            result.status = LoadTestStatus.FAILED
            result.end_time = datetime.utcnow()
            result.errors.append(str(e))

        finally:
            if test_id in self.active_tests:
                del self.active_tests[test_id]
            self.test_history.append(result)

        return result

    def _calculate_user_start_times(
        self,
        concurrent_users: int,
        ramp_up_seconds: int
    ) -> List[float]:
        """Calculate start times for users during ramp-up."""
        if ramp_up_seconds <= 0:
            return [0.0] * concurrent_users

        delay_between_users = ramp_up_seconds / concurrent_users
        return [i * delay_between_users for i in range(concurrent_users)]

    async def _run_user_session(
        self,
        client: httpx.AsyncClient,
        config: LoadTestConfig,
        user_id: int,
        start_delay: float,
        result: LoadTestResult
    ):
        """Run a single user session."""
        # Wait for start time
        if start_delay > 0:
            await asyncio.sleep(start_delay)

        session_start = time.time()
        session_end = session_start + config.duration_seconds

        # Prepare request data
        url = f"{config.base_url}{config.endpoint}"
        headers = config.headers or {}

        while time.time() < session_end:
            request_start = time.time()

            try:
                # Make request
                if config.method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif config.method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=config.body)
                elif config.method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=config.body)
                elif config.method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {config.method}")

                # Record metrics
                response_time = time.time() - request_start
                result.response_times.append(response_time)
                result.total_requests += 1

                # Track status codes
                status_code = response.status_code
                result.status_codes[status_code] = result.status_codes.get(status_code, 0) + 1

                # Track successful requests
                if 200 <= status_code < 400:
                    result.successful_requests += 1
                else:
                    result.failed_requests += 1
                    result.errors.append(f"HTTP {status_code}: {response.text[:100]}")

            except Exception as e:
                # Track failed requests
                response_time = time.time() - request_start
                result.response_times.append(response_time)
                result.total_requests += 1
                result.failed_requests += 1
                result.errors.append(str(e))

            # Think time between requests
            if config.think_time_seconds > 0:
                await asyncio.sleep(config.think_time_seconds)

            # Rate limiting if specified
            if config.requests_per_second:
                target_time = 1.0 / config.requests_per_second
                elapsed = time.time() - request_start
                if elapsed < target_time:
                    await asyncio.sleep(target_time - elapsed)

    async def _run_scenario_user_session(
        self,
        client: httpx.AsyncClient,
        scenario: LoadTestScenario,
        user_id: int,
        start_delay: float,
        duration_seconds: int,
        result: LoadTestResult
    ):
        """Run a user session with scenario-based requests."""
        # Wait for start time
        if start_delay > 0:
            await asyncio.sleep(start_delay)

        session_start = time.time()
        session_end = session_start + duration_seconds

        while time.time() < session_end:
            # Get random request from scenario
            request_config = scenario.get_random_request()

            # Convert scenario request to full config
            test_config = LoadTestConfig(
                name=request_config.name,
                base_url=request_config.base_url,
                endpoint=request_config.endpoint,
                method=request_config.method,
                headers=request_config.headers,
                body=request_config.body,
                timeout_seconds=request_config.timeout_seconds,
                think_time_seconds=request_config.think_time_seconds,
                follow_redirects=request_config.follow_redirects,
                verify_ssl=request_config.verify_ssl
            )

            # Run single request
            await self._run_single_request(client, test_config, result)

            # Think time
            if request_config.think_time_seconds > 0:
                await asyncio.sleep(request_config.think_time_seconds)

    async def _run_single_request(
        self,
        client: httpx.AsyncClient,
        config: LoadTestConfig,
        result: LoadTestResult
    ):
        """Run a single HTTP request."""
        request_start = time.time()

        try:
            url = f"{config.base_url}{config.endpoint}"
            headers = config.headers or {}

            if config.method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif config.method.upper() == "POST":
                response = await client.post(url, headers=headers, json=config.body)
            elif config.method.upper() == "PUT":
                response = await client.put(url, headers=headers, json=config.body)
            elif config.method.upper() == "DELETE":
                response = await client.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {config.method}")

            # Record metrics
            response_time = time.time() - request_start
            result.response_times.append(response_time)
            result.total_requests += 1

            # Track status codes
            status_code = response.status_code
            result.status_codes[status_code] = result.status_codes.get(status_code, 0) + 1

            # Track successful requests
            if 200 <= status_code < 400:
                result.successful_requests += 1
            else:
                result.failed_requests += 1
                result.errors.append(f"HTTP {status_code}: {response.text[:100]}")

        except Exception as e:
            # Track failed requests
            response_time = time.time() - request_start
            result.response_times.append(response_time)
            result.total_requests += 1
            result.failed_requests += 1
            result.errors.append(str(e))

    def _calculate_statistics(self, result: LoadTestResult):
        """Calculate final statistics for the test result."""
        if not result.response_times:
            return

        # Response time statistics
        result.average_response_time = statistics.mean(result.response_times)
        result.min_response_time = min(result.response_times)
        result.max_response_time = max(result.response_times)
        result.p95_response_time = self._percentile(result.response_times, 95)
        result.p99_response_time = self._percentile(result.response_times, 99)

        # Throughput (requests per second)
        if result.end_time:
            duration = (result.end_time - result.start_time).total_seconds()
            if duration > 0:
                result.throughput = result.total_requests / duration

    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_active_tests(self) -> List[LoadTestResult]:
        """Get all currently active tests."""
        return list(self.active_tests.values())

    def get_test_history(self, limit: int = 50) -> List[LoadTestResult]:
        """Get test history."""
        return self.test_history[-limit:]

    def get_test_result(self, test_id: str) -> Optional[LoadTestResult]:
        """Get a specific test result."""
        if test_id in self.active_tests:
            return self.active_tests[test_id]

        for result in self.test_history:
            if result.test_id == test_id:
                return result

        return None

    def cancel_test(self, test_id: str) -> bool:
        """Cancel an active test."""
        if test_id in self.active_tests:
            result = self.active_tests[test_id]
            result.status = LoadTestStatus.CANCELLED
            result.end_time = datetime.utcnow()
            del self.active_tests[test_id]
            self.test_history.append(result)
            return True
        return False


class PredefinedScenarios:
    """Predefined load test scenarios."""

    @staticmethod
    def chat_api_scenario(base_url: str) -> LoadTestScenario:
        """Chat API load test scenario."""
        scenario = LoadTestScenario("Chat API Load Test")

        # Send message (70% weight)
        scenario.add_request(LoadTestConfig(
            name="Send Message",
            base_url=base_url,
            endpoint="/api/v1/chat/message",
            method="POST",
            body={
                "message": "Hello, I need help with my order",
                "conversation_id": None
            },
            think_time_seconds=1.0
        ), weight=7.0)

        # Get conversation history (20% weight)
        scenario.add_request(LoadTestConfig(
            name="Get History",
            base_url=base_url,
            endpoint="/api/v1/chat/history/test_conv_001",
            method="GET",
            think_time_seconds=0.5
        ), weight=2.0)

        # Get conversations list (10% weight)
        scenario.add_request(LoadTestConfig(
            name="Get Conversations",
            base_url=base_url,
            endpoint="/api/v1/chat/conversations",
            method="GET",
            think_time_seconds=0.5
        ), weight=1.0)

        return scenario

    @staticmethod
    def nlu_api_scenario(base_url: str) -> LoadTestScenario:
        """NLU API load test scenario."""
        scenario = LoadTestScenario("NLU API Load Test")

        # Intent classification (40% weight)
        scenario.add_request(LoadTestConfig(
            name="Classify Intent",
            base_url=base_url,
            endpoint="/api/v1/nlu/classify-intent",
            method="POST",
            body={"text": "I want to track my order"},
            think_time_seconds=0.5
        ), weight=4.0)

        # Entity extraction (30% weight)
        scenario.add_request(LoadTestConfig(
            name="Extract Entities",
            base_url=base_url,
            endpoint="/api/v1/nlu/extract-entities",
            method="POST",
            body={"text": "I ordered a iPhone 15 Pro last week"},
            think_time_seconds=0.5
        ), weight=3.0)

        # Sentiment analysis (30% weight)
        scenario.add_request(LoadTestConfig(
            name="Analyze Sentiment",
            base_url=base_url,
            endpoint="/api/v1/nlu/analyze-sentiment",
            method="POST",
            body={"text": "I'm very happy with the service!"},
            think_time_seconds=0.5
        ), weight=3.0)

        return scenario

    @staticmethod
    def health_check_scenario(base_url: str) -> LoadTestScenario:
        """Health check load test scenario."""
        scenario = LoadTestScenario("Health Check Load Test")

        # Basic health check (60% weight)
        scenario.add_request(LoadTestConfig(
            name="Health Check",
            base_url=base_url,
            endpoint="/health",
            method="GET",
            think_time_seconds=0.1
        ), weight=6.0)

        # Detailed health check (40% weight)
        scenario.add_request(LoadTestConfig(
            name="Detailed Health Check",
            base_url=base_url,
            endpoint="/health/detailed",
            method="GET",
            think_time_seconds=0.2
        ), weight=4.0)

        return scenario


# Global load test runner instance
load_test_runner = LoadTestRunner()


def get_load_test_runner() -> LoadTestRunner:
    """Get the global load test runner instance."""
    return load_test_runner


def generate_load_report(result: LoadTestResult) -> Dict[str, Any]:
    """Generate a comprehensive load test report."""
    report = {
        "test_info": {
            "test_id": result.test_id,
            "name": result.config.name,
            "status": result.status.value,
            "start_time": result.start_time.isoformat(),
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "duration_seconds": (
                (result.end_time - result.start_time).total_seconds()
                if result.end_time else 0
            )
        },
        "test_config": {
            "endpoint": result.config.endpoint,
            "method": result.config.method,
            "concurrent_users": result.config.concurrent_users,
            "duration_seconds": result.config.duration_seconds,
            "ramp_up_seconds": result.config.ramp_up_seconds,
            "requests_per_second": result.config.requests_per_second
        },
        "results": {
            "total_requests": result.total_requests,
            "successful_requests": result.successful_requests,
            "failed_requests": result.failed_requests,
            "success_rate": (
                (result.successful_requests / result.total_requests * 100)
                if result.total_requests > 0 else 0
            ),
            "throughput_rps": result.throughput
        },
        "response_times": {
            "average_seconds": result.average_response_time,
            "min_seconds": result.min_response_time,
            "max_seconds": result.max_response_time,
            "p95_seconds": result.p95_response_time,
            "p99_seconds": result.p99_response_time
        },
        "status_codes": result.status_codes,
        "errors": result.errors[:10],  # Limit to first 10 errors
        "total_errors": len(result.errors)
    }

    return report