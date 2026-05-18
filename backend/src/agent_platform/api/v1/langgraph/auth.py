"""LangGraph-compatible Auth handler.

Provides the auth entry point referenced by langgraph.json:
  "auth": {"path": "./src/agent_platform/api/v1/langgraph/auth.py:auth"}

This bridges Forge's JWT auth system to the LangGraph auth protocol.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from agent_platform.auth.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["langgraph-auth"])


class AuthResponse(BaseModel):
    user_id: str
    org_id: Optional[str] = None
    permissions: list[str] = []


async def auth(request: Request) -> dict[str, Any]:
    """LangGraph auth handler.

    Called by LangGraph Platform runtime to authenticate requests.
    Returns a dict with user identity that gets attached to the request context.
    """
    from jose import JWTError, jwt

    from agent_platform.config import get_settings

    settings = get_settings()

    # Extract token from Authorization header
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header[7:]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")

        return {
            "identity": user_id,
            "permissions": payload.get("permissions", ["*"]),
            "metadata": {
                "org_id": payload.get("org_id"),
                "role": payload.get("role", "user"),
            },
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/me", response_model=AuthResponse)
async def get_auth_info(user=Depends(get_current_user)):
    """Get current user auth info (for LangGraph Studio)."""
    return AuthResponse(
        user_id=str(user.id),
        org_id=str(user.org_id) if user.org_id else None,
        permissions=["*"],
    )
