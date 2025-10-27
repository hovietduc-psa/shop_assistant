"""
Global exception handlers for FastAPI application.
"""

import logging
from typing import Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.utils.exceptions import ShopAssistantException

logger = logging.getLogger(__name__)


async def shop_assistant_exception_handler(
    request: Request, exc: ShopAssistantException
) -> JSONResponse:
    """Handle custom Shop Assistant exceptions."""
    logger.error(
        f"Shop Assistant Exception: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "details": exc.details,
            "url": str(request.url),
            "method": request.method,
        }
    )

    status_code = 500  # Default internal server error
    if exc.error_code == "VALIDATION_ERROR":
        status_code = 422
    elif exc.error_code == "NOT_FOUND":
        status_code = 404
    elif exc.error_code in ["AUTHENTICATION_ERROR", "UNAUTHORIZED"]:
        status_code = 401
    elif exc.error_code in ["AUTHORIZATION_ERROR", "FORBIDDEN"]:
        status_code = 403
    elif exc.error_code == "CONFLICT":
        status_code = 409
    elif exc.error_code == "RATE_LIMIT_EXCEEDED":
        status_code = 429
    elif exc.error_code in ["EXTERNAL_SERVICE_ERROR", "LLM_ERROR"]:
        status_code = 502

    return JSONResponse(
        status_code=status_code,
        content={
            "message": exc.message,
            "error_code": exc.error_code,
            "details": exc.details,
            "type": "shop_assistant_error",
        }
    )


async def http_exception_handler(
    request: Request, exc: Union[HTTPException, StarletteHTTPException]
) -> JSONResponse:
    """Handle HTTP exceptions."""
    logger.warning(
        f"HTTP Exception: {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "url": str(request.url),
            "method": request.method,
        }
    )

    # Extract structured detail if available
    detail = exc.detail
    if isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "message": detail.get("message", str(exc.detail)),
                "error_code": detail.get("error_code"),
                "details": detail.get("details", {}),
                "type": "http_error",
            }
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "message": str(exc.detail),
            "error_code": f"HTTP_{exc.status_code}",
            "details": {},
            "type": "http_error",
        }
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle request validation exceptions."""
    logger.warning(
        f"Validation Error: {exc.errors()}",
        extra={
            "errors": exc.errors(),
            "url": str(request.url),
            "method": request.method,
        }
    )

    # Format validation errors
    formatted_errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        formatted_errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "message": "Validation failed",
            "error_code": "VALIDATION_ERROR",
            "details": {"errors": formatted_errors},
            "type": "validation_error",
        }
    )


async def database_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Handle database exceptions."""
    logger.error(
        f"Database Error: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "url": str(request.url),
            "method": request.method,
        }
    )

    message = "Database operation failed"
    if isinstance(exc, IntegrityError):
        message = "Database integrity constraint violated"

    return JSONResponse(
        status_code=500,
        content={
            "message": message,
            "error_code": "DATABASE_ERROR",
            "details": {"exception_type": type(exc).__name__},
            "type": "database_error",
        }
    )


async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle general exceptions."""
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "exception_type": type(exc).__name__,
            "url": str(request.url),
            "method": request.method,
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "error_code": "INTERNAL_SERVER_ERROR",
            "details": {
                "exception_type": type(exc).__name__,
                "debug_message": str(exc) if request.app.debug else None,
            },
            "type": "internal_error",
        }
    )