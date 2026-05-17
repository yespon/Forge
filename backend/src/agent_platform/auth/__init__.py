"""Authentication and authorization module."""

from agent_platform.auth.dependencies import get_current_user, get_current_active_user
from agent_platform.auth.jwt import create_access_token, create_refresh_token, decode_token
from agent_platform.auth.password import verify_password, hash_password
from agent_platform.auth.rbac import require_permission

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_password",
    "hash_password",
    "require_permission",
]
