"""
Shopify-specific exception handling and error classes.
"""

from typing import Dict, Any, Optional
from enum import Enum

from .models import ShopifyError


class ShopifyErrorCode(Enum):
    """Shopify API error codes."""
    # Authentication errors
    INVALID_ACCESS_TOKEN = "INVALID_ACCESS_TOKEN"
    INSUFFICIENT_SCOPE = "INSUFFICIENT_SCOPE"
    SHOP_NOT_FOUND = "SHOP_NOT_FOUND"

    # Rate limiting errors
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BURST_LIMIT_EXCEEDED = "BURST_LIMIT_EXCEEDED"

    # GraphQL errors
    GRAPHQL_VALIDATION_FAILED = "GRAPHQL_VALIDATION_FAILED"
    GRAPHQL_QUERY_COMPLEXITY = "GRAPHQL_QUERY_COMPLEXITY"

    # Resource errors
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    INVALID_RESOURCE = "INVALID_RESOURCE"

    # Permission errors
    PERMISSION_DENIED = "PERMISSION_DENIED"
    OPERATION_FORBIDDEN = "OPERATION_FORBIDDEN"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


class ShopifyRateLimitError(ShopifyError):
    """Error raised when Shopify API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, 429, **kwargs)
        self.retry_after = retry_after


class ShopifyAuthenticationError(ShopifyError):
    """Error raised when Shopify authentication fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, 401, **kwargs)


class ShopifyPermissionError(ShopifyError):
    """Error raised when Shopify permission is denied."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, 403, **kwargs)


class ShopifyNotFoundError(ShopifyError):
    """Error raised when Shopify resource is not found."""

    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(message, 404, **kwargs)
        self.resource_type = resource_type


class ShopifyValidationError(ShopifyError):
    """Error raised when Shopify request validation fails."""

    def __init__(self, message: str, validation_errors: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(message, 422, **kwargs)
        self.validation_errors = validation_errors or {}


class ShopifyServerError(ShopifyError):
    """Error raised when Shopify server error occurs."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, 500, **kwargs)


class ShopifyTimeoutError(ShopifyError):
    """Error raised when Shopify request times out."""

    def __init__(self, message: str, timeout: Optional[float] = None, **kwargs):
        super().__init__(message, 408, **kwargs)
        self.timeout = timeout


