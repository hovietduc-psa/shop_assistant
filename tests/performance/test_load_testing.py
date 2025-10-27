"""
Load testing and performance benchmarks for Shop Assistant AI.
"""

import pytest
import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import json
import psutil
import threading

from app.main import app


@pytest.mark.performance
@pytest.mark.slow
class TestLoadTesting:
    """Test suite for load testing and performance benchmarks."""

    @pytest.fixture
    def load_client(self):
        """Create test client for load testing."""
        return TestClient(app)

    @pytest.fixture
    def performance_monitor(self):
        """Monitor system performance during tests."""
        class PerformanceMonitor:
            def __init__(self):
                self.start_time = None
                self.end_time = None
                self.cpu_samples = []
                self.memory_samples = []
                self.monitoring = False
                self.monitor_thread = None

            def start_monitoring(self):
                self.start_time = time.time()
                self.monitoring = True
                self.cpu_samples = []
                self.memory_samples = []
                self.monitor_thread = threading.Thread(target=self._monitor_loop)
                self.monitor_thread.start()

            def stop_monitoring(self):
                self.monitoring = False
                self.end_time = time.time()
                if self.monitor_thread:
                    self.monitor_thread.join()

            def _monitor_loop(self):
                while self.monitoring:
                    self.cpu_samples.append(psutil.cpu_percent())
                    self.memory_samples.append(psutil.virtual_memory().percent)
                    time.sleep(0.1)

            def get_stats(self):
                duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
                return {
                    "duration_seconds": duration,
                    "avg_cpu_percent": statistics.mean(self.cpu_samples) if self.cpu_samples else 0,
                    "max_cpu_percent": max(self.cpu_samples) if self.cpu_samples else 0,
                    "avg_memory_percent": statistics.mean(self.memory_samples) if self.memory_samples else 0,
                    "max_memory_percent": max(self.memory_samples) if self.memory_samples else 0,
                    "sample_count": len(self.cpu_samples)
                }

        return PerformanceMonitor()

    def test_single_conversation_performance_baseline(
        self,
        load_client,
        performance_monitor,
        mock_current_user,
        mock_llm_manager
    ):
        """Establish baseline performance for single conversation processing."""
        conversation_id = "perf_baseline_001"

        # Start performance monitoring
        performance_monitor.start_monitoring()

        # Time the entire conversation flow
        start_time = time.time()

        # Step 1: Submit message
        message_submit_start = time.time()
        response = load_client.post(
            "/api/v1/conversations/messages",
            json={
                "conversation_id": conversation_id,
                "message": {
                    "content": "I need help with my order status.",
                    "customer_id": "cust_perf_001",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
        message_submit_time = time.time() - message_submit_start

        assert response.status_code == 200
        assert message_submit_time < 2.0  # Should complete within 2 seconds

        # Step 2: Get AI response
        ai_response_start = time.time()
        ai_response = load_client.get(f"/api/v1/conversations/{conversation_id}/ai-response")
        ai_response_time = time.time() - ai_response_start

        assert ai_response.status_code == 200
        assert ai_response_time < 5.0  # AI response within 5 seconds

        # Step 3: Intelligence analysis
        intelligence_start = time.time()
        escalation_check = load_client.post(
            "/api/v1/intelligence/escalation/analyze",
            json={
                "conversation_id": conversation_id,
                "messages": [
                    {"role": "customer", "content": "I need help with my order status."},
                    {"role": "assistant", "content": ai_response.json()["content"]}
                ],
                "customer_id": "cust_perf_001"
            }
        )
        intelligence_time = time.time() - intelligence_start

        assert escalation_check.status_code == 200
        assert intelligence_time < 3.0  # Intelligence analysis within 3 seconds

        total_time = time.time() - start_time
        performance_monitor.stop_monitoring()

        # Performance assertions
        assert total_time < 10.0  # Complete flow within 10 seconds

        perf_stats = performance_monitor.get_stats()
        print(f"\nBaseline Performance Stats:")
        print(f"Total flow time: {total_time:.2f}s")
        print(f"Message submit: {message_submit_time:.2f}s")
        print(f"AI response: {ai_response_time:.2f}s")
        print(f"Intelligence analysis: {intelligence_time:.2f}s")
        print(f"System stats: {perf_stats}")

        # System resource usage should be reasonable
        assert perf_stats["max_cpu_percent"] < 80
        assert perf_stats["max_memory_percent"] < 90

    def test_concurrent_conversation_load(
        self,
        load_client,
        performance_monitor,
        mock_current_user,
        mock_llm_manager
    ):
        """Test system performance under concurrent conversation load."""
        concurrent_count = 20
        conversation_ids = [f"perf_concurrent_{i:03d}" for i in range(concurrent_count)]

        # Start performance monitoring
        performance_monitor.start_monitoring()

        def process_single_conversation(conv_id):
            """Process a single conversation and return timing."""
            start_time = time.time()

            # Submit message
            response = load_client.post(
                "/api/v1/conversations/messages",
                json={
                    "conversation_id": conv_id,
                    "message": {
                        "content": f"I need help with my order {conv_id}.",
                        "customer_id": f"cust_{conv_id}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )

            if response.status_code != 200:
                return None

            # Get AI response
            ai_response = load_client.get(f"/api/v1/conversations/{conv_id}/ai-response")
            if ai_response.status_code != 200:
                return None

            # Intelligence analysis
            escalation_check = load_client.post(
                "/api/v1/intelligence/escalation/analyze",
                json={
                    "conversation_id": conv_id,
                    "messages": [
                        {"role": "customer", "content": f"I need help with my order {conv_id}."},
                        {"role": "assistant", "content": ai_response.json()["content"]}
                    ],
                    "customer_id": f"cust_{conv_id}"
                }
            )

            if escalation_check.status_code != 200:
                return None

            return time.time() - start_time

        # Process conversations concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_count) as executor:
            futures = [executor.submit(process_single_conversation, conv_id) for conv_id in conversation_ids]
            results = [future.result() for future in futures]

        total_time = time.time() - start_time
        performance_monitor.stop_monitoring()

        # Analyze results
        successful_results = [r for r in results if r is not None]
        success_rate = len(successful_results) / concurrent_count

        # Performance assertions
        assert success_rate >= 0.8  # At least 80% success rate
        assert total_time < 30.0  # Complete all conversations within 30 seconds

        if successful_results:
            avg_conversation_time = statistics.mean(successful_results)
            max_conversation_time = max(successful_results)
            min_conversation_time = min(successful_results)

            print(f"\nConcurrent Load Test Results:")
            print(f"Concurrent conversations: {concurrent_count}")
            print(f"Success rate: {success_rate:.2%}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Average conversation time: {avg_conversation_time:.2f}s")
            print(f"Max conversation time: {max_conversation_time:.2f}s")
            print(f"Min conversation time: {min_conversation_time:.2f}s")

            perf_stats = performance_monitor.get_stats()
            print(f"System stats: {perf_stats}")

            # Individual conversation performance should still be reasonable
            assert avg_conversation_time < 8.0
            assert max_conversation_time < 15.0

            # System should handle load without excessive resource usage
            assert perf_stats["max_cpu_percent"] < 90
            assert perf_stats["max_memory_percent"] < 95

    def test_intelligence_analysis_load(
        self,
        load_client,
        performance_monitor,
        mock_current_user,
        mock_llm_manager
    ):
        """Test intelligence system performance under load."""
        analysis_count = 50

        # Create test conversation data
        conversations = []
        for i in range(analysis_count):
            conversations.append({
                "conversation_id": f"intel_load_{i:03d}",
                "messages": [
                    {"role": "customer", "content": f"I'm frustrated with my order {i}. This is terrible service!"},
                    {"role": "agent", "content": f"I understand your frustration about order {i}. Let me help you."}
                ],
                "customer_id": f"cust_intel_{i:03d}"
            })

        # Test escalation analysis performance
        performance_monitor.start_monitoring()

        def run_single_analysis(conv_data):
            """Run single intelligence analysis."""
            start_time = time.time()

            # Escalation analysis
            escalation_response = load_client.post(
                "/api/v1/intelligence/escalation/analyze",
                json=conv_data
            )

            if escalation_response.status_code != 200:
                return None

            # Quality assessment
            quality_response = load_client.post(
                "/api/v1/intelligence/quality/assess",
                json={
                    "conversation_id": conv_data["conversation_id"],
                    "messages": conv_data["messages"],
                    "agent_id": "agent_load_test"
                }
            )

            if quality_response.status_code != 200:
                return None

            return time.time() - start_time

        # Run analyses concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_single_analysis, conv) for conv in conversations]
            results = [future.result() for future in futures]

        total_time = time.time() - start_time
        performance_monitor.stop_monitoring()

        # Analyze results
        successful_results = [r for r in results if r is not None]
        success_rate = len(successful_results) / analysis_count

        print(f"\nIntelligence Load Test Results:")
        print(f"Total analyses: {analysis_count}")
        print(f"Successful analyses: {len(successful_results)}")
        print(f"Success rate: {success_rate:.2%}")
        print(f"Total time: {total_time:.2f}s")

        if successful_results:
            avg_analysis_time = statistics.mean(successful_results)
            throughput = len(successful_results) / total_time

            print(f"Average analysis time: {avg_analysis_time:.2f}s")
            print(f"Throughput: {throughput:.2f} analyses/second")

            perf_stats = performance_monitor.get_stats()
            print(f"System stats: {perf_stats}")

            # Performance assertions
            assert success_rate >= 0.85  # High success rate for intelligence analysis
            assert avg_analysis_time < 5.0  # Individual analysis should be fast
            assert throughput >= 2.0  # Should handle at least 2 analyses per second

    def test_memory_usage_under_load(
        self,
        load_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test memory usage patterns under sustained load."""
        initial_memory = psutil.virtual_memory().percent
        memory_samples = [initial_memory]

        # Sustained load test
        for batch in range(5):  # 5 batches of 10 conversations each
            print(f"Memory test batch {batch + 1}/5")

            # Create and process 10 conversations
            for i in range(10):
                conv_id = f"memory_test_{batch}_{i}"
                response = load_client.post(
                    "/api/v1/conversations/messages",
                    json={
                        "conversation_id": conv_id,
                        "message": {
                            "content": f"Memory test conversation {batch}-{i}",
                            "customer_id": f"cust_memory_{batch}_{i}",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                assert response.status_code == 200

                # Get AI response
                ai_response = load_client.get(f"/api/v1/conversations/{conv_id}/ai-response")
                assert ai_response.status_code == 200

            # Sample memory after batch
            current_memory = psutil.virtual_memory().percent
            memory_samples.append(current_memory)

            # Brief pause between batches
            time.sleep(1)

        # Analyze memory usage
        max_memory = max(memory_samples)
        memory_growth = max_memory - initial_memory

        print(f"\nMemory Usage Test Results:")
        print(f"Initial memory: {initial_memory:.1f}%")
        print(f"Max memory: {max_memory:.1f}%")
        print(f"Memory growth: {memory_growth:.1f}%")
        print(f"Memory samples: {memory_samples}")

        # Memory assertions
        assert max_memory < 90  # Should not exceed 90% memory usage
        assert memory_growth < 20  # Should not grow more than 20 percentage points

    def test_api_response_time_percentiles(
        self,
        load_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test API response time percentiles under various loads."""
        response_times = []
        test_count = 100

        # Collect response times for various endpoints
        for i in range(test_count):
            conv_id = f"percentile_test_{i:03d}"

            # Test message submission endpoint
            start_time = time.time()
            response = load_client.post(
                "/api/v1/conversations/messages",
                json={
                    "conversation_id": conv_id,
                    "message": {
                        "content": f"Percentile test message {i}",
                        "customer_id": f"cust_percentile_{i}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            response_time = time.time() - start_time

            if response.status_code == 200:
                response_times.append(response_time)

        # Calculate percentiles
        if response_times:
            p50 = statistics.median(response_times)
            p95 = sorted(response_times)[int(len(response_times) * 0.95)]
            p99 = sorted(response_times)[int(len(response_times) * 0.99)]
            avg_time = statistics.mean(response_times)
            max_time = max(response_times)

            print(f"\nAPI Response Time Percentiles:")
            print(f"Total requests: {len(response_times)}")
            print(f"Average: {avg_time:.3f}s")
            print(f"50th percentile (median): {p50:.3f}s")
            print(f"95th percentile: {p95:.3f}s")
            print(f"99th percentile: {p99:.3f}s")
            print(f"Maximum: {max_time:.3f}s")

            # Performance assertions
            assert p50 < 1.0  # Median response time under 1 second
            assert p95 < 2.0  # 95% of requests under 2 seconds
            assert p99 < 5.0  # 99% of requests under 5 seconds
            assert max_time < 10.0  # Maximum response time under 10 seconds

    def test_rate_limiting_performance(
        self,
        load_client,
        mock_current_user
    ):
        """Test rate limiting behavior and performance impact."""
        request_times = []
        rate_limited_requests = 0

        # Send rapid requests to test rate limiting
        for i in range(200):  # More than typical rate limit
            start_time = time.time()
            response = load_client.post(
                "/api/v1/conversations/messages",
                json={
                    "conversation_id": f"rate_limit_{i:03d}",
                    "message": {
                        "content": f"Rate limit test {i}",
                        "customer_id": f"cust_rate_{i}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            response_time = time.time() - start_time

            request_times.append(response_time)

            if response.status_code == 429:  # Rate limited
                rate_limited_requests += 1
                # Wait for rate limit to reset
                time.sleep(0.1)

        # Analyze rate limiting behavior
        total_requests = len(request_times)
        rate_limit_rate = rate_limited_requests / total_requests

        print(f"\nRate Limiting Test Results:")
        print(f"Total requests: {total_requests}")
        print(f"Rate limited requests: {rate_limited_requests}")
        print(f"Rate limiting rate: {rate_limit_rate:.2%}")

        if request_times:
            avg_response_time = statistics.mean(request_times)
            print(f"Average response time: {avg_response_time:.3f}s")

        # Should implement some rate limiting
        assert rate_limit_rate > 0.01  # At least 1% of requests should be rate limited
        assert rate_limit_rate < 0.5   # But not more than 50% of requests

    def test_long_running_conversation_performance(
        self,
        load_client,
        mock_current_user,
        mock_llm_manager
    ):
        """Test performance of long-running conversations with many messages."""
        conversation_id = "long_running_test"
        message_count = 20
        response_times = []

        start_time = time.time()

        for i in range(message_count):
            # Alternate between customer and agent messages
            if i % 2 == 0:
                role = "customer"
                content = f"Customer message {i//2 + 1} with detailed information about their issue and requirements."
            else:
                role = "agent"
                content = f"Agent response {i//2 + 1} providing comprehensive help and assistance."

            message_start = time.time()
            response = load_client.post(
                "/api/v1/conversations/messages",
                json={
                    "conversation_id": conversation_id,
                    "message": {
                        "content": content,
                        "role": role,
                        "customer_id": "cust_long_running" if role == "customer" else None,
                        "agent_id": "agent_long_running" if role == "agent" else None,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
            message_time = time.time() - message_start

            assert response.status_code == 200
            response_times.append(message_time)

            # Brief pause between messages
            time.sleep(0.1)

        total_time = time.time() - start_time
        avg_message_time = statistics.mean(response_times)
        max_message_time = max(response_times)

        print(f"\nLong-running Conversation Test Results:")
        print(f"Total messages: {message_count}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Average message time: {avg_message_time:.3f}s")
        print(f"Max message time: {max_message_time:.3f}s")
        print(f"Messages per second: {message_count / total_time:.2f}")

        # Performance should remain consistent for long conversations
        assert avg_message_time < 2.0
        assert max_message_time < 5.0
        assert message_count / total_time > 2.0  # At least 2 messages per second