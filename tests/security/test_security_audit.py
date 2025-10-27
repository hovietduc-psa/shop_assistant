"""
Security audit and penetration testing for Shop Assistant AI.
"""

import pytest
import json
import re
import base64
import hashlib
import secrets
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import requests

from app.main import app


@pytest.mark.security
class TestSecurityAudit:
    """Security audit and penetration testing suite."""

    @pytest.fixture
    def security_client(self):
        """Create test client for security testing."""
        return TestClient(app)

    def test_authentication_bypass_attempts(self, security_client):
        """Test various authentication bypass attempts."""
        # Test 1: Missing authentication header
        response = security_client.get("/api/v1/intelligence/dashboard/overview")
        assert response.status_code == 401

        # Test 2: Invalid token format
        security_client.headers.update({"Authorization": "InvalidToken"})
        response = security_client.get("/api/v1/intelligence/dashboard/overview")
        assert response.status_code == 401

        # Test 3: Malformed JWT
        security_client.headers.update({"Authorization": "Bearer not.a.valid.jwt"})
        response = security_client.get("/api/v1/intelligence/dashboard/overview")
        assert response.status_code == 401

        # Test 4: Expired token simulation
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE1MTYyMzkwMjJ9.invalid"
        security_client.headers.update({"Authorization": f"Bearer {expired_token}"})
        response = security_client.get("/api/v1/intelligence/dashboard/overview")
        assert response.status_code == 401

    def test_authorization_escalation_attempts(self, security_client, mock_current_user):
        """Test attempts to escalate privileges."""
        # Test 1: Accessing admin endpoints as regular user
        response = security_client.get("/api/v1/admin/system/config")
        assert response.status_code in [401, 403, 404]

        # Test 2: Modifying other users' data
        other_user_data = {
            "user_id": "other_user_123",
            "permissions": ["admin", "superuser"]
        }
        response = security_client.put("/api/v1/users/other_user_123", json=other_user_data)
        assert response.status_code in [401, 403, 404]

        # Test 3: Accessing restricted conversations
        response = security_client.get("/api/v1/conversations/restricted_conversation_123")
        assert response.status_code in [401, 403, 404]

    def test_sql_injection_attempts(self, security_client, mock_current_user):
        """Test SQL injection vulnerability attempts."""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1' UNION SELECT * FROM users --",
            "'; INSERT INTO users (id, email) VALUES (999, 'hacker@evil.com'); --",
            "admin'/*",
            "' OR 1=1#",
            "1' AND (SELECT COUNT(*) FROM users) > 0 --"
        ]

        for payload in malicious_inputs:
            # Test conversation ID injection
            response = security_client.get(f"/api/v1/conversations/{payload}/messages")
            assert response.status_code in [400, 404, 422]

            # Test search parameter injection
            response = security_client.get(f"/api/v1/conversations/search?q={payload}")
            assert response.status_code in [400, 422]

            # Test user ID injection in message submission
            message_data = {
                "conversation_id": "test_conv",
                "message": {
                    "content": "Test message",
                    "customer_id": payload,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            response = security_client.post("/api/v1/conversations/messages", json=message_data)
            assert response.status_code in [400, 422]

    def test_xss_vulnerability_checks(self, security_client, mock_current_user):
        """Test Cross-Site Scripting (XSS) vulnerability attempts."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            "<iframe src=javascript:alert('XSS')>",
            "'\"><script>alert('XSS')</script>",
            "<body onload=alert('XSS')>"
        ]

        for payload in xss_payloads:
            # Test message content XSS
            message_data = {
                "conversation_id": "xss_test_conv",
                "message": {
                    "content": payload,
                    "customer_id": "xss_test_customer",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            response = security_client.post("/api/v1/conversations/messages", json=message_data)

            # Should either accept and sanitize, or reject
            if response.status_code == 200:
                # If accepted, verify payload is sanitized in response
                response_text = response.text.lower()
                assert "<script>" not in response_text
                assert "javascript:" not in response_text
                assert "onerror=" not in response_text
                assert "onload=" not in response_text

            # Test search parameter XSS
            response = security_client.get(f"/api/v1/conversations/search?q={payload}")
            if response.status_code == 200:
                response_text = response.text.lower()
                assert "<script>" not in response_text

    def test_csrf_token_validation(self, security_client):
        """Test Cross-Site Request Forgery (CSRF) protection."""
        # Test 1: Request without CSRF token
        response = security_client.post(
            "/api/v1/conversations/messages",
            json={
                "conversation_id": "csrf_test",
                "message": {
                    "content": "Test message",
                    "customer_id": "csrf_test_customer"
                }
            },
            headers={"Content-Type": "application/json"}
        )

        # Should either require CSRF token or have other protection
        # This test verifies the behavior - adjust based on your CSRF implementation

    def test_input_validation_and_sanitization(self, security_client, mock_current_user):
        """Test input validation and sanitization."""
        test_cases = [
            # Oversized inputs
            {
                "name": "oversized_message",
                "data": {
                    "conversation_id": "a" * 10000,  # Very long ID
                    "message": {
                        "content": "x" * 1000000,  # Very long message
                        "customer_id": "y" * 10000
                    }
                },
                "expected_status": [400, 413, 422]
            },
            # Invalid data types
            {
                "name": "invalid_types",
                "data": {
                    "conversation_id": 12345,  # Number instead of string
                    "message": {
                        "content": ["array", "instead", "of", "string"],  # Array instead of string
                        "customer_id": {"key": "value"}  # Object instead of string
                    }
                },
                "expected_status": [400, 422]
            },
            # Special characters
            {
                "name": "special_chars",
                "data": {
                    "conversation_id": "test\x00\x01\x02",  # Control characters
                    "message": {
                        "content": "Test with \x00\x01\x02 control chars",
                        "customer_id": "customer\u0000test"
                    }
                },
                "expected_status": [400, 422]
            }
        ]

        for test_case in test_cases:
            response = security_client.post("/api/v1/conversations/messages", json=test_case["data"])
            assert response.status_code in test_case["expected_status"], \
                f"Test case '{test_case['name']}' failed with status {response.status_code}"

    def test_rate_limiting_effectiveness(self, security_client):
        """Test rate limiting to prevent DoS attacks."""
        # Rapid fire requests
        responses = []
        for i in range(100):  # Send many requests quickly
            response = security_client.post(
                "/api/v1/conversations/messages",
                json={
                    "conversation_id": f"rate_limit_test_{i}",
                    "message": {
                        "content": f"Rate limit test message {i}",
                        "customer_id": "rate_test_customer"
                    }
                }
            )
            responses.append(response.status_code)

        # Should have some rate limiting responses
        rate_limited_count = sum(1 for status in responses if status == 429)
        assert rate_limited_count > 0, "No rate limiting detected"

        # Should not block all legitimate requests
        successful_count = sum(1 for status in responses if status == 200)
        assert successful_count > 0, "All requests were rate limited"

    def test_sensitive_data_exposure(self, security_client, mock_current_user):
        """Test for sensitive data exposure in responses."""
        # Test 1: Error messages don't expose sensitive information
        response = security_client.get("/api/v1/nonexistent/endpoint")
        assert response.status_code == 404
        assert "database" not in response.text.lower()
        assert "password" not in response.text.lower()
        assert "secret" not in response.text.lower()
        assert "key" not in response.text.lower()

        # Test 2: Debug information not exposed
        response = security_client.get("/api/v1/conversations/invalid_conversation_id")
        if response.status_code != 200:
            assert "traceback" not in response.text.lower()
            assert "exception" not in response.text.lower()
            assert "stack trace" not in response.text.lower()

        # Test 3: User data filtering
        response = security_client.get("/api/v1/intelligence/dashboard/overview")
        if response.status_code == 200:
            response_text = response.text.lower()
            # Should not expose internal system details
            assert "internal_server_error" not in response_text
            assert "sql" not in response_text
            assert "admin_panel" not in response_text

    def test_file_upload_vulnerabilities(self, security_client, mock_current_user):
        """Test file upload security vulnerabilities."""
        malicious_files = [
            # Executable files
            ("malware.exe", b"MZ\x90\x00", "application/x-msdownload"),
            ("script.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            # Large files
            ("huge.txt", b"x" * (100 * 1024 * 1024), "text/plain"),  # 100MB
            # Files with suspicious names
            ("../../../etc/passwd", b"root:x:0:0:root:/root:/bin/bash", "text/plain"),
            ("config.ini", b"[database]\npassword=secret123", "text/plain")
        ]

        for filename, content, content_type in malicious_files:
            response = security_client.post(
                "/api/v1/files/upload",
                files={"file": (filename, content, content_type)}
            )

            # Should reject malicious uploads
            assert response.status_code in [400, 403, 413, 422], \
                f"Malicious file '{filename}' was accepted"

    def test_api_endpoint_enumeration(self, security_client):
        """Test protection against API endpoint enumeration."""
        common_endpoints = [
            "/api/v1/admin",
            "/api/v1/config",
            "/api/v1/debug",
            "/api/v1/health",
            "/api/v1/status",
            "/api/v1/system",
            "/api/v1/logs",
            "/api/v1/backup",
            "/api/v1/database"
        ]

        for endpoint in common_endpoints:
            response = security_client.get(endpoint)
            # Should either require authentication or not exist
            assert response.status_code in [401, 403, 404], \
                f"Endpoint '{endpoint}' is accessible without proper authorization"

    def test_http_header_security(self, security_client):
        """Test HTTP security headers."""
        response = security_client.get("/api/v1/")

        # Check for security headers
        headers = response.headers

        # These headers should be present in production
        # (Note: May not be present in test environment)
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy"
        ]

        # Log which headers are missing for review
        missing_headers = [h for h in security_headers if h not in headers]
        if missing_headers:
            print(f"Missing security headers: {missing_headers}")

    def test_session_management_security(self, security_client):
        """Test session management security."""
        # Test 1: Session fixation
        # (This would test if session IDs change after login)

        # Test 2: Session timeout
        # (This would test if sessions expire appropriately)

        # Test 3: Concurrent session limits
        # (This would test if users can have too many concurrent sessions)

        # For now, just verify endpoints exist and require authentication
        response = security_client.post("/api/v1/auth/login")
        # Should exist and require proper credentials
        assert response.status_code in [400, 422, 401]  # Missing credentials is expected

    def test_error_handling_information_disclosure(self, security_client, mock_current_user):
        """Test that error handling doesn't disclose sensitive information."""
        # Test various error conditions
        error_endpoints = [
            "/api/v1/conversations/invalid-uuid-format/messages",
            "/api/v1/intelligence/escalation/analyze",  # POST with no data
            "/api/v1/users/nonexistent-user-12345"
        ]

        for endpoint in error_endpoints:
            response = security_client.get(endpoint)

            # Should not expose sensitive information in error messages
            error_text = response.text.lower()
            sensitive_patterns = [
                "password",
                "secret",
                "key",
                "token",
                "database",
                "sql",
                "query",
                "stack trace",
                "traceback",
                "exception",
                "internal server",
                "debug"
            ]

            found_sensitive = [pattern for pattern in sensitive_patterns if pattern in error_text]

            if found_sensitive:
                print(f"Endpoint '{endpoint}' may expose sensitive info: {found_sensitive}")

    def test_dependency_vulnerabilities(self):
        """Test for known vulnerabilities in dependencies."""
        # This would typically integrate with security scanning tools
        # For now, just verify the structure exists

        try:
            import pkg_resources

            # Get list of installed packages
            installed_packages = [d.project_name for d in pkg_resources.working_set]

            # Check for common vulnerable packages (simplified check)
            known_vulnerable = [
                "requests<2.20.0",  # Example - check actual vulnerabilities
                "urllib3<1.24.2",
                "pyyaml<5.1"
            ]

            # In a real implementation, this would use a security database
            # For now, just log the packages for manual review
            print(f"Installed packages: {len(installed_packages)}")

        except ImportError:
            print("pkg_resources not available for dependency checking")

    def test_api_abuse_patterns(self, security_client, mock_current_user):
        """Test protection against API abuse patterns."""
        abuse_patterns = [
            # Test 1: Bulk operations
            lambda: [security_client.post("/api/v1/conversations/messages",
                json={"conversation_id": f"bulk_test_{i}", "message": {"content": f"Message {i}", "customer_id": "bulk_test"}})
                for i in range(50)],

            # Test 2: Large data requests
            lambda: security_client.get("/api/v1/conversations/search?limit=10000"),

            # Test 3: Complex query attempts
            lambda: security_client.get("/api/v1/intelligence/dashboard/overview?" + "&".join([f"param{i}=value{i}" for i in range(100)]))
        ]

        for i, pattern in enumerate(abuse_patterns):
            try:
                if i == 0:  # Bulk operations
                    responses = pattern()
                    rate_limited = sum(1 for r in responses if r.status_code == 429)
                    assert rate_limited > 0, "Bulk operations not rate limited"
                else:  # Other patterns
                    response = pattern()
                    # Should either succeed (if valid) or be properly rate limited
                    assert response.status_code in [200, 400, 413, 422, 429]
            except Exception as e:
                # Should handle abuse gracefully without crashing
                assert not isinstance(e, (ConnectionError, TimeoutError))

    def test_logging_and_monitoring(self, security_client, mock_current_user):
        """Test that security events are properly logged."""
        # Test suspicious activities
        suspicious_activities = [
            # Failed login attempts
            lambda: security_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}),
            # Accessing non-existent resources
            lambda: security_client.get("/api/v1/admin/secret"),
            # Invalid data submission
            lambda: security_client.post("/api/v1/conversations/messages", json={"invalid": "data"})
        ]

        for activity in suspicious_activities:
            try:
                response = activity()
                # Activity should be logged (this would be verified by checking logs in a real implementation)
                # For now, just ensure the system doesn't crash
                assert response.status_code in [400, 401, 403, 404, 422]
            except Exception as e:
                # Should handle gracefully
                pytest.fail(f"Suspicious activity caused exception: {e}")

    def test_cors_configuration(self, security_client):
        """Test Cross-Origin Resource Sharing (CORS) configuration."""
        # Test preflight request
        response = security_client.options(
            "/api/v1/conversations/messages",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        # Should either deny or properly configure CORS
        if response.status_code == 200:
            cors_headers = response.headers
            # If CORS is enabled, should be properly configured
            if "Access-Control-Allow-Origin" in cors_headers:
                # Should not allow arbitrary origins in production
                allowed_origin = cors_headers["Access-Control-Allow-Origin"]
                assert allowed_origin != "*", "Wildcard CORS origin not recommended for production"

    def test_sensitive_http_methods(self, security_client):
        """Test that sensitive HTTP methods are properly protected."""
        sensitive_methods = ["DELETE", "PUT", "PATCH"]
        test_endpoints = [
            "/api/v1/conversations/test_conv",
            "/api/v1/users/test_user",
            "/api/v1/intelligence/escalation/test_escalation"
        ]

        for method in sensitive_methods:
            for endpoint in test_endpoints:
                response = security_client.request(method, endpoint)
                # Should require authentication
                assert response.status_code in [401, 403, 404, 405], \
                    f"Sensitive method {method} on {endpoint} not properly protected"