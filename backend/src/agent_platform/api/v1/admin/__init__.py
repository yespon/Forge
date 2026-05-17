"""Admin API endpoints."""

from agent_platform.api.v1.admin.audit import router as audit_router

__all__ = ["audit_router"]
