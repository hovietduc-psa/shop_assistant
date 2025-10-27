"""
Enterprise-grade API rate limiting and security system for Shop Assistant AI.
Implements advanced rate limiting, threat detection, and security monitoring.
"""

import asyncio
import time
import hashlib
import hmac
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import redis.asyncio as redis
from fastapi import Request, HTTPException, status
import logging


def get_remote_address(request: Request) -> str:
    """Get remote address from request."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"

logger = logging.getLogger(__name__)


class SecurityLevel(Enum):
    """Security severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Types of security threats."""
    BRUTE_FORCE = "brute_force"
    DDoS = "ddos"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    RATE_LIMIT_ABUSE = "rate_limit_abuse"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"


@dataclass
class SecurityEvent:
    """Security event data structure."""
    event_id: str
    threat_type: ThreatType
    security_level: SecurityLevel
    source_ip: str
    user_agent: str
    endpoint: str
    timestamp: datetime
    details: Dict[str, Any]
    blocked: bool = False
    risk_score: float = 0.0


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    name: str
    requests_per_window: int
    window_seconds: int
    block_duration_seconds: int = 300
    scope: str = "ip"  # ip, user, endpoint, global
    priority: int = 0
    conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """Security system configuration."""
    enabled_features: Set[str] = field(default_factory=lambda: {
        "rate_limiting", "threat_detection", "ip_whitelist",
        "request_validation", "security_monitoring"
    })
    redis_url: str = "redis://localhost:6379/0"
    default_rate_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(
        name="default",
        requests_per_window=100,
        window_seconds=60,
        block_duration_seconds=300
    ))
    authenticated_rate_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(
        name="authenticated",
        requests_per_window=1000,
        window_seconds=60,
        block_duration_seconds=600
    ))
    admin_rate_limit: RateLimitRule = field(default_factory=lambda: RateLimitRule(
        name="admin",
        requests_per_window=5000,
        window_seconds=60,
        block_duration_seconds=900
    ))
    ip_whitelist: Set[str] = field(default_factory=set)
    ip_blacklist: Set[str] = field(default_factory=set)
    threat_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "brute_force": 0.8,
        "ddos": 0.9,
        "sql_injection": 0.95,
        "xss": 0.9,
        "suspicious_pattern": 0.7,
        "rate_limit_abuse": 0.6
    })


class EnterpriseRateLimiter:
    """Enterprise-grade rate limiting system."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.custom_rules: Dict[str, RateLimitRule] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.blocked_users: Dict[str, datetime] = {}

    async def initialize(self):
        """Initialize Redis connection and load rules."""
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            await self.redis_client.ping()
            logger.info("Enterprise rate limiter initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory rate limiting: {e}")
            self.redis_client = None

    async def check_rate_limit(self, request: Request, user_id: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Check if request exceeds rate limits."""
        if not self._is_feature_enabled("rate_limiting"):
            return True, {"allowed": True, "remaining": float('inf')}

        source_ip = self._get_client_ip(request)
        endpoint = request.url.path

        # Check if IP is blocked
        if await self._is_ip_blocked(source_ip):
            return False, {"allowed": False, "reason": "IP blocked"}

        # Check if user is blocked
        if user_id and await self._is_user_blocked(user_id):
            return False, {"allowed": False, "reason": "User blocked"}

        # Determine applicable rate limit rule
        rule = await self._get_applicable_rule(request, user_id)

        # Check rate limit based on rule scope
        if rule.scope == "ip":
            return await self._check_ip_rate_limit(source_ip, rule, endpoint)
        elif rule.scope == "user" and user_id:
            return await self._check_user_rate_limit(user_id, rule, endpoint)
        elif rule.scope == "endpoint":
            return await self._check_endpoint_rate_limit(endpoint, rule)
        else:  # global
            return await self._check_global_rate_limit(rule)

    async def _check_ip_rate_limit(self, ip: str, rule: RateLimitRule, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """Check IP-based rate limiting."""
        key = f"rate_limit:ip:{ip}:{endpoint}"
        return await self._check_redis_rate_limit(key, rule)

    async def _check_user_rate_limit(self, user_id: str, rule: RateLimitRule, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """Check user-based rate limiting."""
        key = f"rate_limit:user:{user_id}:{endpoint}"
        return await self._check_redis_rate_limit(key, rule)

    async def _check_endpoint_rate_limit(self, endpoint: str, rule: RateLimitRule) -> Tuple[bool, Dict[str, Any]]:
        """Check endpoint-based rate limiting."""
        key = f"rate_limit:endpoint:{endpoint}"
        return await self._check_redis_rate_limit(key, rule)

    async def _check_global_rate_limit(self, rule: RateLimitRule) -> Tuple[bool, Dict[str, Any]]:
        """Check global rate limiting."""
        key = "rate_limit:global"
        return await self._check_redis_rate_limit(key, rule)

    async def _check_redis_rate_limit(self, key: str, rule: RateLimitRule) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using Redis sliding window."""
        if self.redis_client:
            return await self._check_redis_sliding_window(key, rule)
        else:
            return await self._check_memory_sliding_window(key, rule)

    async def _check_redis_sliding_window(self, key: str, rule: RateLimitRule) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limit using Redis sliding window algorithm."""
        now = time.time()
        window_start = now - rule.window_seconds

        try:
            # Remove old entries
            await self.redis_client.zremrangebyscore(key, 0, window_start)

            # Count current requests
            current_requests = await self.redis_client.zcard(key)

            if current_requests >= rule.requests_per_window:
                # Add block entry
                block_key = f"blocked:{key}"
                await self.redis_client.setex(
                    block_key,
                    rule.block_duration_seconds,
                    datetime.utcnow().isoformat()
                )

                return False, {
                    "allowed": False,
                    "remaining": 0,
                    "reset_time": now + rule.window_seconds,
                    "limit": rule.requests_per_window
                }

            # Add current request
            await self.redis_client.zadd(key, {str(now): now})
            await self.redis_client.expire(key, rule.window_seconds)

            return True, {
                "allowed": True,
                "remaining": rule.requests_per_window - current_requests - 1,
                "reset_time": now + rule.window_seconds,
                "limit": rule.requests_per_window
            }

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return True, {"allowed": True, "remaining": float('inf')}

    async def _check_memory_sliding_window(self, key: str, rule: RateLimitRule) -> Tuple[bool, Dict[str, Any]]:
        """Fallback in-memory rate limiting."""
        now = time.time()

        # Simple in-memory tracking (less accurate but functional)
        if not hasattr(self, '_memory_store'):
            self._memory_store = {}

        if key not in self._memory_store:
            self._memory_store[key] = []

        # Remove old entries
        self._memory_store[key] = [
            timestamp for timestamp in self._memory_store[key]
            if now - timestamp < rule.window_seconds
        ]

        if len(self._memory_store[key]) >= rule.requests_per_window:
            return False, {
                "allowed": False,
                "remaining": 0,
                "reset_time": now + rule.window_seconds,
                "limit": rule.requests_per_window
            }

        self._memory_store[key].append(now)

        return True, {
            "allowed": True,
            "remaining": rule.requests_per_window - len(self._memory_store[key]),
            "reset_time": now + rule.window_seconds,
            "limit": rule.requests_per_window
        }

    async def _get_applicable_rule(self, request: Request, user_id: Optional[str]) -> RateLimitRule:
        """Determine which rate limit rule applies to the request."""
        endpoint = request.url.path

        # Check custom rules first
        for rule_name, rule in self.custom_rules.items():
            if self._rule_matches_request(rule, request, user_id):
                return rule

        # Check if admin endpoint
        if endpoint.startswith("/admin") or endpoint.startswith("/dashboard"):
            return self.config.admin_rate_limit

        # Check if authenticated user
        if user_id:
            return self.config.authenticated_rate_limit

        return self.config.default_rate_limit

    def _rule_matches_request(self, rule: RateLimitRule, request: Request, user_id: Optional[str]) -> bool:
        """Check if a rule matches the current request."""
        if not rule.conditions:
            return False

        # Check endpoint patterns
        if "endpoints" in rule.conditions:
            endpoint = request.url.path
            if not any(pattern in endpoint for pattern in rule.conditions["endpoints"]):
                return False

        # Check user roles
        if "user_roles" in rule.conditions and user_id:
            # This would integrate with user role system
            pass

        return True

    async def _is_ip_blocked(self, ip: str) -> bool:
        """Check if IP address is blocked."""
        # Check static blacklist
        if ip in self.config.ip_blacklist:
            return True

        # Check dynamic blocks
        if self.redis_client:
            block_key = f"blocked_ip:{ip}"
            return await self.redis_client.exists(block_key)
        else:
            return ip in self.blocked_ips and datetime.utcnow() < self.blocked_ips[ip]

    async def _is_user_blocked(self, user_id: str) -> bool:
        """Check if user is blocked."""
        if self.redis_client:
            block_key = f"blocked_user:{user_id}"
            return await self.redis_client.exists(block_key)
        else:
            return user_id in self.blocked_users and datetime.utcnow() < self.blocked_users[user_id]

    async def block_ip(self, ip: str, duration_seconds: int = 3600, reason: str = "Security violation"):
        """Block an IP address."""
        if self.redis_client:
            block_key = f"blocked_ip:{ip}"
            await self.redis_client.setex(
                block_key,
                duration_seconds,
                json.dumps({"reason": reason, "timestamp": datetime.utcnow().isoformat()})
            )
        else:
            self.blocked_ips[ip] = datetime.utcnow() + timedelta(seconds=duration_seconds)

        logger.warning(f"IP {ip} blocked for {duration_seconds} seconds. Reason: {reason}")

    async def block_user(self, user_id: str, duration_seconds: int = 3600, reason: str = "Security violation"):
        """Block a user."""
        if self.redis_client:
            block_key = f"blocked_user:{user_id}"
            await self.redis_client.setex(
                block_key,
                duration_seconds,
                json.dumps({"reason": reason, "timestamp": datetime.utcnow().isoformat()})
            )
        else:
            self.blocked_users[user_id] = datetime.utcnow() + timedelta(seconds=duration_seconds)

        logger.warning(f"User {user_id} blocked for {duration_seconds} seconds. Reason: {reason}")

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address considering proxies."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return get_remote_address(request)

    def _is_feature_enabled(self, feature: str) -> bool:
        """Check if a security feature is enabled."""
        return feature in self.config.enabled_features

    async def add_custom_rule(self, rule: RateLimitRule):
        """Add a custom rate limiting rule."""
        self.custom_rules[rule.name] = rule
        logger.info(f"Added custom rate limit rule: {rule.name}")

    async def remove_custom_rule(self, rule_name: str):
        """Remove a custom rate limiting rule."""
        if rule_name in self.custom_rules:
            del self.custom_rules[rule_name]
            logger.info(f"Removed custom rate limit rule: {rule_name}")

    async def get_rate_limit_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        stats = {
            "active_rules": len(self.custom_rules) + 3,  # +3 for default rules
            "blocked_ips": len(self.config.ip_blacklist),
            "memory_store_size": len(getattr(self, '_memory_store', {})),
            "custom_rules": list(self.custom_rules.keys()),
            "enabled_features": list(self.config.enabled_features)
        }

        if self.redis_client:
            try:
                # Get Redis stats
                blocked_ips_count = len(await self.redis_client.keys("blocked_ip:*"))
                blocked_users_count = len(await self.redis_client.keys("blocked_user:*"))
                rate_limit_keys = len(await self.redis_client.keys("rate_limit:*"))

                stats.update({
                    "redis_connected": True,
                    "blocked_ips_redis": blocked_ips_count,
                    "blocked_users_redis": blocked_users_count,
                    "active_rate_limits": rate_limit_keys
                })
            except Exception as e:
                stats["redis_connected"] = False
                stats["redis_error"] = str(e)
        else:
            stats["redis_connected"] = False

        return stats


class ThreatDetectionSystem:
    """Advanced threat detection system."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.security_events: List[SecurityEvent] = []
        self.threat_patterns: Dict[str, Any] = {}
        self._initialize_threat_patterns()

    async def initialize(self):
        """Initialize threat detection system."""
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            await self.redis_client.ping()
            logger.info("Threat detection system initialized with Redis")
        except Exception as e:
            logger.warning(f"Redis unavailable for threat detection: {e}")
            self.redis_client = None

    def _initialize_threat_patterns(self):
        """Initialize threat detection patterns."""
        self.threat_patterns = {
            "sql_injection": [
                "union select", "drop table", "insert into", "delete from",
                "update set", "exec(", "script>", "javascript:",
                "1=1", "1 = 1", "or 1=1", "and 1=1"
            ],
            "xss": [
                "<script", "</script>", "javascript:", "onerror=", "onload=",
                "alert(", "document.cookie", "window.location", "eval("
            ],
            "path_traversal": [
                "../", "..\\", "%2e%2e%2f", "%2e%2e\\", "..%2f", "..%5c"
            ],
            "command_injection": [
                ";", "|", "&", "&&", "`", "$(", "${", "nc ", "netcat",
                "wget ", "curl ", "ping ", "whoami"
            ],
            "suspicious_user_agents": [
                "sqlmap", "nikto", "dirb", "nmap", "masscan", "zap",
                "burp", "acunetix", "appscan", "arachni"
            ]
        }

    async def analyze_request(self, request: Request, user_id: Optional[str] = None) -> List[SecurityEvent]:
        """Analyze request for security threats."""
        events = []

        if not self._is_feature_enabled("threat_detection"):
            return events

        source_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        endpoint = str(request.url.path)
        method = request.method

        # Analyze various threat vectors
        events.extend(await self._check_sql_injection(request, source_ip, user_agent, endpoint))
        events.extend(await self._check_xss(request, source_ip, user_agent, endpoint))
        events.extend(await self._check_path_traversal(request, source_ip, user_agent, endpoint))
        events.extend(await self._check_command_injection(request, source_ip, user_agent, endpoint))
        events.extend(await self._check_brute_force(request, source_ip, user_agent, endpoint, user_id))
        events.extend(await self._check_ddos_pattern(request, source_ip, user_agent, endpoint))
        events.extend(await self._check_suspicious_user_agent(source_ip, user_agent, endpoint))
        events.extend(await self._check_anomalous_behavior(request, source_ip, user_agent, endpoint, user_id))

        # Store events and take action if needed
        for event in events:
            await self._handle_security_event(event)

        return events

    async def _check_sql_injection(self, request: Request, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for SQL injection patterns."""
        events = []

        # Check query parameters
        for param_name, param_value in request.query_params.items():
            if await self._contains_threat_pattern(param_value.lower(), "sql_injection"):
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    threat_type=ThreatType.SQL_INJECTION,
                    security_level=SecurityLevel.HIGH,
                    source_ip=ip,
                    user_agent=user_agent,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow(),
                    details={"parameter": param_name, "value": param_value[:100]},
                    risk_score=0.9
                ))

        # Check form data if available
        if hasattr(request, '_form') and request._form:
            for field_name, field_value in request._form.items():
                if isinstance(field_value, str) and await self._contains_threat_pattern(field_value.lower(), "sql_injection"):
                    events.append(SecurityEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.SQL_INJECTION,
                        security_level=SecurityLevel.HIGH,
                        source_ip=ip,
                        user_agent=user_agent,
                        endpoint=endpoint,
                        timestamp=datetime.utcnow(),
                        details={"form_field": field_name, "value": field_value[:100]},
                        risk_score=0.9
                    ))

        return events

    async def _check_xss(self, request: Request, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for XSS patterns."""
        events = []

        # Check query parameters
        for param_name, param_value in request.query_params.items():
            if await self._contains_threat_pattern(param_value.lower(), "xss"):
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    threat_type=ThreatType.XSS,
                    security_level=SecurityLevel.HIGH,
                    source_ip=ip,
                    user_agent=user_agent,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow(),
                    details={"parameter": param_name, "value": param_value[:100]},
                    risk_score=0.85
                ))

        return events

    async def _check_path_traversal(self, request: Request, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for path traversal patterns."""
        events = []

        # Check URL path
        if await self._contains_threat_pattern(endpoint.lower(), "path_traversal"):
            events.append(SecurityEvent(
                event_id=self._generate_event_id(),
                threat_type=ThreatType.SUSPICIOUS_PATTERN,
                security_level=SecurityLevel.MEDIUM,
                source_ip=ip,
                user_agent=user_agent,
                endpoint=endpoint,
                timestamp=datetime.utcnow(),
                details={"type": "path_traversal"},
                risk_score=0.7
            ))

        return events

    async def _check_command_injection(self, request: Request, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for command injection patterns."""
        events = []

        # Check query parameters
        for param_name, param_value in request.query_params.items():
            if await self._contains_threat_pattern(param_value.lower(), "command_injection"):
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    threat_type=ThreatType.SUSPICIOUS_PATTERN,
                    security_level=SecurityLevel.HIGH,
                    source_ip=ip,
                    user_agent=user_agent,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow(),
                    details={"parameter": param_name, "value": param_value[:100]},
                    risk_score=0.8
                ))

        return events

    async def _check_brute_force(self, request: Request, ip: str, user_agent: str, endpoint: str, user_id: Optional[str]) -> List[SecurityEvent]:
        """Check for brute force attack patterns."""
        events = []

        # Focus on authentication endpoints
        if not any(auth_path in endpoint for auth_path in ["/login", "/auth", "/signin", "/token"]):
            return events

        key = f"auth_attempts:{ip}"

        if self.redis_client:
            try:
                # Get recent attempts
                now = time.time()
                window_start = now - 300  # 5 minutes
                await self.redis_client.zremrangebyscore(key, 0, window_start)
                attempts = await self.redis_client.zcard(key)

                # Add current attempt
                await self.redis_client.zadd(key, {str(now): now})
                await self.redis_client.expire(key, 300)

                # Check threshold
                if attempts >= 10:  # 10 attempts in 5 minutes
                    events.append(SecurityEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.BRUTE_FORCE,
                        security_level=SecurityLevel.HIGH,
                        source_ip=ip,
                        user_agent=user_agent,
                        endpoint=endpoint,
                        timestamp=datetime.utcnow(),
                        details={"attempts_5min": attempts, "user_id": user_id},
                        risk_score=0.8
                    ))
            except Exception as e:
                logger.error(f"Brute force detection error: {e}")

        return events

    async def _check_ddos_pattern(self, request: Request, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for DDoS attack patterns."""
        events = []

        key = f"request_rate:{ip}"

        if self.redis_client:
            try:
                # Get recent requests
                now = time.time()
                window_start = now - 60  # 1 minute
                await self.redis_client.zremrangebyscore(key, 0, window_start)
                requests = await self.redis_client.zcard(key)

                # Add current request
                await self.redis_client.zadd(key, {str(now): now})
                await self.redis_client.expire(key, 60)

                # Check threshold (100 requests per minute)
                if requests >= 100:
                    events.append(SecurityEvent(
                        event_id=self._generate_event_id(),
                        threat_type=ThreatType.DDoS,
                        security_level=SecurityLevel.CRITICAL,
                        source_ip=ip,
                        user_agent=user_agent,
                        endpoint=endpoint,
                        timestamp=datetime.utcnow(),
                        details={"requests_per_minute": requests},
                        risk_score=0.95
                    ))
            except Exception as e:
                logger.error(f"DDoS detection error: {e}")

        return events

    async def _check_suspicious_user_agent(self, ip: str, user_agent: str, endpoint: str) -> List[SecurityEvent]:
        """Check for suspicious user agents."""
        events = []

        user_agent_lower = user_agent.lower()

        for suspicious_ua in self.threat_patterns["suspicious_user_agents"]:
            if suspicious_ua in user_agent_lower:
                events.append(SecurityEvent(
                    event_id=self._generate_event_id(),
                    threat_type=ThreatType.SUSPICIOUS_PATTERN,
                    security_level=SecurityLevel.MEDIUM,
                    source_ip=ip,
                    user_agent=user_agent,
                    endpoint=endpoint,
                    timestamp=datetime.utcnow(),
                    details={"suspicious_pattern": suspicious_ua},
                    risk_score=0.6
                ))
                break

        return events

    async def _check_anomalous_behavior(self, request: Request, ip: str, user_agent: str, endpoint: str, user_id: Optional[str]) -> List[SecurityEvent]:
        """Check for anomalous behavior patterns."""
        events = []

        # Check for unusual endpoint access patterns
        if user_id:
            key = f"user_endpoints:{user_id}"

            if self.redis_client:
                try:
                    # Get user's endpoint history
                    endpoints = await self.redis_client.smembers(key)

                    # Add current endpoint
                    await self.redis_client.sadd(key, endpoint)
                    await self.redis_client.expire(key, 86400)  # 24 hours

                    # Check if user is accessing many different endpoints (potential scraping)
                    if len(endpoints) > 50:  # More than 50 different endpoints in 24 hours
                        events.append(SecurityEvent(
                            event_id=self._generate_event_id(),
                            threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                            security_level=SecurityLevel.MEDIUM,
                            source_ip=ip,
                            user_agent=user_agent,
                            endpoint=endpoint,
                            timestamp=datetime.utcnow(),
                            details={"unique_endpoints_24h": len(endpoints), "user_id": user_id},
                            risk_score=0.5
                        ))
                except Exception as e:
                    logger.error(f"Anomaly detection error: {e}")

        return events

    async def _contains_threat_pattern(self, text: str, threat_type: str) -> bool:
        """Check if text contains threat patterns."""
        if threat_type not in self.threat_patterns:
            return False

        patterns = self.threat_patterns[threat_type]
        return any(pattern in text for pattern in patterns)

    async def _handle_security_event(self, event: SecurityEvent):
        """Handle security event (logging, blocking, etc.)."""
        # Store event
        self.security_events.append(event)

        # Log event
        log_level = {
            SecurityLevel.LOW: logging.INFO,
            SecurityLevel.MEDIUM: logging.WARNING,
            SecurityLevel.HIGH: logging.ERROR,
            SecurityLevel.CRITICAL: logging.CRITICAL
        }.get(event.security_level, logging.INFO)

        logger.log(
            log_level,
            f"Security Event: {event.threat_type.value} from {event.source_ip} on {event.endpoint} "
            f"(Risk Score: {event.risk_score})"
        )

        # Store in Redis for analytics
        if self.redis_client:
            try:
                event_key = f"security_event:{event.event_id}"
                await self.redis_client.setex(
                    event_key,
                    86400,  # 24 hours
                    json.dumps({
                        "threat_type": event.threat_type.value,
                        "security_level": event.security_level.value,
                        "source_ip": event.source_ip,
                        "endpoint": event.endpoint,
                        "timestamp": event.timestamp.isoformat(),
                        "risk_score": event.risk_score,
                        "details": event.details
                    })
                )
            except Exception as e:
                logger.error(f"Failed to store security event: {e}")

        # Auto-block for high-risk events
        threshold = self.config.threat_thresholds.get(event.threat_type.value, 0.8)
        if event.risk_score >= threshold:
            event.blocked = True
            # This would trigger actual blocking in the middleware

    def _generate_event_id(self) -> str:
        """Generate unique security event ID."""
        return f"sec_{int(time.time())}_{hash(str(time.time() + time.time_ns())) % 10000:04d}"

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return get_remote_address(request)

    def _is_feature_enabled(self, feature: str) -> bool:
        """Check if a security feature is enabled."""
        return feature in self.config.enabled_features

    async def get_security_stats(self) -> Dict[str, Any]:
        """Get security and threat detection statistics."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)

        # Filter events from last 24 hours
        recent_events = [
            event for event in self.security_events
            if event.timestamp > last_24h
        ]

        # Count by threat type
        threat_counts = {}
        level_counts = {}
        total_risk_score = 0

        for event in recent_events:
            threat_counts[event.threat_type.value] = threat_counts.get(event.threat_type.value, 0) + 1
            level_counts[event.security_level.value] = level_counts.get(event.security_level.value, 0) + 1
            total_risk_score += event.risk_score

        return {
            "total_events_24h": len(recent_events),
            "events_by_threat_type": threat_counts,
            "events_by_security_level": level_counts,
            "average_risk_score": total_risk_score / len(recent_events) if recent_events else 0,
            "blocked_events": sum(1 for event in recent_events if event.blocked),
            "enabled_features": list(self.config.enabled_features),
            "threat_patterns_loaded": len(self.threat_patterns),
            "redis_connected": self.redis_client is not None
        }


class EnterpriseSecurityManager:
    """Main security management system."""

    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.rate_limiter = EnterpriseRateLimiter(self.config)
        self.threat_detector = ThreatDetectionSystem(self.config)
        self._initialized = False

    async def initialize(self):
        """Initialize all security components."""
        await self.rate_limiter.initialize()
        await self.threat_detector.initialize()
        self._initialized = True
        logger.info("Enterprise security manager initialized")

    async def process_request(self, request: Request, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Process request through all security systems."""
        if not self._initialized:
            await self.initialize()

        result = {
            "allowed": True,
            "security_events": [],
            "rate_limit_info": {},
            "threats_detected": 0
        }

        # Rate limiting check
        rate_allowed, rate_info = await self.rate_limiter.check_rate_limit(request, user_id)
        result["allowed"] = result["allowed"] and rate_allowed
        result["rate_limit_info"] = rate_info

        if not rate_allowed:
            result["security_events"].append({
                "type": "rate_limit_exceeded",
                "message": rate_info.get("reason", "Rate limit exceeded"),
                "severity": "high"
            })

        # Threat detection
        threat_events = await self.threat_detector.analyze_request(request, user_id)
        result["security_events"].extend([
            {
                "type": event.threat_type.value,
                "security_level": event.security_level.value,
                "risk_score": event.risk_score,
                "blocked": event.blocked,
                "details": event.details
            }
            for event in threat_events
        ])
        result["threats_detected"] = len(threat_events)

        # Block request if high-risk threats detected
        high_risk_events = [e for e in threat_events if e.risk_score >= 0.8 or e.blocked]
        if high_risk_events:
            result["allowed"] = False
            result["block_reason"] = f"High-risk threats detected: {len(high_risk_events)}"

        return result

    async def get_security_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive security dashboard data."""
        rate_stats = await self.rate_limiter.get_rate_limit_stats()
        threat_stats = await self.threat_detector.get_security_stats()

        return {
            "status": "active" if self._initialized else "inactive",
            "configuration": {
                "enabled_features": list(self.config.enabled_features),
                "ip_whitelist_size": len(self.config.ip_whitelist),
                "ip_blacklist_size": len(self.config.ip_blacklist),
                "custom_rate_limit_rules": len(self.rate_limiter.custom_rules)
            },
            "rate_limiting": rate_stats,
            "threat_detection": threat_stats,
            "performance": {
                "redis_connected": rate_stats.get("redis_connected", False) and threat_stats.get("redis_connected", False)
            }
        }