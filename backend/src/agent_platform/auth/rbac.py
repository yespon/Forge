"""Role-Based Access Control decorators and utilities."""

from functools import wraps
from typing import Callable, TypeVar

from fastapi import HTTPException, status

from agent_platform.models.user import User, UserRole

F = TypeVar("F", bound=Callable)


# Permission mapping: role -> allowed permissions
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.PLATFORM_ADMIN: {
        "*",  # All permissions
    },
    UserRole.ORG_ADMIN: {
        "user:read", "user:create", "user:update", "user:delete",
        "org:read", "org:update", "org:manage",
        "team:read", "team:create", "team:update", "team:delete",
        "session:read", "session:create", "session:update", "session:delete",
        "task:read", "task:create", "task:update", "task:delete",
        "skill:read", "skill:create", "skill:update", "skill:delete",
        "approval:read", "approval:approve",
        "sandbox:read", "sandbox:create", "sandbox:update", "sandbox:delete",
    },
    UserRole.TEAM_ADMIN: {
        "user:read",
        "team:read", "team:update",
        "session:read", "session:create", "session:update", "session:delete",
        "task:read", "task:create", "task:update",
        "skill:read",
        "approval:read", "approval:approve",
        "sandbox:read", "sandbox:create", "sandbox:update",
    },
    UserRole.DEVELOPER: {
        "user:read",
        "team:read",
        "session:read", "session:create", "session:update",
        "task:read", "task:create",
        "skill:read",
        "approval:read",
        "sandbox:read", "sandbox:create",
    },
    UserRole.VIEWER: {
        "user:read",
        "team:read",
        "session:read",
        "task:read",
        "skill:read",
        "sandbox:read",
    },
}


def has_permission(user: User, permission: str) -> bool:
    """Check if user has a specific permission.

    Args:
        user: User to check
        permission: Permission string (e.g., "session:create")

    Returns:
        True if user has permission, False otherwise
    """
    user_permissions = ROLE_PERMISSIONS.get(user.role, set())

    # Check for wildcard or specific permission
    return "*" in user_permissions or permission in user_permissions


def require_permission(permission: str) -> Callable[[F], F]:
    """Decorator to require a specific permission for an endpoint.

    Usage:
        @router.post("/sessions")
        @require_permission("session:create")
        async def create_session(current_user: CurrentUser):
            ...

    Args:
        permission: Required permission string

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get("current_user")

            if not current_user:
                # Try to find in args
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission}",
                )

            return await func(*args, **kwargs)

        return wrapper  # type: ignore
    return decorator


def require_any_permission(*permissions: str) -> Callable[[F], F]:
    """Decorator to require any of the specified permissions.

    Args:
        permissions: List of permission strings (any one grants access)

    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")

            if not current_user:
                for arg in args:
                    if isinstance(arg, User):
                        current_user = arg
                        break

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if any(has_permission(current_user, p) for p in permissions):
                return await func(*args, **kwargs)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: requires any of {permissions}",
            )

        return wrapper  # type: ignore
    return decorator


def require_admin(*args, **kwargs):
    """Dependency to require admin privileges.

    This function can be used as a FastAPI dependency to ensure
    only admin users can access certain endpoints.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_admin)])
        async def admin_endpoint():
            ...

    Returns:
        User object if admin, raises HTTPException otherwise
    """
    from agent_platform.auth.dependencies import get_current_user

    async def check_admin(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in (UserRole.PLATFORM_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )
        return current_user

    return check_admin