class ShopifyConnectionError(ShopifyError):
    """Error raised when Shopify connection fails."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, 503, **kwargs)


class ShopifyGraphQLValidationError(ShopifyValidationError):
    """Error raised when GraphQL validation fails."""

    def __init__(self, message: str, graphql_errors: Optional[list] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.graphql_errors = graphql_errors or []


class ShopifyInventoryError(ShopifyError):
    """Error raised when inventory operations fail."""

    def __init__(self, message: str, variant_id: Optional[str] = None, location_id: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.variant_id = variant_id
        self.location_id = location_id


class ShopifyWebhookError(ShopifyError):
    """Error raised when webhook processing fails."""

    def __init__(self, message: str, webhook_topic: Optional[str] = None, shop_domain: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.webhook_topic = webhook_topic
        self.shop_domain = shop_domain


def shopify_error_from_response(status_code: int, response_data: Dict[str, Any]) -> ShopifyError:
    """
    Create appropriate ShopifyError from HTTP response.

    Args:
        status_code: HTTP status code
        response_data: Response data from Shopify

    Returns:
        Appropriate ShopifyError subclass
    """
    # Extract error message
    error_message = "Unknown Shopify error"
    if "errors" in response_data:
        errors = response_data["errors"]
        if isinstance(errors, str):
            error_message = errors
        elif isinstance(errors, dict):
            # Format validation errors
            error_parts = []
            for field, field_errors in errors.items():
                if isinstance(field_errors, list):
                    error_parts.append(f"{field}: {', '.join(field_errors)}")
                else:
                    error_parts.append(f"{field}: {field_errors}")
            error_message = "; ".join(error_parts)
    elif "error" in response_data:
        error_message = response_data["error"]
    elif "message" in response_data:
        error_message = response_data["message"]

    # Create appropriate error based on status code
    if status_code == 401:
        return ShopifyAuthenticationError(error_message, response=response_data)
    elif status_code == 403:
        return ShopifyPermissionError(error_message, response=response_data)
    elif status_code == 404:
        return ShopifyNotFoundError(error_message, response=response_data)
    elif status_code == 422:
        validation_errors = response_data.get("errors", {})
        return ShopifyValidationError(error_message, validation_errors, response=response_data)
    elif status_code == 429:
        retry_after = response_data.get("retry_after")
        return ShopifyRateLimitError(error_message, retry_after, response=response_data)
    elif status_code == 500:
        return ShopifyServerError(error_message, response=response_data)
    elif status_code == 503:
        return ShopifyConnectionError(error_message, response=response_data)
    else:
        return ShopifyError(error_message, status_code, response_data)


def shopify_graphql_error_from_response(errors: list) -> ShopifyGraphQLValidationError:
    """
    Create ShopifyGraphQLValidationError from GraphQL errors.

    Args:
        errors: List of GraphQL error objects

    Returns:
        ShopifyGraphQLValidationError
    """
    if not errors:
        return ShopifyGraphQLValidationError("Unknown GraphQL error")

    # Format error messages
    error_messages = []
    for error in errors:
        if isinstance(error, dict):
            message = error.get("message", "Unknown error")
            field = error.get("field")
            code = error.get("code")

            error_part = message
            if field:
                error_part = f"{field}: {error_part}"
            if code:
                error_part = f"{error_part} (code: {code})"

            error_messages.append(error_part)
        else:
            error_messages.append(str(error))

    error_message = "; ".join(error_messages)

    return ShopifyGraphQLValidationError(
        error_message,
        graphql_errors=errors
    )


def is_retryable_error(error: ShopifyError) -> bool:
    """
    Check if an error is retryable.

    Args:
        error: ShopifyError instance

    Returns:
        True if error is retryable, False otherwise
    """
    # Rate limit errors are retryable
    if isinstance(error, ShopifyRateLimitError):
        return True

    # Server errors are potentially retryable
    if isinstance(error, ShopifyServerError):
        return True

    # Connection errors are retryable
    if isinstance(error, ShopifyConnectionError):
        return True

    # Timeout errors are retryable
    if isinstance(error, ShopifyTimeoutError):
        return True

    # Check status code for other retryable errors
    if error.status_code in [429, 500, 502, 503, 504]:
        return True

    return False


def get_retry_delay(error: ShopifyError, attempt: int = 1) -> float:
    """
    Get retry delay for exponential backoff.

    Args:
        error: ShopifyError instance
        attempt: Current attempt number (1-based)

    Returns:
        Delay in seconds
    """
    if isinstance(error, ShopifyRateLimitError) and error.retry_after:
        return error.retry_after

    # Exponential backoff with jitter
    import random
    base_delay = min(2 ** (attempt - 1), 60)  # Max 60 seconds
    jitter = random.uniform(0, 0.1 * base_delay)

    return base_delay + jitter


class ShopErrorHandler:
    """Handler for Shopify errors with retry logic and logging."""

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    async def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute a function with retry logic for Shopify errors.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Last error if all retries fail
        """
        import asyncio
        from loguru import logger

        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except ShopifyError as e:
                last_error = e

                if not is_retryable_error(e) or attempt >= self.max_retries:
                    logger.error(f"Shopify operation failed after {attempt} attempts: {e}")
                    raise

                delay = get_retry_delay(e, attempt)
                logger.warning(f"Shopify operation failed (attempt {attempt}/{self.max_retries}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        raise last_error if last_error else ShopifyError("Unknown error during retry")