from src.routers.events import router as events_router
from src.routers.auth import router as auth_router
from src.routers.platform import router as platform_router

__all__ = ["events_router", "auth_router", "platform_router"]
