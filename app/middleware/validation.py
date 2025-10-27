"""
API request/response validation middleware.
"""

import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import re
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.concurrency import iterate_in_threadpool
from pydantic import BaseModel, ValidationError
from loguru import logger

from app.core.config import settings


class ValidationLevel(Enum):
    """Validation severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationRule:
    """Validation rule definition."""
    name: str
    level: ValidationLevel
    validator: Callable[[Any], bool]
    message: str
    action: str = "log"  # log, block, modify


@dataclass
class ValidationResult:
    """Validation result."""
    rule_name: str
    level: ValidationLevel
    passed: bool
    message: str
    action: str
    details: Optional[Dict[str, Any]] = None


class RequestValidator:
    """Request validation utility."""

    def __init__(self):
        self.rules = self._load_default_rules()

    def _load_default_rules(self) -> List[ValidationRule]:
        """Load default validation rules."""
        return [
            # Size limits
            ValidationRule(
                name="max_request_size",
                level=ValidationLevel.ERROR,
                validator=lambda req: len(req.get("body", "")) <= settings.MAX_REQUEST_SIZE,
                message=f"Request size exceeds maximum allowed size of {settings.MAX_REQUEST_SIZE} bytes",
                action="block"
            ),

            # Content type validation
            ValidationRule(
                name="valid_content_type",
                level=ValidationLevel.WARNING,
                validator=lambda req: self._validate_content_type(req.get("headers", {})),
                message="Invalid or missing content-type header",
                action="log"
            ),

            # SQL injection detection
            ValidationRule(
                name="sql_injection_check",
                level=ValidationLevel.CRITICAL,
                validator=lambda req: self._check_sql_injection(req.get("body", "")),
                message="Potential SQL injection detected",
                action="block"
            ),

            # XSS detection
            ValidationRule(
                name="xss_check",
                level=ValidationLevel.CRITICAL,
                validator=lambda req: self._check_xss(req.get("body", "")),
                message="Potential XSS attack detected",
                action="block"
            ),

            # Request rate validation (basic)
            ValidationRule(
                name="basic_rate_check",
                level=ValidationLevel.WARNING,
                validator=lambda req: self._basic_rate_check(req.get("client_ip", "")),
                message="High request frequency detected",
                action="log"
            ),

            # JSON structure validation
            ValidationRule(
                name="valid_json",
                level=ValidationLevel.ERROR,
                validator=lambda req: self._validate_json(req.get("body", "")),
                message="Invalid JSON structure",
                action="block"
            ),

            # Required headers validation
            ValidationRule(
                name="required_headers",
                level=ValidationLevel.WARNING,
                validator=lambda req: self._validate_required_headers(req.get("headers", {})),
                message="Missing required headers",
                action="log"
            ),
        ]

    def _validate_content_type(self, headers: Dict[str, str]) -> bool:
        """Validate content-type header."""
        content_type = headers.get("content-type", "").lower()

        # Allow common content types
        allowed_types = [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain"
        ]

        return any(allowed in content_type for allowed in allowed_types)

    def _check_sql_injection(self, body: str) -> bool:
        """Check for SQL injection patterns."""
        if not body:
            return True

        # Common SQL injection patterns
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
            r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
            r"(\b(OR|AND)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(--|#|/\*|\*/)",
            r"(\b(SCRIPT|JAVASCRIPT|VBSCRIPT|ONLOAD|ONERROR)\b)",
            r"(\b(CHAR|VARCHAR|INT|TEXT|DATE)\s*\()",
            r"(\b(INFORMATION_SCHEMA|SYS|MASTER|MSDB)\b)",
            r"(\b(SLEEP|BENCHMARK|WAITFOR|DELAY)\b)",
            r"(\b(USER|VERSION|DATABASE|@@)\b)"
        ]

        body_lower = body.lower()
        for pattern in sql_patterns:
            if re.search(pattern, body_lower, re.IGNORECASE):
                logger.warning(f"SQL injection pattern detected: {pattern}")
                return False

        return True

    def _check_xss(self, body: str) -> bool:
        """Check for XSS patterns."""
        if not body:
            return True

        # Common XSS patterns
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"expression\s*\(",
            r"@import",
            r"vbscript:",
            r"behavior\s*:",
            r"binding\s*:",
            r"base64\s*:",
            r"data\s*:",
            r"<svg[^>]*>.*?</svg>"
        ]

        body_lower = body.lower()
        for pattern in xss_patterns:
            if re.search(pattern, body_lower, re.IGNORECASE):
                logger.warning(f"XSS pattern detected: {pattern}")
                return False

        return True

    def _basic_rate_check(self, client_ip: str) -> bool:
        """Basic rate check (placeholder - would use proper rate limiting)."""
        # This is a simplified check - real implementation would use Redis or similar
        return True

    def _validate_json(self, body: str) -> bool:
        """Validate JSON structure."""
        if not body:
            return True

        # Check if it's supposed to be JSON
        if body.strip().startswith('{') or body.strip().startswith('['):
            try:
                json.loads(body)
                return True
            except json.JSONDecodeError:
                return False

        return True

    def _validate_required_headers(self, headers: Dict[str, str]) -> bool:
        """Validate required headers."""
        # Define required headers based on your application needs
        required_headers = []

        # Check for API key if required
        if settings.REQUIRE_API_KEY:
            if not headers.get("x-api-key"):
                return False

        return True

    async def validate_request(self, request: Request) -> List[ValidationResult]:
        """Validate incoming request."""
        results = []

        try:
            # Get request data
            request_data = await self._extract_request_data(request)

            # Run validation rules
            for rule in self.rules:
                try:
                    passed = rule.validator(request_data)
                    result = ValidationResult(
                        rule_name=rule.name,
                        level=rule.level,
                        passed=passed,
                        message=rule.message,
                        action=rule.action,
                        details={"request_size": len(request_data.get("body", ""))}
                    )
                    results.append(result)

                    # Log validation result
                    if not passed:
                        logger.warning(
                            f"Request validation failed: {rule.name} - {rule.message}"
                        )

                except Exception as e:
                    logger.error(f"Validation rule error ({rule.name}): {e}")
                    results.append(ValidationResult(
                        rule_name=rule.name,
                        level=ValidationLevel.ERROR,
                        passed=False,
                        message=f"Validation rule error: {str(e)}",
                        action="log"
                    ))

        except Exception as e:
            logger.error(f"Request validation error: {e}")
            results.append(ValidationResult(
                rule_name="request_validation",
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"Request validation failed: {str(e)}",
                action="log"
            ))

        return results

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract relevant data from request."""
        # Get request body
        try:
            body = await request.body()
            body_str = body.decode('utf-8', errors='ignore')
        except Exception:
            body_str = ""

        # Get headers
        headers = dict(request.headers)

        # Get client IP
        client_ip = request.client.host
        forwarded_for = headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        return {
            "method": request.method,
            "url": str(request.url),
            "headers": headers,
            "body": body_str,
            "client_ip": client_ip,
            "user_agent": headers.get("user-agent", ""),
            "content_type": headers.get("content-type", ""),
            "content_length": headers.get("content-length", "0")
        }


