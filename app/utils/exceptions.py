"""
Custom exception classes for the application.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class ShopAssistantException(Exception):
    """Base exception class for Shop Assistant AI."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(ShopAssistantException):
    """Exception raised for validation errors."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        self.field = field
        super().__init__(message, error_code="VALIDATION_ERROR", **kwargs)


class AuthenticationError(ShopAssistantException):
    """Exception raised for authentication errors."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, error_code="AUTHENTICATION_ERROR", **kwargs)


class AuthorizationError(ShopAssistantException):
    """Exception raised for authorization errors."""

    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(message, error_code="AUTHORIZATION_ERROR", **kwargs)


class NotFoundError(ShopAssistantException):
    """Exception raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, error_code="NOT_FOUND", **kwargs)


class ConflictError(ShopAssistantException):
    """Exception raised for conflict errors."""

    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(message, error_code="CONFLICT", **kwargs)


class RateLimitError(ShopAssistantException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, error_code="RATE_LIMIT_EXCEEDED", **kwargs)


class ExternalServiceError(ShopAssistantException):
    """Exception raised for external service errors."""

    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        **kwargs
    ):
        self.service_name = service_name
        super().__init__(message, error_code="EXTERNAL_SERVICE_ERROR", **kwargs)


class LLMError(ShopAssistantException):
    """Exception raised for LLM-related errors."""

    def __init__(
        self,
        message: str = "LLM processing error",
        model_name: Optional[str] = None,
        **kwargs
    ):
        self.model_name = model_name
        super().__init__(message, error_code="LLM_ERROR", **kwargs)


class DatabaseError(ShopAssistantException):
    """Exception raised for database errors."""

    def __init__(self, message: str = "Database error", **kwargs):
        super().__init__(message, error_code="DATABASE_ERROR", **kwargs)


class CacheError(ShopAssistantException):
    """Exception raised for cache errors."""

    def __init__(self, message: str = "Cache error", **kwargs):
        super().__init__(message, error_code="CACHE_ERROR", **kwargs)


# HTTP Exception helpers
def create_http_exception(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create an HTTP exception with structured response."""
    return HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "error_code": error_code,
            "details": details or {},
        }
    )


def create_validation_http_exception(
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a validation HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=message,
        error_code="VALIDATION_ERROR",
        details={**(details or {}), "field": field} if field else details or {},
    )


def create_not_found_http_exception(
    message: str = "Resource not found",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a not found HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_404_NOT_FOUND,
        message=message,
        error_code="NOT_FOUND",
        details=details,
    )


def create_unauthorized_http_exception(
    message: str = "Unauthorized",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create an unauthorized HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_401_UNAUTHORIZED,
        message=message,
        error_code="UNAUTHORIZED",
        details=details,
    )


def create_forbidden_http_exception(
    message: str = "Forbidden",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a forbidden HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        message=message,
        error_code="FORBIDDEN",
        details=details,
    )


def create_conflict_http_exception(
    message: str = "Conflict",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a conflict HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_409_CONFLICT,
        message=message,
        error_code="CONFLICT",
        details=details,
    )


def create_rate_limit_http_exception(
    message: str = "Rate limit exceeded",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create a rate limit HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        message=message,
        error_code="RATE_LIMIT_EXCEEDED",
        details=details,
    )


def create_internal_server_error_http_exception(
    message: str = "Internal server error",
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    """Create an internal server error HTTP exception."""
    return create_http_exception(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=message,
        error_code="INTERNAL_SERVER_ERROR",
        details=details,
    )