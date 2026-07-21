"""
API Routers for MARS-PaperPulse (Deep Research standalone).
"""

from routers.health import router as health_router
from routers.files import router as files_router
from routers.credentials import router as credentials_router
from routers.deepresearch import router as deepresearch_router
from routers.models import router as models_router
from routers.providers import router as providers_router
from routers.auth import router as auth_router
from routers.admin import router as admin_router


def register_routers(app):
    """Register all routers with the FastAPI application."""
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(health_router)
    app.include_router(files_router)
    app.include_router(credentials_router)
    app.include_router(deepresearch_router)
    app.include_router(models_router)
    app.include_router(providers_router)


__all__ = [
    "register_routers",
    "auth_router",
    "admin_router",
    "health_router",
    "files_router",
    "credentials_router",
    "deepresearch_router",
    "models_router",
    "providers_router",
]
