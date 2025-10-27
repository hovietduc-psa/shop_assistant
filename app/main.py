"""
Shop Assistant AI - Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from pathlib import Path

from app.core.config import settings
from app.middleware.logging import LoggingMiddleware
from app.middleware.security import SecurityMiddleware
from app.utils.error_handlers import (
    shop_assistant_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    database_exception_handler,
    general_exception_handler,
)
from app.utils.exceptions import ShopAssistantException
import redis

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)

# Initialize Redis client for middleware
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Shop Assistant AI application...")
    yield
    logger.info("Shutting down Shop Assistant AI application...")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered sales and consulting agent API",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Add exception handlers
app.add_exception_handler(ShopAssistantException, shop_assistant_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_hosts_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add custom middleware
app.add_middleware(SecurityMiddleware, redis_client=redis_client)
app.add_middleware(LoggingMiddleware)

# Add CORS preflight handler before router
@app.options("/{path:path}")
async def handle_options(request: Request):
    """Handle OPTIONS requests for CORS preflight."""
    return JSONResponse(
        content={"message": "OK"},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400"
        }
    )

# Create a static files directory and mount it
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def frontend():
    """Serve the chat frontend."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="""
        <html>
            <head><title>Shop Assistant AI</title></head>
            <body>
                <h1>Shop Assistant AI</h1>
                <p>Frontend not found. Please check that the static files are properly set up.</p>
                <p><a href="/docs">API Documentation</a></p>
            </body>
        </html>
        """
    )


# Include API routers after frontend routes to avoid conflicts
try:
    from app.api.v1.endpoints import auth
    app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
    print("Auth router loaded successfully")
except ImportError as e:
    print(f"Auth router failed to load: {e}")

try:
    from app.api.v1.endpoints import chat
    app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["Chat"])
    print("Chat router loaded successfully")
except ImportError as e:
    print(f"Chat router failed to load: {e}")

try:
    from app.api.v1.endpoints import ai
    app.include_router(ai.router, prefix=f"{settings.API_V1_STR}/ai", tags=["AI Services"])
    print("AI router loaded successfully")
except ImportError as e:
    print(f"AI router failed to load: {e}")

try:
    from app.api.v1.endpoints import tools_streamlined
    app.include_router(tools_streamlined.router, prefix=f"{settings.API_V1_STR}/tools", tags=["Streamlined Tools"])
    print("Tools streamlined router loaded successfully")
except ImportError as e:
    print(f"Tools streamlined router failed to load: {e}")

# Force reload to fix chat endpoints

# Shopify endpoints
try:
    from app.api.v1.endpoints.shopify import products_router, orders_router, customers_router, collections_router, webhooks_router, policies_router
    app.include_router(products_router, prefix=f"{settings.API_V1_STR}/products", tags=["Shopify Products"])
    app.include_router(orders_router, prefix=f"{settings.API_V1_STR}/orders", tags=["Shopify Orders"])
    app.include_router(customers_router, prefix=f"{settings.API_V1_STR}/customers", tags=["Shopify Customers"])
    app.include_router(collections_router, prefix=f"{settings.API_V1_STR}/collections", tags=["Shopify Collections"])
    app.include_router(webhooks_router, prefix=f"{settings.API_V1_STR}/webhooks", tags=["Shopify Webhooks"])
    app.include_router(policies_router, prefix=f"{settings.API_V1_STR}/policies", tags=["Shopify Policies"])
except ImportError:
    pass

# Other endpoints
try:
    from app.api.v1.endpoints.sandbox import playground_router
    app.include_router(playground_router, prefix=f"{settings.API_V1_STR}/sandbox", tags=["Sandbox"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints.sandbox.testing import testing_router
    app.include_router(testing_router, prefix=f"{settings.API_V1_STR}/sandbox", tags=["Sandbox Testing"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints.agents import agents_router, auth_router, routing_router
    if agents_router:
        app.include_router(agents_router, prefix=f"{settings.API_V1_STR}/agents", tags=["Agent Management"])
    if auth_router:
        app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/agents/auth", tags=["Agent Auth"])
    if routing_router:
        app.include_router(routing_router, prefix=f"{settings.API_V1_STR}/agents/routing", tags=["Agent Routing"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints.metrics import router as metrics_router
    from app.api.v1.endpoints.monitoring import health_router, analytics_router, cache_router
    app.include_router(metrics_router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["Monitoring Metrics"])
    app.include_router(health_router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["Monitoring Health"])
    app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["Monitoring Analytics"])
    app.include_router(cache_router, prefix=f"{settings.API_V1_STR}/monitoring", tags=["Monitoring Cache"])
except ImportError:
    pass

try:
    from app.api.v1.endpoints.security import router as security_router
    app.include_router(security_router, prefix=f"{settings.API_V1_STR}/security", tags=["Security"])
except ImportError:
    pass


@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {
        "message": "Shop Assistant AI API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "operational",
        "frontend": "/",
        "chat_api": f"{settings.API_V1_STR}/chat/message"
    }


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "shop-assistant-ai"}


@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    """Add request ID header for tracing."""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response