class ResponseValidator:
    """Response validation utility."""

    def __init__(self):
        self.rules = self._load_default_rules()

    def _load_default_rules(self) -> List[ValidationRule]:
        """Load default response validation rules."""
        return [
            # Response size validation
            ValidationRule(
                name="max_response_size",
                level=ValidationLevel.WARNING,
                validator=lambda resp: len(resp.get("body", "")) <= settings.MAX_RESPONSE_SIZE,
                message=f"Response size exceeds maximum of {settings.MAX_RESPONSE_SIZE} bytes",
                action="log"
            ),

            # Sensitive data exposure check
            ValidationRule(
                name="sensitive_data_check",
                level=ValidationLevel.CRITICAL,
                validator=lambda resp: self._check_sensitive_data(resp.get("body", "")),
                message="Potential sensitive data exposure detected",
                action="log"
            ),

            # Error information disclosure
            ValidationRule(
                name="error_disclosure_check",
                level=ValidationLevel.WARNING,
                validator=lambda resp: self._check_error_disclosure(resp.get("body", "")),
                message="Detailed error information in response",
                action="log"
            ),

            # Response structure validation
            ValidationRule(
                name="response_structure",
                level=ValidationLevel.ERROR,
                validator=lambda resp: self._validate_response_structure(resp),
                message="Invalid response structure",
                action="log"
            ),
        ]

    def _check_sensitive_data(self, body: str) -> bool:
        """Check for sensitive data exposure."""
        if not body:
            return True

        # Patterns that might indicate sensitive data exposure
        sensitive_patterns = [
            r"password\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]",
            r"token\s*[:=]\s*['\"][^'\"]{16,}['\"]",
            r"api_key\s*[:=]\s*['\"][^'\"]{16,}['\"]",
            r"private_key\s*[:=]\s*['\"][^'\"]{32,}['\"]",
            r"credit_card\s*[:=]\s*['\"]?\d{13,19}['\"]?",
            r"ssn\s*[:=]\s*['\"]?\d{3}-?\d{2}-?\d{4}['\"]?",
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"  # Credit card pattern
        ]

        body_lower = body.lower()
        for pattern in sensitive_patterns:
            if re.search(pattern, body_lower, re.IGNORECASE):
                logger.warning(f"Sensitive data pattern detected: {pattern}")
                return False

        return True

    def _check_error_disclosure(self, body: str) -> bool:
        """Check for excessive error information disclosure."""
        if not body:
            return True

        # Patterns that might indicate excessive error information
        error_patterns = [
            r"traceback\s*\(",
            r"stack\s*trace",
            r"internal\s*server\s*error",
            r"file\s*path\s*[:=]",
            r"line\s*\d+",
            r"exception\s*:",
            r"error\s*code\s*\d+",
            r"mysql\s*error",
            r"postgresql\s*error",
            r"sqlite\s*error"
        ]

        body_lower = body.lower()
        found_patterns = []
        for pattern in error_patterns:
            if re.search(pattern, body_lower, re.IGNORECASE):
                found_patterns.append(pattern)

        # Allow some error information but flag excessive detail
        if len(found_patterns) > 2:
            logger.warning(f"Excessive error disclosure: {found_patterns}")
            return False

        return True

    def _validate_response_structure(self, response_data: Dict[str, Any]) -> bool:
        """Validate response structure."""
        # Basic structure validation
        if response_data.get("status_code", 200) >= 400:
            # Error responses should have error information
            body = response_data.get("body", "")
            if not body:
                return False

        return True

    async def validate_response(self, response: Response, request: Request) -> List[ValidationResult]:
        """Validate outgoing response."""
        results = []

        try:
            # Get response data
            response_data = await self._extract_response_data(response, request)

            # Run validation rules
            for rule in self.rules:
                try:
                    passed = rule.validator(response_data)
                    result = ValidationResult(
                        rule_name=rule.name,
                        level=rule.level,
                        passed=passed,
                        message=rule.message,
                        action=rule.action,
                        details={"response_size": len(response_data.get("body", ""))}
                    )
                    results.append(result)

                    # Log validation result
                    if not passed:
                        logger.warning(
                            f"Response validation failed: {rule.name} - {rule.message}"
                        )

                except Exception as e:
                    logger.error(f"Response validation rule error ({rule.name}): {e}")
                    results.append(ValidationResult(
                        rule_name=rule.name,
                        level=ValidationLevel.ERROR,
                        passed=False,
                        message=f"Validation rule error: {str(e)}",
                        action="log"
                    ))

        except Exception as e:
            logger.error(f"Response validation error: {e}")
            results.append(ValidationResult(
                rule_name="response_validation",
                level=ValidationLevel.ERROR,
                passed=False,
                message=f"Response validation failed: {str(e)}",
                action="log"
            ))

        return results

    async def _extract_response_data(self, response: Response, request: Request) -> Dict[str, Any]:
        """Extract relevant data from response."""
        # Get response body
        try:
            if hasattr(response, 'body'):
                body = response.body
                if isinstance(body, bytes):
                    body_str = body.decode('utf-8', errors='ignore')
                else:
                    body_str = str(body)
            else:
                body_str = ""
        except Exception:
            body_str = ""

        # Get headers
        headers = dict(response.headers) if hasattr(response, 'headers') else {}

        return {
            "status_code": getattr(response, 'status_code', 200),
            "headers": headers,
            "body": body_str,
            "content_type": headers.get("content-type", ""),
            "content_length": headers.get("content-length", "0"),
            "request_method": request.method,
            "request_url": str(request.url)
        }


