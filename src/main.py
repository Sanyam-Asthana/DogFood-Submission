"""Main FastAPI Application Entrypoint.

DOGFOOD 2026 Hackathon Portal API - Events Implementation
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.database import init_db
from src.routers import events_router, auth_router, platform_router
from src.services.platform_service import PlatformService
import src.auth as auth
from src.seed import seed_fixtures
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hackathon_portal")


from typing import Optional

class AuthDetails(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle handler."""
    logger.info("Initializing database schema...")
    init_db()

    # Retrieve or generate platform owner setup key
    owner_key = PlatformService.get_or_create_owner_key()
    banner = f"""
================================================================================
  PLATFORM OWNER SETUP KEY: {owner_key}
  Use this key to claim Owner privileges:
    POST /api/platform/claim-owner with {{"setup_key": "{owner_key}"}}
  (Saved to: .owner_key)
================================================================================
"""
    print(banner, flush=True)
    logger.info(f"Platform owner setup key is ready (persisted to .owner_key).")

    # Automatically seed test fixtures if running in development mode
    try:
        logger.info("Checking/seeding initial fixtures...")
        seed_fixtures()
    except Exception as e:
        logger.warning(f"Seeding fixtures encountered an issue: {e}")

    # Ensure all site-level accounts with legacy 'participant' role are normalized to 'user'
    try:
        from src.database import SessionLocal
        from src.models.user import User, UserRole
        db = SessionLocal()
        db.query(User).filter(User.role == "participant").update({"role": UserRole.USER.value})
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Role normalization encountered an issue: {e}")

    yield
    logger.info("Shutting down DOGFOOD Hackathon Portal API.")


app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## DOGFOOD 2026 Submission & Judging Portal API - Events & Roles Module
    
    ### Modules:
    - **Platform Administration**: Self-hosted owner setup key, organizer promotion/demotion.
    - **Events**: Create, configure, monitor, and enforce deadlines for hackathon events and tracks.
    - **Event Roles & Judging**: Event membership, judge invitations and responses.
    - **Authentication**: User registration, login, roles, and session tokens.
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Platform & Roles",
            "description": "Platform ownership claiming, organizer management, and judge invitations.",
        },
        {
            "name": "Events",
            "description": "Event lifecycle, submission deadlines, and competition tracks.",
        },
        {
            "name": "Authentication",
            "description": "User login, roles, and session tokens.",
        },
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Events, Auth, and Platform routers
app.include_router(events_router, prefix=settings.API_PREFIX)
app.include_router(events_router)  # Also available at /events directly
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(auth_router)
app.include_router(platform_router, prefix=settings.API_PREFIX)
app.include_router(platform_router)


# Supabase Auth endpoints from existing auth_endpoint.py
@app.post("/create_account", tags=["Supabase Auth"], summary="Supabase Sign Up")
def create_account(details: AuthDetails):
    return auth.create_account(details.username, details.password, details.role)


@app.post("/login", tags=["Supabase Auth"], summary="Supabase Login")
def login(details: AuthDetails):
    return auth.login(details.username, details.password)


@app.post("/logout", tags=["Supabase Auth"], summary="Supabase Logout")
def logout():
    return auth.logout()


@app.post("/get_current_user", tags=["Supabase Auth"], summary="Get Current Supabase User")
def get_current_user():
    return auth.get_current_user()


@app.get("/", tags=["Health & Info"], summary="API Root / Health Check")
def root_info():
    """Returns portal service status, current version, and links to documentation."""
    return {
        "portal": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "documentation": "/docs",
        "redoc": "/redoc",
        "api_prefix": settings.API_PREFIX,
    }


@app.get("/health", tags=["Health & Info"], summary="Health Probe")
def health_check():
    """Liveness probe for Docker container healthchecks."""
    return {"status": "ok"}


# Serve Testing Studio frontend
from pathlib import Path
from fastapi.responses import FileResponse

frontend_index_path = Path(__file__).resolve().parent / "temp_frontend" / "index.html"


@app.get("/app", include_in_schema=False)
@app.get("/portal", include_in_schema=False)
def serve_portal():
    return FileResponse(frontend_index_path)
