"""
API security middleware and hardening.
"""

import time
import hashlib
import hmac
import secrets
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import re
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from loguru import logger

from app.core.config import settings
import redis


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for rate limiting and request validation."""

    def __init__(self, app, redis_client: redis.Redis = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.rate_limits = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with security checks."""
        client_ip = self._get_client_ip(request)

        # Rate limiting
        if not await self._check_rate_limit(request, client_ip):
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"}
            )

        # Request validation
        await self._validate_request(request)

        # Process request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(response)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(self, request: Request, client_ip: str) -> bool:
        """Check if request exceeds rate limits."""
        if not self.redis_client:
            return True  # Skip rate limiting if Redis not available

        current_time = int(time.time())
        window_start = current_time - 60  # 1-minute window

        # Use client IP as rate limit key
        rate_limit_key = f"rate_limit:{client_ip}"

        # Remove old entries
        self.redis_client.zremrangebyscore(rate_limit_key, 0, window_start)

        # Count current requests
        current_requests = self.redis_client.zcard(rate_limit_key)

        # Check if rate limit exceeded
        if current_requests >= settings.RATE_LIMIT_PER_MINUTE:
            return False

        # Add current request
        self.redis_client.zadd(rate_limit_key, {str(current_time): current_time})
        self.redis_client.expire(rate_limit_key, 60)

        return True

    async def _validate_request(self, request: Request) -> None:
        """Validate request for security issues."""
        # Check for suspicious patterns
        suspicious_patterns = [
            "<script",
            "javascript:",
            "onload=",
            "onerror=",
            "../",
            "..\\",
            "SELECT.*FROM",
            "INSERT.*INTO",
            "UPDATE.*SET",
            "DELETE.*FROM",
        ]

        # Check URL
        url_str = str(request.url).lower()
        for pattern in suspicious_patterns:
            if pattern in url_str:
                logger.warning(f"Suspicious pattern detected in URL: {pattern}")
                break

        # Check headers for suspicious content
        for header_name, header_value in request.headers.items():
            if any(pattern in header_value.lower() for pattern in suspicious_patterns):
                logger.warning(f"Suspicious pattern detected in header {header_name}: {pattern}")

        # Validate content type for POST/PUT requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type:
                logger.warning("Missing content-type header")

    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy - allow external CDNs for docs
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https: https://fastapi.tiangolo.com; "
            "font-src 'self' https://cdn.jsdelivr.net; "
            "connect-src 'self' https://cdn.jsdelivr.net; "
            "frame-ancestors 'none';"
        )
        # DEBUG: Allow CDN for Swagger UI
        print(f"DEBUG: CSP = {csp}")
        response.headers["Content-Security-Policy"] = csp

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        # HSTS (only in production with HTTPS)
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )