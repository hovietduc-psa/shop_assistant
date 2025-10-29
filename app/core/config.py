"""
Application configuration settings.
"""
# Force reload to clear Shopify domain cache

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Project settings
    PROJECT_NAME: str = "Shop Assistant AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"  # Chat endpoints configured

    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/shop_assistant"
    )

    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # CORS settings
    ALLOWED_HOSTS: str = "*"

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse ALLOWED_HOSTS from comma-separated string to list."""
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    # OpenRouter settings
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    DEFAULT_LLM_MODEL: str = os.getenv("DEFAULT_LLM_MODEL", "openai/gpt-4")

    # 3-Stage system model configuration for cost and performance optimization
    # Stage 1: Intent Classification
    INTENT_CLASSIFICATION_MODEL: str = os.getenv("INTENT_CLASSIFICATION_MODEL", "meta-llama/llama-3.1-8b-instruct")

    # Stage 2: Tool Call/Execution
    TOOL_CALL_MODEL: str = os.getenv("TOOL_CALL_MODEL", "openai/gpt-4o-mini")

    # Stage 3: Response Generation
    RESPONSE_GENERATION_MODEL: str = os.getenv("RESPONSE_GENERATION_MODEL", "openai/gpt-4o-mini")

    # Cohere settings
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_BASE_URL: str = "https://api.cohere.ai/v1"
    DEFAULT_EMBEDDING_MODEL: str = "embed-english-v3.0"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Development settings
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    TESTING: bool = os.getenv("TESTING", "false").lower() == "true"

    # File upload settings
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [".txt", ".pdf", ".doc", ".docx"]

    # Session settings
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_CONVERSATION_LENGTH: int = 50

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Shopify settings
    SHOPIFY_SHOP_DOMAIN: str = os.getenv("SHOPIFY_SHOP_DOMAIN", "")
    SHOPIFY_ACCESS_TOKEN: str = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    SHOPIFY_API_VERSION: str = "2024-01"
    SHOPIFY_WEBHOOK_SECRET: str = os.getenv("SHOPIFY_WEBHOOK_SECRET", "")
    SHOPIFY_APP_SECRET: str = os.getenv("SHOPIFY_APP_SECRET", "")

    # Shopify API limits
    SHOPIFY_RATE_LIMIT_PER_SECOND: int = 2
    SHOPIFY_BURST_LIMIT: int = 40
    SHOPIFY_BATCH_SIZE: int = 250

    # LangGraph experimental settings
    USE_LANGGRAPH: bool = os.getenv("USE_LANGGRAPH", "false").lower() == "true"
    LANGGRAPH_PHASE: int = int(os.getenv("LANGGRAPH_PHASE", "1"))
    LANGGRAPH_ENABLE_INTELLIGENT_ROUTING: bool = os.getenv("LANGGRAPH_ENABLE_INTELLIGENT_ROUTING", "false").lower() == "true"
    LANGGRAPH_ENABLE_STREAMING: bool = os.getenv("LANGGRAPH_ENABLE_STREAMING", "false").lower() == "true"
    LANGGRAPH_ENABLE_PARALLEL_PROCESSING: bool = os.getenv("LANGGRAPH_ENABLE_PARALLEL_PROCESSING", "false").lower() == "true"
    LANGGRAPH_ENABLE_CACHING: bool = os.getenv("LANGGRAPH_ENABLE_CACHING", "false").lower() == "true"
    LANGGRAPH_ENABLE_MONITORING: bool = os.getenv("LANGGRAPH_ENABLE_MONITORING", "false").lower() == "true"
    LANGGRAPH_MAX_CONCURRENT_WORKFLOWS: int = int(os.getenv("LANGGRAPH_MAX_CONCURRENT_WORKFLOWS", "5"))
    LANGGRAPH_CHECKPOINT_TTL: int = int(os.getenv("LANGGRAPH_CHECKPOINT_TTL", "3600"))
    LANGGRAPH_CACHE_TTL: int = int(os.getenv("LANGGRAPH_CACHE_TTL", "1800"))
    LANGGRAPH_STREAM_CHUNK_SIZE: int = int(os.getenv("LANGGRAPH_STREAM_CHUNK_SIZE", "100"))
    LANGGRAPH_TIMEOUT: int = int(os.getenv("LANGGRAPH_TIMEOUT", "30"))

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra environment variables


# Create global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings