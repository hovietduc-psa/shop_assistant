"""
Security middleware for enterprise-grade API protection.
Integrates rate limiting, threat detection, and security monitoring.
"""

import time
import json
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

from app.services.enterprise_security import (
    EnterpriseSecurityManager, SecurityConfig, SecurityLevel, ThreatType
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
security = HTTPBearer(auto_error=False)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Enterprise security middleware for API protection."""

    def __init__(self, app, security_manager: Optional[EnterpriseSecurityManager] = None):
        super().__init__(app)
        self.security_manager = security_manager or EnterpriseSecurityManager()
        self._bypass_paths = {
            "/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico",
            "/static", "/metrics", "/monitoring/health"
        }

    async def dispatch(self, request: Request, call_next):
        """Process request through security pipeline."""
        # Skip security for certain paths
        if self._should_bypass_security(request):
            return await call_next(request)

        start_time = time.time()

        try:
            # Extract user information if available
            user_id = await self._extract_user_id(request)

            # Process through security systems
            security_result = await self.security_manager.process_request(request, user_id)

            # Handle security violations
            if not security_result["allowed"]:
                return self._create_security_response(
                    request,
                    security_result,
                    user_id
                )

            # Add security headers to response
            response = await call_next(request)
            self._add_security_headers(response, security_result)

            # Log request completion
            process_time = time.time() - start_time
            await self._log_request_completion(request, response, process_time, security_result)

            return response

        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # In case of security system errors, allow request but log the error
            response = await call_next(request)
            return response

    def _should_bypass_security(self, request: Request) -> bool:
        """Check if request should bypass security checks."""
        path = request.url.path

        # Bypass specific paths
        if any(path.startswith(bypass_path) for bypass_path in self._bypass_paths):
            return True

        # Bypass OPTIONS requests for CORS
        if request.method == "OPTIONS":
            return True

        return False

    async def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request if authenticated."""
        try:
            # Try to get from Authorization header
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # This would typically involve JWT validation
                # For now, return a placeholder
                return "authenticated_user"

            # Try to get from session cookie
            session_cookie = request.cookies.get("session")
            if session_cookie:
                # This would involve session validation
                return "session_user"

            return None
        except Exception as e:
            logger.debug(f"Failed to extract user ID: {e}")
            return None

    def _create_security_response(self, request: Request, security_result: Dict[str, Any], user_id: Optional[str]) -> JSONResponse:
        """Create response for security violations."""
        # Determine appropriate HTTP status
        if security_result.get("rate_limit_info", {}).get("allowed") is False:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
            error_type = "rate_limit_exceeded"
        else:
            status_code = status.HTTP_403_FORBIDDEN
            error_type = "security_violation"

        # Prepare response data
        response_data = {
            "error": "Security violation detected",
            "error_type": error_type,
            "timestamp": time.time(),
            "request_id": f"req_{int(time.time())}_{hash(str(time.time())) % 10000:04d}",
            "details": {
                "threats_detected": security_result.get("threats_detected", 0),
                "security_events_count": len(security_result.get("security_events", []))
            }
        }

        # Add rate limiting information if applicable
        if "rate_limit_info" in security_result:
            rate_info = security_result["rate_limit_info"]
            response_data["rate_limit"] = {
                "limit": rate_info.get("limit"),
                "remaining": rate_info.get("remaining"),
                "reset_time": rate_info.get("reset_time")
            }

        # Log security violation
        logger.warning(
            f"Security violation: {error_type} from {self._get_client_ip(request)} "
            f"on {request.method} {request.url.path} "
            f"(Threats: {security_result.get('threats_detected', 0)})"
        )

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={
                "X-Security-Block": "true",
                "X-Content-Type-Options": "nosniff"
            }
        )

    def _add_security_headers(self, response: Response, security_result: Dict[str, Any]):
        """Add security headers to response."""
        # Standard security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Security metrics headers
        if security_result.get("threats_detected", 0) > 0:
            response.headers["X-Security-Threats"] = str(security_result["threats_detected"])

        # Rate limiting headers
        if "rate_limit_info" in security_result:
            rate_info = security_result["rate_limit_info"]
            if "limit" in rate_info:
                response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            if "remaining" in rate_info:
                response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            if "reset_time" in rate_info:
                response.headers["X-RateLimit-Reset"] = str(int(rate_info["reset_time"]))

        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

    async def _log_request_completion(self, request: Request, response: Response, process_time: float, security_result: Dict[str, Any]):
        """Log request completion with security information."""
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": round(process_time, 4),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "threats_detected": security_result.get("threats_detected", 0),
            "security_events": len(security_result.get("security_events", [])),
            "rate_limited": not security_result.get("rate_limit_info", {}).get("allowed", True)
        }

        # Log at appropriate level based on security events
        if security_result.get("threats_detected", 0) > 0:
            logger.info(f"Request completed with security events: {json.dumps(log_data)}")
        elif process_time > 1.0:  # Slow requests
            logger.warning(f"Slow request detected: {json.dumps(log_data)}")
        else:
            logger.debug(f"Request completed: {json.dumps(log_data)}")

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        return request.client.host if request.client else "unknown"


