"""
API health check and monitoring endpoints.
"""

import asyncio
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis
from loguru import logger

from app.db.session import get_db, get_redis_client
from app.core.config import settings
from app.services.llm import LLMService
from app.services.nlu import NLUService
from app.services.embedding import EmbeddingService
from app.services.dialogue import DialogueManager
from app.services.memory import ConversationMemoryManager
from app.services.quality import ConversationQualityAssessor


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Individual health check result."""
    name: str
    status: HealthStatus
    response_time: float
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class SystemHealthReport:
    """Complete system health report."""
    overall_status: HealthStatus
    checks: List[HealthCheckResult]
    uptime_seconds: float
    version: str
    timestamp: datetime
    system_info: Dict[str, Any]


class HealthChecker:
    """System health checking utility."""

    def __init__(self):
        self.start_time = time.time()
        self.llm_service = LLMService()
        self.nlu_service = NLUService()
        self.embedding_service = EmbeddingService()
        self.dialogue_manager = DialogueManager()
        self.memory_manager = ConversationMemoryManager()
        self.quality_assessor = ConversationQualityAssessor()

    def check_database_health(self, db: Session) -> HealthCheckResult:
        """Check database connectivity and performance."""
        start_time = time.time()

        try:
            # Test basic connectivity
            result = db.execute(text("SELECT 1"))
            db_result = result.scalar()
            logger.info(f"Database health check result: {db_result}")

            if db_result != 1:
                return HealthCheckResult(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    response_time=time.time() - start_time,
                    message="Database query returned unexpected result",
                    details={"expected": 1, "actual": db_result}
                )

            # Test table access
            try:
                table_result = db.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
                table_count = table_result.scalar()
            except Exception:
                table_count = 0

            # Check connection pool
            pool_status = {
                "size": db.bind.pool.size() if hasattr(db.bind, 'pool') else "unknown",
                "checked_in": db.bind.pool.checkedin() if hasattr(db.bind, 'pool') else "unknown",
                "checked_out": db.bind.pool.checkedout() if hasattr(db.bind, 'pool') else "unknown"
            }

            response_time = time.time() - start_time

            # Determine status based on response time
            if response_time > 5.0:
                status = HealthStatus.DEGRADED
                message = "Database response time is slow"
            elif response_time > 10.0:
                status = HealthStatus.UNHEALTHY
                message = "Database response time is critical"
            else:
                status = HealthStatus.HEALTHY
                message = "Database is operating normally"

            return HealthCheckResult(
                name="database",
                status=status,
                response_time=response_time,
                message=message,
                details={
                    "table_count": table_count,
                    "pool_status": pool_status,
                    "connection_string": str(db.bind.url).replace(db.bind.url.password or "", "***") if db.bind.url.password else str(db.bind.url)
                }
            )

        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"Database connection failed: {str(e)}",
                details={"error": str(e)}
            )

    def check_redis_health(self, redis_client: redis.Redis) -> HealthCheckResult:
        """Check Redis connectivity and performance."""
        start_time = time.time()

        try:
            # Test basic connectivity
            redis_client.ping()
            logger.info("Redis ping successful")

            # Test read/write performance
            test_key = f"health_check_{int(time.time())}"
            test_value = "test_value"

            # Write test
            write_start = time.time()
            redis_client.set(test_key, test_value, ex=60)
            write_time = time.time() - write_start

            # Read test
            read_start = time.time()
            read_value = redis_client.get(test_key)
            read_time = time.time() - read_start
            logger.info(f"Redis read/write test: expected={test_value}, actual={read_value}")

            # Cleanup
            redis_client.delete(test_key)

            # Get Redis info
            info = redis_client.info()

            response_time = time.time() - start_time

            if read_value != test_value:
                return HealthCheckResult(
                    name="redis",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="Redis read/write test failed",
                    details={
                        "expected": test_value,
                        "actual": read_value if read_value else None
                    }
                )

            # Determine status based on response times
            if response_time > 1.0 or write_time > 0.5 or read_time > 0.5:
                status = HealthStatus.DEGRADED
                message = "Redis response time is slow"
            elif response_time > 2.0:
                status = HealthStatus.UNHEALTHY
                message = "Redis response time is critical"
            else:
                status = HealthStatus.HEALTHY
                message = "Redis is operating normally"

            return HealthCheckResult(
                name="redis",
                status=status,
                response_time=response_time,
                message=message,
                details={
                    "write_time": write_time,
                    "read_time": read_time,
                    "redis_info": {
                        "version": info.get("redis_version"),
                        "used_memory": info.get("used_memory_human"),
                        "connected_clients": info.get("connected_clients"),
                        "total_commands_processed": info.get("total_commands_processed")
                    }
                }
            )

        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"Redis connection failed: {str(e)}",
                details={"error": str(e)}
            )

    async def check_llm_service_health(self) -> HealthCheckResult:
        """Check LLM service availability and performance."""
        start_time = time.time()

        try:
            # Test LLM service with a simple request
            test_messages = [
                {"role": "user", "content": "Hello"}
            ]

            response = await self.llm_service.generate_response(
                messages=test_messages,
                temperature=0.1,
                max_tokens=10
            )

            response_time = time.time() - start_time

            if response and "choices" in response and len(response["choices"]) > 0:
                if response_time > 10.0:
                    status = HealthStatus.DEGRADED
                    message = "LLM service response is slow"
                elif response_time > 20.0:
                    status = HealthStatus.UNHEALTHY
                    message = "LLM service response is critical"
                else:
                    status = HealthStatus.HEALTHY
                    message = "LLM service is operating normally"

                return HealthCheckResult(
                    name="llm_service",
                    status=status,
                    response_time=response_time,
                    message=message,
                    details={
                        "model": settings.DEFAULT_LLM_MODEL,
                        "response_length": len(response["choices"][0]["message"]["content"]),
                        "usage": response.get("usage", {})
                    }
                )
            else:
                return HealthCheckResult(
                    name="llm_service",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="LLM service returned invalid response",
                    details={"response": response}
                )

        except Exception as e:
            return HealthCheckResult(
                name="llm_service",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"LLM service check failed: {str(e)}",
                details={"error": str(e)}
            )

    async def check_embedding_service_health(self) -> HealthCheckResult:
        """Check embedding service availability and performance."""
        start_time = time.time()

        try:
            # Test embedding service with a simple text
            test_text = "Hello world"

            embeddings = await self.embedding_service.generate_embeddings([test_text])

            response_time = time.time() - start_time

            if embeddings and len(embeddings) > 0:
                if response_time > 5.0:
                    status = HealthStatus.DEGRADED
                    message = "Embedding service response is slow"
                elif response_time > 10.0:
                    status = HealthStatus.UNHEALTHY
                    message = "Embedding service response is critical"
                else:
                    status = HealthStatus.HEALTHY
                    message = "Embedding service is operating normally"

                return HealthCheckResult(
                    name="embedding_service",
                    status=status,
                    response_time=response_time,
                    message=message,
                    details={
                        "model": settings.DEFAULT_EMBEDDING_MODEL,
                        "embedding_dimension": len(embeddings[0]) if embeddings[0] else 0,
                        "batch_size": len(embeddings)
                    }
                )
            else:
                return HealthCheckResult(
                    name="embedding_service",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="Embedding service returned invalid response",
                    details={"embeddings": embeddings}
                )

        except Exception as e:
            return HealthCheckResult(
                name="embedding_service",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"Embedding service check failed: {str(e)}",
                details={"error": str(e)}
            )

    async def check_nlu_service_health(self) -> HealthCheckResult:
        """Check NLU service availability and performance."""
        start_time = time.time()

        try:
            test_text = "I want to track my order"

            # Test intent classification
            intent_result = await self.nlu_service.classify_intent(test_text)

            # Test entity extraction
            entity_result = await self.nlu_service.extract_entities(test_text)

            # Test sentiment analysis
            sentiment_result = await self.nlu_service.analyze_sentiment(test_text)

            response_time = time.time() - start_time

            if intent_result and entity_result and sentiment_result:
                if response_time > 8.0:
                    status = HealthStatus.DEGRADED
                    message = "NLU service response is slow"
                elif response_time > 15.0:
                    status = HealthStatus.UNHEALTHY
                    message = "NLU service response is critical"
                else:
                    status = HealthStatus.HEALTHY
                    message = "NLU service is operating normally"

                return HealthCheckResult(
                    name="nlu_service",
                    status=status,
                    response_time=response_time,
                    message=message,
                    details={
                        "intent_classification": bool(intent_result.get("intent")),
                        "entity_extraction": bool(entity_result.get("entities")),
                        "sentiment_analysis": bool(sentiment_result.get("sentiment")),
                        "intent_confidence": intent_result.get("confidence", 0),
                        "sentiment_confidence": sentiment_result.get("confidence", 0)
                    }
                )
            else:
                return HealthCheckResult(
                    name="nlu_service",
                    status=HealthStatus.UNHEALTHY,
                    response_time=response_time,
                    message="NLU service returned incomplete response",
                    details={
                        "intent_result": intent_result,
                        "entity_result": entity_result,
                        "sentiment_result": sentiment_result
                    }
                )

        except Exception as e:
            return HealthCheckResult(
                name="nlu_service",
                status=HealthStatus.UNHEALTHY,
                response_time=time.time() - start_time,
                message=f"NLU service check failed: {str(e)}",
                details={"error": str(e)}
            )

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100

            # Process information
            process = psutil.Process()
            process_memory = process.memory_info()
            process_cpu = process.cpu_percent()

            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "usage_percent": memory_percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "usage_percent": round(disk_percent, 2)
                },
                "process": {
                    "pid": process.pid,
                    "memory_rss_mb": round(process_memory.rss / (1024**2), 2),
                    "memory_vms_mb": round(process_memory.vms / (1024**2), 2),
                    "cpu_percent": process_cpu,
                    "num_threads": process.num_threads(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {"error": str(e)}

    async def run_comprehensive_health_check(
        self,
        db: Session,
        redis_client: redis.Redis,
        include_system_checks: bool = True
    ) -> SystemHealthReport:
        """Run comprehensive health check of all system components."""
        checks = []

        # Database health check (sync call)
        db_check = self.check_database_health(db)
        checks.append(db_check)

        # Redis health check (sync call)
        redis_check = self.check_redis_health(redis_client)
        checks.append(redis_check)

        # LLM service health check
        llm_check = await self.check_llm_service_health()
        checks.append(llm_check)

        # Embedding service health check
        embedding_check = await self.check_embedding_service_health()
        checks.append(embedding_check)

        # NLU service health check
        nlu_check = await self.check_nlu_service_health()
        checks.append(nlu_check)

        # Determine overall status
        unhealthy_count = sum(1 for check in checks if check.status == HealthStatus.UNHEALTHY)
        degraded_count = sum(1 for check in checks if check.status == HealthStatus.DEGRADED)

        if unhealthy_count > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif degraded_count > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        # Get system information
        system_info = {}
        if include_system_checks:
            system_info = self.get_system_info()

        return SystemHealthReport(
            overall_status=overall_status,
            checks=checks,
            uptime_seconds=time.time() - self.start_time,
            version=settings.VERSION,
            timestamp=datetime.utcnow(),
            system_info=system_info
        )


router = APIRouter()
health_checker = HealthChecker()


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Basic health check endpoint.
    Returns minimal health information for load balancers and monitoring systems.
    """
    logger.info("Health check endpoint called")
    try:
        # Quick checks only
        logger.info("Calling database health check")
        db_check = health_checker.check_database_health(db)
        logger.info(f"Database check result: {db_check.status.value}")

        logger.info("Calling Redis health check")
        redis_check = health_checker.check_redis_health(redis_client)
        logger.info(f"Redis check result: {redis_check.status.value}")

        # Determine status
        if db_check.status == HealthStatus.UNHEALTHY or redis_check.status == HealthStatus.UNHEALTHY:
            status_code = 503
            status = "unhealthy"
        elif db_check.status == HealthStatus.DEGRADED or redis_check.status == HealthStatus.DEGRADED:
            status_code = 200
            status = "degraded"
        else:
            status_code = 200
            status = "healthy"

        result = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - health_checker.start_time,
            "version": settings.VERSION,
            "checks": {
                "database": {
                    "status": db_check.status.value,
                    "response_time": db_check.response_time
                },
                "redis": {
                    "status": redis_check.status.value,
                    "response_time": redis_check.response_time
                }
            }
        }
        logger.info(f"Health check result: {status}")
        return result

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 503


