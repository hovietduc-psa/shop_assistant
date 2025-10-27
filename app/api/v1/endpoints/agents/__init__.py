"""
Agent management API endpoints package.
"""

try:
    from .agents import router as agents_router
except ImportError as e:
    print(f"Failed to import agents_router: {e}")
    agents_router = None

try:
    from .auth import router as auth_router
except ImportError as e:
    print(f"Failed to import auth_router: {e}")
    auth_router = None

try:
    from .routing import router as routing_router
except ImportError as e:
    print(f"Failed to import routing_router: {e}")
    routing_router = None

# Only include available routers in __all__
__all__ = []
if agents_router:
    __all__.append("agents_router")
if auth_router:
    __all__.append("auth_router")
if routing_router:
    __all__.append("routing_router")