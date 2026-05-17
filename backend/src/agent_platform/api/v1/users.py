"""User management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.auth.password import hash_password
from agent_platform.auth.rbac import require_permission
from agent_platform.database import get_db
from agent_platform.models.org import Org
from agent_platform.models.user import User, UserRole, UserStatus

router = APIRouter(prefix="/users", tags=["users"])


# Request/Response Schemas
class UserBase(BaseModel):
    """Base user schema."""

    email: EmailStr
    display_name: str | None = None
    role: UserRole = UserRole.DEVELOPER


class UserCreate(UserBase):
    """Create user request."""

    password: str = Field(..., min_length=8)
    org_id: UUID | None = None


class UserUpdate(BaseModel):
    """Update user request."""

    email: EmailStr | None = None
    display_name: str | None = None
    role: UserRole | None = None
    status: UserStatus | None = None
    password: str | None = Field(None, min_length=8)


class UserResponse(BaseModel):
    """User response schema."""

    id: str
    email: str
    display_name: str | None
    role: str
    status: str
    org_id: str
    settings: dict
    login_count: int
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list response."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int


# Endpoints
@router.get("", response_model=UserListResponse)
@require_permission("user:read")
async def list_users(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    org_id: Annotated[UUID | None, Query()] = None,
    role: Annotated[UserRole | None, Query()] = None,
    status: Annotated[UserStatus | None, Query()] = None,
) -> UserListResponse:
    """List users with pagination and filtering.

    Users can only see users in their own organization
    unless they are platform admins.
    """
    # Build query
    query = select(User).where(User.deleted_at.is_(None))

    # Filter by org (non-platform admins can only see their org)
    if current_user.role != UserRole.PLATFORM_ADMIN:
        query = query.where(User.org_id == current_user.org_id)
    elif org_id:
        query = query.where(User.org_id == org_id)

    # Additional filters
    if role:
        query = query.where(User.role == role)
    if status:
        query = query.where(User.status == status)

    # Get total count
    count_result = await db.execute(select(query.subquery().c.id))
    total = len(count_result.all())

    # Pagination
    query = query.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@require_permission("user:create")
async def create_user(
    current_user: CurrentUser,
    request: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Create a new user.

    Users can only create users in their own organization.
    Only org admins can assign admin roles.
    """
    # Determine org_id
    org_id = request.org_id or current_user.org_id

    # Permission check: non-platform admins can only create in their org
    if current_user.role != UserRole.PLATFORM_ADMIN and org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create users in other organizations",
        )

    # Permission check: only admins can create admins
    if request.role in (UserRole.PLATFORM_ADMIN, UserRole.ORG_ADMIN):
        if current_user.role not in (UserRole.PLATFORM_ADMIN, UserRole.ORG_ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can create admin users",
            )

    # Check email uniqueness within org
    result = await db.execute(
        select(User).where(
            User.email == request.email,
            User.org_id == org_id,
            User.deleted_at.is_(None),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered in this organization",
        )

    # Create user
    user = User(
        org_id=org_id,
        email=request.email,
        display_name=request.display_name,
        role=request.role,
        status=UserStatus.ACTIVE,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user information."""
    return UserResponse.model_validate(current_user)


@router.get("/{user_id}", response_model=UserResponse)
@require_permission("user:read")
async def get_user(
    current_user: CurrentUser,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Get user by ID."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Permission check
    if (
        current_user.role != UserRole.PLATFORM_ADMIN
        and user.org_id != current_user.org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access users from other organizations",
        )

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
@require_permission("user:update")
async def update_user(
    current_user: CurrentUser,
    user_id: UUID,
    request: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update user information."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Permission check
    if current_user.role != UserRole.PLATFORM_ADMIN:
        if user.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot modify users from other organizations",
            )

        # Users can only modify themselves unless they're admins
        if user.id != current_user.id and current_user.role != UserRole.ORG_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only modify your own profile",
            )

        # Only admins can change roles
        if request.role and request.role != user.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change user roles",
            )

    # Update fields
    if request.email:
        # Check email uniqueness
        existing = await db.execute(
            select(User).where(
                User.email == request.email,
                User.org_id == user.org_id,
                User.id != user.id,
                User.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )
        user.email = request.email

    if request.display_name is not None:
        user.display_name = request.display_name

    if request.role:
        user.role = request.role

    if request.status:
        user.status = request.status

    if request.password:
        user.password_hash = hash_password(request.password)

    await db.commit()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("user:delete")
async def delete_user(
    current_user: CurrentUser,
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft delete a user."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Permission check
    if current_user.role != UserRole.PLATFORM_ADMIN:
        if user.org_id != current_user.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete users from other organizations",
            )

    # Cannot delete yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Soft delete
    from datetime import datetime, timezone
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()