@router.get("/health/detailed", response_model=Dict[str, Any])
async def detailed_health_check(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client),
    include_system_checks: bool = True
):
    """
    Detailed health check endpoint.
    Returns comprehensive health information for monitoring and debugging.
    """
    try:
        # Schedule background health check update
        background_tasks.add_task(
            health_checker.run_comprehensive_health_check,
            db, redis_client, include_system_checks
        )

        # Run health check
        health_report = await health_checker.run_comprehensive_health_check(
            db, redis_client, include_system_checks
        )

        # Convert to response format
        response = {
            "overall_status": health_report.overall_status.value,
            "timestamp": health_report.timestamp.isoformat(),
            "uptime_seconds": health_report.uptime_seconds,
            "version": health_report.version,
            "system_info": health_report.system_info,
            "checks": []
        }

        for check in health_report.checks:
            check_data = {
                "name": check.name,
                "status": check.status.value,
                "response_time": check.response_time,
                "message": check.message,
                "timestamp": check.timestamp.isoformat()
            }

            if check.details:
                check_data["details"] = check.details

            response["checks"].append(check_data)

        # Set appropriate status code
        if health_report.overall_status == HealthStatus.UNHEALTHY:
            status_code = 503
        elif health_report.overall_status == HealthStatus.DEGRADED:
            status_code = 200
        else:
            status_code = 200

        return response, status_code

    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "overall_status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 503


