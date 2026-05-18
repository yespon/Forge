"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import models to register with Base
from agent_platform import models  # noqa: F401
from agent_platform.api.v1 import approvals, artifacts, auth, chat, connectors, health, langgraph, orgs, sandbox, sessions, skills, tasks, users, webhooks, ws
from agent_platform.api.v1 import integration as integration_routes
from agent_platform.api.v1.admin import audit as admin_audit
from agent_platform.config import get_settings
from agent_platform.database import init_db
from agent_platform.middleware.rate_limit import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    if settings.is_development:
        await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Multi-User Agent Runtime Platform",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, tags=["auth"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(orgs.router, prefix="/api/v1", tags=["organizations"])
app.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(sandbox.router, prefix="/api/v1", tags=["sandbox"])
app.include_router(approvals.router, prefix="/api/v1", tags=["approvals"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(connectors.router, prefix="/api/v1", tags=["connectors"])
app.include_router(artifacts.router, prefix="/api/v1", tags=["artifacts"])
app.include_router(skills.router, prefix="/api/v1", tags=["skills"])
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")
app.include_router(integration_routes.router)
app.include_router(langgraph.router)
app.include_router(admin_audit.router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/health")
async def root_health_check():
    """Health check endpoint at root path."""
    from agent_platform.api.v1.health import health_check
    from agent_platform.database import get_db

    async for db in get_db():
        return await health_check(db)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
