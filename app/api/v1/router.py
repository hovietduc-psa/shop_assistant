"""
Main API router for version 1.
"""

from fastapi import APIRouter

# Import endpoints with error handling to provide better debugging
health = auth = chat = ai = tools_streamlined = None
try:
    from app.api.v1.endpoints import health, auth, chat, ai, tools_streamlined
    print("Core endpoints imported successfully")
except ImportError as e:
    print(f"Core endpoints failed: {e}")

try:
    from app.api.v1.endpoints.shopify import (
        products_router, orders_router, customers_router, collections_router, webhooks_router, policies_router
    )
    print("Shopify endpoints imported successfully")
except ImportError as e:
    print(f"Shopify endpoints failed: {e}")
    products_router = orders_router = customers_router = collections_router = webhooks_router = policies_router = None

try:
    from app.api.v1.endpoints.sandbox import playground_router
    print("Sandbox playground endpoints imported successfully")
except ImportError as e:
    print(f"Sandbox playground endpoints failed: {e}")
    playground_router = None

try:
    from app.api.v1.endpoints.sandbox.testing import testing_router
    print("Sandbox testing endpoints imported successfully")
except ImportError as e:
    print(f"Sandbox testing endpoints failed: {e}")
    testing_router = None

try:
    from app.api.v1.endpoints.agents import agents_router, auth_router, routing_router
    print("Agent management endpoints imported successfully")
except ImportError as e:
    print(f"Agent management endpoints failed: {e}")
    agents_router = auth_router = routing_router = None

try:
    from app.api.v1.endpoints.metrics import router as metrics_router
    from app.api.v1.endpoints.monitoring import (
        health_router, analytics_router, cache_router
    )
    print("Monitoring endpoints imported successfully")
except ImportError as e:
    print(f"Monitoring endpoints failed: {e}")
    health_router = metrics_router = analytics_router = cache_router = None

api_router = APIRouter()

# Include endpoint routers with try-catch for each
try:
    if health:
        api_router.include_router(health.router, prefix="/health", tags=["Health"])
        print("Health endpoints loaded")
    else:
        print("Health endpoints not available")
except ImportError as e:
    print(f"Health endpoints failed: {e}")

try:
    if auth:
        api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
        print("Auth endpoints loaded")
    else:
        print("Auth endpoints not available")
except ImportError as e:
    print(f"Auth endpoints failed: {e}")

try:
    if chat:
        api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
        print("Chat endpoints loaded")
    else:
        print("Chat endpoints not available")
except ImportError as e:
    print(f"Chat endpoints failed: {e}")

try:
    if ai:
        api_router.include_router(ai.router, prefix="/ai", tags=["AI Services"])
        print("AI endpoints loaded")
    else:
        print("AI endpoints not available")
except ImportError as e:
    print(f"AI endpoints failed: {e}")

try:
    if tools_streamlined:
        api_router.include_router(tools_streamlined.router, prefix="/tools", tags=["Streamlined Tools"])
        print("Streamlined tools endpoints loaded")
    else:
        print("Streamlined tools endpoints not available")
except ImportError as e:
    print(f"Streamlined tools endpoints failed: {e}")

# Shopify endpoints
try:
    if products_router:
        api_router.include_router(products_router)
        print("Shopify products endpoints loaded")
    else:
        print("Shopify products endpoints not available")
except ImportError as e:
    print(f"Shopify products endpoints failed: {e}")

try:
    if orders_router:
        api_router.include_router(orders_router)
        print("Shopify orders endpoints loaded")
    else:
        print("Shopify orders endpoints not available")
except ImportError as e:
    print(f"Shopify orders endpoints failed: {e}")

try:
    if customers_router:
        api_router.include_router(customers_router)
        print("Shopify customers endpoints loaded")
    else:
        print("Shopify customers endpoints not available")
except ImportError as e:
    print(f"Shopify customers endpoints failed: {e}")

try:
    if collections_router:
        api_router.include_router(collections_router)
        print("Shopify collections endpoints loaded")
    else:
        print("Shopify collections endpoints not available")
except ImportError as e:
    print(f"Shopify collections endpoints failed: {e}")