@router.get("/health/ready", response_model=Dict[str, Any])
async def readiness_check(
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Readiness check endpoint for Kubernetes/container orchestration.
    Checks if the application is ready to serve traffic.
    """
    try:
        # Check critical components
        db_check = health_checker.check_database_health(db)
        redis_check = health_checker.check_redis_health(redis_client)

        # Application is ready if database and redis are healthy
        if (db_check.status == HealthStatus.HEALTHY and
            redis_check.status == HealthStatus.HEALTHY):

            return {
                "ready": True,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": db_check.status.value,
                    "redis": redis_check.status.value
                }
            }
        else:
            return {
                "ready": False,
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {
                    "database": db_check.status.value,
                    "redis": redis_check.status.value
                }
            }, 503

    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "ready": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 503


@router.get("/health/live", response_model=Dict[str, Any])
async def liveness_check():
    """
    Liveness check endpoint for Kubernetes/container orchestration.
    Checks if the application is still running.
    """
    try:
        # Simple liveness check - if we can respond, we're alive
        return {
            "alive": True,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - health_checker.start_time
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return {
            "alive": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 503


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Get application metrics for monitoring.
    """
    try:
        system_info = health_checker.get_system_info()

        # Get basic health metrics
        health_report = await health_checker.run_comprehensive_health_check(
            db, redis_client, include_system_checks=False
        )

        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": time.time() - health_checker.start_time,
            "version": settings.VERSION,
            "system": system_info,
            "health_checks": {
                check.name: {
                    "status": check.status.value,
                    "response_time": check.response_time
                }
                for check in health_report.checks
            }
        }

        return metrics

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 500


@router.get("/")
async def legacy_health_check(db: Session = Depends(get_db)):
    """
    Legacy health check endpoint for backward compatibility.
    """
    return await health_check(BackgroundTasks(), db)


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity check.
    """
    return {
        "status": "ok",
        "message": "pong",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/version")
async def version_info():
    """
    Get version information.
    """
    return {
        "version": settings.VERSION,
        "name": settings.PROJECT_NAME,
        "environment": "development" if settings.DEBUG else "production"
    }