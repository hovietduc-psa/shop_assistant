"""
Database session management.
"""

from typing import Generator
import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=20,
    max_overflow=30,
    echo=settings.DEBUG,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.

    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis_client() -> redis.Redis:
    """
    Get Redis client instance.

    Returns:
        redis.Redis: Redis client
    """
    return redis_client