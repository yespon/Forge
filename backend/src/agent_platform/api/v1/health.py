"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.config import get_settings
from agent_platform.database import get_db

router = APIRouter()
settings = get_settings()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint.

    Returns:
        Health status including database connectivity.
    """
    # Check database connectivity
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar()  # scalar() returns value directly, not a coroutine
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENV,
        "services": {
            "database": db_status,
        },
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    return {"ready": True}


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes."""
    return {"alive": True}