class ValidationMiddleware(BaseHTTPMiddleware):
    """API validation middleware."""

    def __init__(
        self,
        app,
        enable_request_validation: bool = True,
        enable_response_validation: bool = True,
        block_on_critical: bool = True
    ):
        super().__init__(app)
        self.enable_request_validation = enable_request_validation
        self.enable_response_validation = enable_response_validation
        self.block_on_critical = block_on_critical

        self.request_validator = RequestValidator()
        self.response_validator = ResponseValidator()

    async def dispatch(self, request: Request, call_next):
        """Process request through validation middleware."""
        # Request validation
        if self.enable_request_validation:
            request_results = await self.request_validator.validate_request(request)

            # Check for critical failures that should block the request
            critical_failures = [
                result for result in request_results
                if not result.passed and result.level == ValidationLevel.CRITICAL and result.action == "block"
            ]

            if critical_failures and self.block_on_critical:
                logger.error(f"Request blocked due to critical validation failures: {[r.rule_name for r in critical_failures]}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Bad Request",
                        "message": "Request validation failed",
                        "validation_errors": [
                            {
                                "rule": r.rule_name,
                                "message": r.message,
                                "level": r.level.value
                            }
                            for r in critical_failures
                        ]
                    }
                )

            # Log all validation results
            for result in request_results:
                if not result.passed:
                    self._log_validation_result(result, "request")

        # Process the request
        response = await call_next(request)

        # Response validation
        if self.enable_response_validation:
            response_results = await self.response_validator.validate_response(response, request)

            # Log validation results
            for result in response_results:
                if not result.passed:
                    self._log_validation_result(result, "response")

            # Add validation headers if needed
            if any(not r.passed for r in response_results):
                response.headers["X-Validation-Warnings"] = str(len([r for r in response_results if not r.passed]))

        return response

    def _log_validation_result(self, result: ValidationResult, validation_type: str):
        """Log validation result based on level."""
        message = f"{validation_type.title()} validation failed - {result.rule_name}: {result.message}"

        if result.level == ValidationLevel.CRITICAL:
            logger.error(message)
        elif result.level == ValidationLevel.ERROR:
            logger.error(message)
        elif result.level == ValidationLevel.WARNING:
            logger.warning(message)
        else:
            logger.info(message)