try:
    if webhooks_router:
        api_router.include_router(webhooks_router)
        print("Shopify webhooks endpoints loaded")
    else:
        print("Shopify webhooks endpoints not available")
except ImportError as e:
    print(f"Shopify webhooks endpoints failed: {e}")

try:
    if policies_router:
        api_router.include_router(policies_router)
        print("Shopify policies endpoints loaded")
    else:
        print("Shopify policies endpoints not available")
except ImportError as e:
    print(f"Shopify policies endpoints failed: {e}")

# Advanced API features
try:
    if health_router:
        api_router.include_router(health_router, prefix="/monitoring")
        print("Monitoring health endpoints loaded")
    else:
        print("Monitoring health endpoints not available")
except ImportError as e:
    print(f"Monitoring health endpoints failed: {e}")

try:
    if metrics_router:
        api_router.include_router(metrics_router, prefix="/monitoring")
        print("Monitoring metrics endpoints loaded")
    else:
        print("Monitoring metrics endpoints not available")
except ImportError as e:
    print(f"Monitoring metrics endpoints failed: {e}")

try:
    if analytics_router:
        api_router.include_router(analytics_router, prefix="/monitoring")
        print("Monitoring analytics endpoints loaded")
    else:
        print("Monitoring analytics endpoints not available")
except ImportError as e:
    print(f"Monitoring analytics endpoints failed: {e}")

try:
    if cache_router:
        api_router.include_router(cache_router, prefix="/monitoring")
        print("Monitoring cache endpoints loaded")
    else:
        print("Monitoring cache endpoints not available")
except ImportError as e:
    print(f"Monitoring cache endpoints failed: {e}")

try:
    if playground_router:
        api_router.include_router(playground_router, prefix="/sandbox")
        print("Sandbox playground endpoints loaded")
    else:
        print("Sandbox playground endpoints not available")
except (ImportError, NameError) as e:
    print(f"Sandbox playground endpoints failed: {e}")

try:
    if testing_router:
        api_router.include_router(testing_router, prefix="/sandbox")
        print("Sandbox testing endpoints loaded")
    else:
        print("Sandbox testing endpoints not available")
except (ImportError, NameError) as e:
    print(f"Sandbox testing endpoints failed: {e}")

# Agent Management System
try:
    if agents_router:
        api_router.include_router(agents_router, prefix="/agents")
        print("Agent management endpoints loaded")
    else:
        print("Agent management endpoints not available")
except (ImportError, NameError) as e:
    print(f"Agent management endpoints failed: {e}")

try:
    if auth_router:
        api_router.include_router(auth_router, prefix="/agents/auth")
        print("Agent auth endpoints loaded")
    else:
        print("Agent auth endpoints not available")
except (ImportError, NameError) as e:
    print(f"Agent auth endpoints failed: {e}")

try:
    if routing_router:
        api_router.include_router(routing_router, prefix="/agents/routing")
        print("Agent routing endpoints loaded")
    else:
        print("Agent routing endpoints not available")
except (ImportError, NameError) as e:
    print(f"Agent routing endpoints failed: {e}")


# Enterprise Security System
try:
    from app.api.v1.endpoints.security import router as security_router
    api_router.include_router(security_router, prefix="/security", tags=["Security"])
    print("Security endpoints loaded")
except ImportError as e:
    print(f"Security endpoints failed: {e}")

# Create a simple root endpoint that shows what's available
@api_router.get("/")
async def api_root():
    return {
        "message": "Shop Assistant AI API v1",
        "status": "operational",
        "version": "0.1.0",
        "available_endpoints": {
            "health": "/health",
            "auth": "/auth",
            "chat": "/chat",
            "ai": "/ai",
            "tools": "/tools",
            "shopify": {
                "products": "/products",
                "orders": "/orders",
                "customers": "/customers",
                "collections": "/collections",
                "webhooks": "/webhooks",
                "policies": "/policies"
            },
            "monitoring": "/monitoring",
            "sandbox": "/sandbox",
            "agents": "/agents",
            "security": "/security"
        },
        "docs": "/docs"
    }