"""
API integration testing framework for Shop Assistant AI.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import pytest
from loguru import logger

from app.core.config import settings


class TestResult(Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class APITestCase:
    """API test case definition."""
    name: str
    method: str
    endpoint: str
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
    expected_status: int = 200
    expected_response: Optional[Dict[str, Any]] = None
    response_validator: Optional[str] = None
    timeout: float = 30.0
    tags: List[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class APITestResult:
    """API test result."""
    test_case: APITestCase
    status: TestResult
    execution_time: float
    response_status: int
    response_body: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None


@dataclass
class TestSuiteMetrics:
    """Test suite execution metrics."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_execution_time: float
    average_response_time: float
    slowest_test: Tuple[str, float]
    fastest_test: Tuple[str, float]
    success_rate: float


class APIIntegrationTester:
    """API integration testing framework."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or f"http://{settings.API_HOST}:{settings.API_PORT}"
        self.client = httpx.AsyncClient(timeout=60.0)
        self.test_results: List[APITestResult] = []
        self.session_token: Optional[str] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def _load_test_cases(self) -> List[APITestCase]:
        """Load comprehensive test cases."""
        test_cases = [
            # Health Check Tests
            APITestCase(
                name="Health Check",
                method="GET",
                endpoint="/health",
                expected_status=200,
                tags=["health", "basic"]
            ),

            # Chat API Tests
            APITestCase(
                name="Send Message - Basic",
                method="POST",
                endpoint="/api/v1/chat/message",
                body={
                    "message": "Hello, I need help with my order",
                    "conversation_id": None
                },
                expected_status=200,
                response_validator="message_response",
                tags=["chat", "basic"]
            ),

            APITestCase(
                name="Send Message - With Context",
                method="POST",
                endpoint="/api/v1/chat/message",
                body={
                    "message": "What's the status of order #12345?",
                    "conversation_id": "test_conv_001"
                },
                expected_status=200,
                response_validator="message_response",
                tags=["chat", "context"]
            ),

            APITestCase(
                name="Send Message - Empty Message",
                method="POST",
                endpoint="/api/v1/chat/message",
                body={
                    "message": "",
                    "conversation_id": None
                },
                expected_status=422,
                tags=["chat", "validation"]
            ),

            # NLU API Tests
            APITestCase(
                name="NLU Intent Classification",
                method="POST",
                endpoint="/api/v1/nlu/classify-intent",
                body={
                    "text": "I want to track my order"
                },
                expected_status=200,
                response_validator="intent_response",
                tags=["nlu", "intent"]
            ),

            APITestCase(
                name="NLU Entity Extraction",
                method="POST",
                endpoint="/api/v1/nlu/extract-entities",
                body={
                    "text": "I ordered a iPhone 15 Pro last week"
                },
                expected_status=200,
                response_validator="entity_response",
                tags=["nlu", "entities"]
            ),

            APITestCase(
                name="NLU Sentiment Analysis",
                method="POST",
                endpoint="/api/v1/nlu/analyze-sentiment",
                body={
                    "text": "I'm very happy with the service!"
                },
                expected_status=200,
                response_validator="sentiment_response",
                tags=["nlu", "sentiment"]
            ),

            # Conversation Management Tests
            APITestCase(
                name="Get Conversation History",
                method="GET",
                endpoint="/api/v1/chat/history/test_conv_001",
                expected_status=200,
                response_validator="conversation_history",
                tags=["conversation", "history"]
            ),

            APITestCase(
                name="Get User Conversations",
                method="GET",
                endpoint="/api/v1/chat/conversations",
                params={"limit": 10, "offset": 0},
                expected_status=200,
                response_validator="conversation_list",
                tags=["conversation", "list"]
            ),

            APITestCase(
                name="Create New Conversation",
                method="POST",
                endpoint="/api/v1/chat/conversations",
                expected_status=200,
                response_validator="conversation_response",
                tags=["conversation", "create"]
            ),

            # Quality Assessment Tests
            APITestCase(
                name="Assess Conversation Quality",
                method="POST",
                endpoint="/api/v1/chat/dialogue/quality",
                body={
                    "conversation_id": "test_conv_001"
                },
                expected_status=200,
                response_validator="quality_assessment",
                tags=["quality", "assessment"]
            ),

            # Dialogue Management Tests
            APITestCase(
                name="Get Active Dialogue Contexts",
                method="GET",
                endpoint="/api/v1/chat/dialogue/active-contexts",
                expected_status=200,
                response_validator="active_contexts",
                tags=["dialogue", "contexts"]
            ),

            APITestCase(
                name="Run Dialogue Tests",
                method="POST",
                endpoint="/api/v1/chat/dialogue/test",
                body={
                    "test_type": "basic_suite",
                    "parallel": False
                },
                expected_status=200,
                response_validator="test_results",
                tags=["dialogue", "testing"]
            ),

            # Search Tests - FEATURE DISABLED
            # APITestCase(
            #     name="Search Similar Conversations",
            #     method="POST",
            #     endpoint="/api/v1/chat/dialogue/search-similar",
            #     body={
            #         "query": "order tracking issue",
            #         "limit": 5
            #     },
            #     expected_status=200,
            #     response_validator="search_results",
            #     tags=["search", "similarity"]
            # ),

            # Insights Tests
            APITestCase(
                name="Get Conversation Insights",
                method="GET",
                endpoint="/api/v1/chat/conversations/test_conv_001/insights",
                expected_status=200,
                response_validator="conversation_insights",
                tags=["insights", "analytics"]
            ),

            # Summarization Tests
            APITestCase(
                name="Summarize Conversation",
                method="POST",
                endpoint="/api/v1/chat/dialogue/summarize",
                body={
                    "conversation_id": "test_conv_001"
                },
                expected_status=200,
                response_validator="conversation_summary",
                tags=["dialogue", "summarization"]
            ),

            # Error Handling Tests
            APITestCase(
                name="Invalid Endpoint",
                method="GET",
                endpoint="/api/v1/invalid/endpoint",
                expected_status=404,
                tags=["error", "404"]
            ),

            APITestCase(
                name="Invalid HTTP Method",
                method="PATCH",
                endpoint="/api/v1/chat/message",
                expected_status=405,
                tags=["error", "405"]
            ),

            APITestCase(
                name="Malformed JSON Request",
                method="POST",
                endpoint="/api/v1/chat/message",
                body="invalid json",
                headers={"Content-Type": "application/json"},
                expected_status=422,
                tags=["error", "validation"]
            ),

            # Performance Tests
            APITestCase(
                name="Concurrent Message Load",
                method="POST",
                endpoint="/api/v1/chat/message",
                body={
                    "message": "This is a load test message",
                    "conversation_id": "load_test_conv"
                },
                expected_status=200,
                timeout=10.0,
                tags=["performance", "load"]
            ),
        ]

        return test_cases

    async def _execute_test_case(self, test_case: APITestCase) -> APITestResult:
        """Execute a single API test case."""
        start_time = time.time()

        try:
            # Prepare request
            url = f"{self.base_url}{test_case.endpoint}"
            headers = test_case.headers or {}

            # Add auth token if available
            if self.session_token:
                headers["Authorization"] = f"Bearer {self.session_token}"

            # Execute request
            response = await self.client.request(
                method=test_case.method,
                url=url,
                headers=headers,
                params=test_case.params,
                json=test_case.body,
                timeout=test_case.timeout
            )

            execution_time = time.time() - start_time

            # Parse response
            try:
                response_body = response.json()
            except:
                response_body = {"raw_response": response.text}

            # Validate response
            status = TestResult.PASSED
            error_message = None

            if response.status_code != test_case.expected_status:
                status = TestResult.FAILED
                error_message = f"Expected status {test_case.expected_status}, got {response.status_code}"

            # Custom response validation
            if status == TestResult.PASSED and test_case.response_validator:
                validation_result = await self._validate_response(
                    test_case.response_validator, response_body
                )
                if not validation_result:
                    status = TestResult.FAILED
                    error_message = f"Response validation failed: {test_case.response_validator}"

            # Performance metrics
            performance_metrics = {
                "response_time": execution_time,
                "status_code": response.status_code,
                "response_size": len(response.content)
            }

            return APITestResult(
                test_case=test_case,
                status=status,
                execution_time=execution_time,
                response_status=response.status_code,
                response_body=response_body,
                error_message=error_message,
                performance_metrics=performance_metrics
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            return APITestResult(
                test_case=test_case,
                status=TestResult.FAILED,
                execution_time=execution_time,
                response_status=0,
                error_message=f"Test timed out after {test_case.timeout}s"
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return APITestResult(
                test_case=test_case,
                status=TestResult.ERROR,
                execution_time=execution_time,
                response_status=0,
                error_message=str(e)
            )

    async def _validate_response(self, validator: str, response: Dict[str, Any]) -> bool:
        """Validate API response structure."""
        validators = {
            "message_response": lambda r: all(key in r for key in ["id", "message", "sender", "timestamp"]),
            "intent_response": lambda r: "intent" in r and "confidence" in r,
            "entity_response": lambda r: "entities" in r and isinstance(r["entities"], list),
            "sentiment_response": lambda r: "sentiment" in r and "confidence" in r,
            "conversation_history": lambda r: "messages" in r and "total_count" in r,
            "conversation_list": lambda r: isinstance(r, list),
            "conversation_response": lambda r: "id" in r and "title" in r,
            "quality_assessment": lambda r: "overall_score" in r and "dimension_scores" in r,
            "active_contexts": lambda r: "active_conversations" in r and "contexts" in r,
            "test_results": lambda r: "test_results" in r and "suite_metrics" in r,
            "search_results": lambda r: "similar_conversations" in r,
            "conversation_insights": lambda r: isinstance(r, dict),
            "conversation_summary": lambda r: "summary" in r
        }

        validator_func = validators.get(validator)
        if validator_func:
            return validator_func(response)

        return True  # No validation specified

    async def run_test_suite(
        self,
        test_tags: Optional[List[str]] = None,
        parallel: bool = True,
        max_concurrent: int = 5
    ) -> Tuple[List[APITestResult], TestSuiteMetrics]:
        """Run the complete API integration test suite."""
        logger.info("Starting API integration test suite")

        test_cases = self._load_test_cases()

        # Filter by tags if specified
        if test_tags:
            test_cases = [tc for tc in test_cases if any(tag in tc.tags for tag in test_tags)]

        if not test_cases:
            logger.warning("No test cases found matching the specified tags")
            return [], TestSuiteMetrics(0, 0, 0, 0, 0, 0, 0, ("", 0), ("", 0), 0)

        start_time = time.time()

        if parallel:
            # Run tests in parallel
            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_with_semaphore(test_case):
                async with semaphore:
                    return await self._execute_test_case(test_case)

            tasks = [run_with_semaphore(tc) for tc in test_cases]
            self.test_results = await asyncio.gather(*tasks)
        else:
            # Run tests sequentially
            self.test_results = []
            for test_case in test_cases:
                result = await self._execute_test_case(test_case)
                self.test_results.append(result)

        total_execution_time = time.time() - start_time

        # Calculate metrics
        metrics = self._calculate_suite_metrics(self.test_results, total_execution_time)

        logger.info(f"API integration test suite completed: {metrics.passed_tests}/{metrics.total_tests} passed")

        return self.test_results, metrics

    def _calculate_suite_metrics(
        self,
        results: List[APITestResult],
        total_time: float
    ) -> TestSuiteMetrics:
        """Calculate test suite execution metrics."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.status == TestResult.PASSED)
        failed_tests = sum(1 for r in results if r.status == TestResult.FAILED)
        skipped_tests = sum(1 for r in results if r.status == TestResult.SKIPPED)
        error_tests = sum(1 for r in results if r.status == TestResult.ERROR)

        response_times = [r.execution_time for r in results if r.status != TestResult.ERROR]
        average_response_time = sum(response_times) / len(response_times) if response_times else 0

        slowest_test = ("", 0)
        fastest_test = ("", float('inf'))

        for result in results:
            if result.status != TestResult.ERROR:
                if result.execution_time > slowest_test[1]:
                    slowest_test = (result.test_case.name, result.execution_time)
                if result.execution_time < fastest_test[1]:
                    fastest_test = (result.test_case.name, result.execution_time)

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        return TestSuiteMetrics(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            total_execution_time=total_time,
            average_response_time=average_response_time,
            slowest_test=slowest_test,
            fastest_test=fastest_test,
            success_rate=success_rate
        )

    def generate_test_report(self, results: List[APITestResult], metrics: TestSuiteMetrics) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        report = {
            "test_summary": asdict(metrics),
            "test_results": [],
            "failed_tests": [],
            "performance_analysis": {},
            "recommendations": []
        }

        # Individual test results
        for result in results:
            test_result = {
                "name": result.test_case.name,
                "method": result.test_case.method,
                "endpoint": result.test_case.endpoint,
                "status": result.status.value,
                "execution_time": result.execution_time,
                "response_status": result.response_status,
                "tags": result.test_case.tags
            }

            if result.error_message:
                test_result["error_message"] = result.error_message

            report["test_results"].append(test_result)

            # Track failed tests
            if result.status in [TestResult.FAILED, TestResult.ERROR]:
                report["failed_tests"].append(test_result)

        # Performance analysis
        response_times = [r.execution_time for r in results if r.status != TestResult.ERROR]
        if response_times:
            report["performance_analysis"] = {
                "average_response_time": sum(response_times) / len(response_times),
                "min_response_time": min(response_times),
                "max_response_time": max(response_times),
                "response_time_std": self._calculate_std(response_times)
            }

        # Recommendations
        if metrics.success_rate < 90:
            report["recommendations"].append("Overall success rate is below 90%. Review failed tests.")

        if metrics.average_response_time > 2.0:
            report["recommendations"].append("Average response time is above 2s. Consider optimization.")

        if any(r.execution_time > 5.0 for r in results):
            report["recommendations"].append("Some tests are taking longer than 5s. Check for performance bottlenecks.")

        return report

    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    async def run_load_test(
        self,
        endpoint: str,
        method: str = "POST",
        body: Dict[str, Any] = None,
        concurrent_users: int = 10,
        duration_seconds: int = 60,
        ramp_up_seconds: int = 10
    ) -> Dict[str, Any]:
        """Run API load testing."""
        logger.info(f"Starting load test: {concurrent_users} users for {duration_seconds}s")

        start_time = time.time()
        end_time = start_time + duration_seconds

        async def user_session(user_id: int, delay_start: float):
            await asyncio.sleep(delay_start)

            requests_sent = 0
            response_times = []
            errors = 0

            while time.time() < end_time:
                request_start = time.time()

                try:
                    response = await self.client.request(
                        method=method,
                        url=f"{self.base_url}{endpoint}",
                        json=body
                    )

                    response_time = time.time() - request_start
                    response_times.append(response_time)
                    requests_sent += 1

                    if response.status_code >= 400:
                        errors += 1

                except Exception as e:
                    errors += 1
                    logger.error(f"User {user_id} request failed: {e}")

                # Small delay between requests
                await asyncio.sleep(0.1)

            return {
                "user_id": user_id,
                "requests_sent": requests_sent,
                "response_times": response_times,
                "errors": errors
            }

        # Create user sessions with staggered starts
        tasks = []
        for i in range(concurrent_users):
            delay = (i / concurrent_users) * ramp_up_seconds
            task = user_session(i, delay)
            tasks.append(task)

        # Run all user sessions
        user_results = await asyncio.gather(*tasks)

        # Aggregate results
        total_requests = sum(r["requests_sent"] for r in user_results)
        total_errors = sum(r["errors"] for r in user_results)
        all_response_times = []

        for result in user_results:
            all_response_times.extend(result["response_times"])

        actual_duration = time.time() - start_time

        load_test_results = {
            "load_test_summary": {
                "concurrent_users": concurrent_users,
                "duration_seconds": actual_duration,
                "total_requests": total_requests,
                "successful_requests": total_requests - total_errors,
                "failed_requests": total_errors,
                "requests_per_second": total_requests / actual_duration,
                "error_rate": (total_errors / total_requests) * 100 if total_requests > 0 else 0
            },
            "performance_metrics": {}
        }

        if all_response_times:
            load_test_results["performance_metrics"] = {
                "average_response_time": sum(all_response_times) / len(all_response_times),
                "min_response_time": min(all_response_times),
                "max_response_time": max(all_response_times),
                "p95_response_time": self._calculate_percentile(all_response_times, 95),
                "p99_response_time": self._calculate_percentile(all_response_times, 99)
            }

        return load_test_results

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not values:
            return 0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]