class SecurityAuditMiddleware(BaseHTTPMiddleware):
    """Middleware for security auditing and monitoring."""

    def __init__(self, app, security_manager: Optional[EnterpriseSecurityManager] = None):
        super().__init__(app)
        self.security_manager = security_manager or EnterpriseSecurityManager()

    async def dispatch(self, request: Request, call_next):
        """Process request with security auditing."""
        start_time = time.time()

        # Collect request information
        request_info = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "timestamp": time.time()
        }

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Prepare audit log
        audit_log = {
            "request": request_info,
            "response": {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "process_time": round(process_time, 4)
            },
            "security": await self._collect_security_metrics(request, response)
        }

        # Log audit information
        await self._log_security_audit(audit_log)

        return response

    async def _collect_security_metrics(self, request: Request, response: Response) -> Dict[str, Any]:
        """Collect security-related metrics."""
        return {
            "rate_limit_headers": {
                "limit": response.headers.get("X-RateLimit-Limit"),
                "remaining": response.headers.get("X-RateLimit-Remaining"),
                "reset": response.headers.get("X-RateLimit-Reset")
            },
            "security_headers": {
                "threats_detected": response.headers.get("X-Security-Threats"),
                "block": response.headers.get("X-Security-Block")
            },
            "security_score": self._calculate_security_score(request, response)
        }

    def _calculate_security_score(self, request: Request, response: Response) -> float:
        """Calculate security score for the request."""
        score = 1.0  # Start with perfect score

        # Deduct for security threats
        threats = response.headers.get("X-Security-Threats")
        if threats:
            score -= min(0.5, int(threats) * 0.1)

        # Deduct for rate limiting
        if response.headers.get("X-Security-Block"):
            score -= 0.3

        # Deduct for slow responses (potential DoS)
        if hasattr(response, 'headers') and 'X-Process-Time' in response.headers:
            try:
                process_time = float(response.headers['X-Process-Time'])
                if process_time > 2.0:
                    score -= 0.2
            except (ValueError, TypeError):
                pass

        return max(0.0, score)

    async def _log_security_audit(self, audit_log: Dict[str, Any]):
        """Log security audit information."""
        try:
            # Log to application logger
            logger.info(f"Security audit: {json.dumps(audit_log, default=str)}")

            # Store in Redis for analytics if available
            if hasattr(self.security_manager, 'threat_detector') and self.security_manager.threat_detector.redis_client:
                audit_key = f"security_audit:{int(time.time())}"
                await self.security_manager.threat_detector.redis_client.setex(
                    audit_key,
                    86400,  # 24 hours
                    json.dumps(audit_log, default=str)
                )

        except Exception as e:
            logger.error(f"Failed to log security audit: {e}")

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


# Security dependency for FastAPI routes
async def get_current_user_security(credentials: Optional[HTTPAuthorizationCredentials] = security) -> Optional[Dict[str, Any]]:
    """Security dependency for user authentication."""
    if credentials is None:
        return None

    try:
        # This would typically validate JWT token
        # For now, return basic user info
        return {
            "user_id": "authenticated_user",
            "is_authenticated": True,
            "is_admin": False,
            "permissions": ["read", "write"]
        }
    except Exception as e:
        logger.debug(f"Authentication failed: {e}")
        return None


async def require_admin_user(current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Security dependency requiring admin privileges."""
    if current_user is None or not current_user.get("is_authenticated"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user


# Factory function for creating security middleware
def create_security_middleware(
    app,
    config: Optional[SecurityConfig] = None,
    enable_audit: bool = True
) -> list:
    """Create security middleware stack."""
    security_manager = EnterpriseSecurityManager(config)

    middleware_stack = []

    # Add main security middleware
    security_middleware = SecurityMiddleware(app, security_manager)
    middleware_stack.append(security_middleware)

    # Add audit middleware if enabled
    if enable_audit:
        audit_middleware = SecurityAuditMiddleware(app, security_manager)
        middleware_stack.append(audit_middleware)

    return middleware_stack, security_manager