class SanitizationService:
    """Data sanitization service."""

    @staticmethod
    def sanitize_input(data: str) -> str:
        """Sanitize input string."""
        if not data:
            return data

        # Remove potential malicious content
        sanitized = data

        # Remove script tags
        sanitized = re.sub(r'<script[^>]*>.*?</script>', '', sanitized, flags=re.IGNORECASE | re.DOTALL)

        # Remove potentially dangerous attributes
        sanitized = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', sanitized, flags=re.IGNORECASE)

        # Remove javascript: protocol
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)

        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())

        return sanitized.strip()

    @staticmethod
    def sanitize_output(data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize output data dictionary."""
        if not isinstance(data, dict):
            return data

        sanitized = data.copy()

        # Remove sensitive keys
        sensitive_keys = ['password', 'secret', 'token', 'api_key', 'private_key']
        for key in list(sanitized.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***REDACTED***"

        return sanitized


# Pydantic models for validation
class ValidationRequest(BaseModel):
    """Validation request model."""
    data: Dict[str, Any]
    rules: Optional[List[str]] = None


class ValidationResponse(BaseModel):
    """Validation response model."""
    valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]


# Dependency injection
async def get_validation_service() -> ValidationMiddleware:
    """Get validation service instance."""
    return ValidationMiddleware(
        app=None,  # Will be set during app initialization
        enable_request_validation=settings.ENABLE_REQUEST_VALIDATION,
        enable_response_validation=settings.ENABLE_RESPONSE_VALIDATION,
        block_on_critical=settings.BLOCK_ON_CRITICAL_VALIDATION
    )