# Pytest integration
@pytest.fixture
async def api_tester():
    """Pytest fixture for API integration tester."""
    async with APIIntegrationTester() as tester:
        yield tester


@pytest.mark.asyncio
async def test_api_health_check(api_tester: APIIntegrationTester):
    """Test API health check endpoint."""
    test_case = APITestCase(
        name="Health Check",
        method="GET",
        endpoint="/health",
        expected_status=200
    )

    result = await api_tester._execute_test_case(test_case)
    assert result.status == TestResult.PASSED
    assert result.response_status == 200


@pytest.mark.asyncio
async def test_chat_message_flow(api_tester: APIIntegrationTester):
    """Test complete chat message flow."""
    # Send message
    test_case = APITestCase(
        name="Send Message",
        method="POST",
        endpoint="/api/v1/chat/message",
        body={
            "message": "Hello, I need help with my order",
            "conversation_id": None
        },
        expected_status=200
    )

    result = await api_tester._execute_test_case(test_case)
    assert result.status == TestResult.PASSED
    assert result.response_body is not None
    assert "message" in result.response_body


if __name__ == "__main__":
    # Run tests directly
    async def main():
        async with APIIntegrationTester() as tester:
            results, metrics = await tester.run_test_suite()
            report = tester.generate_test_report(results, metrics)

            print(json.dumps(report, indent=2))

            # Run load test
            load_results = await tester.run_load_test(
                endpoint="/api/v1/chat/message",
                body={"message": "Load test message", "conversation_id": None},
                concurrent_users=5,
                duration_seconds=30
            )

            print("\nLoad Test Results:")
            print(json.dumps(load_results, indent=2))

    asyncio.run(main())