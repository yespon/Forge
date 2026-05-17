"""Authentication endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from agent_platform.auth.dependencies import CurrentUser, get_current_active_user
from agent_platform.config import get_settings
from agent_platform.database import get_db, get_redis
from agent_platform.models.org import Org
from agent_platform.models.user import User, UserRole, UserStatus

router = APIRouter(prefix="/auth", tags=["auth"])


# Request/Response Schemas
class TokenResponse(BaseModel):
    """Token response schema."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="Refresh token")


class UserResponse(BaseModel):
    """User response schema."""

    id: str
    email: str
    display_name: str | None
    role: str
    status: str
    org_id: str
    settings: dict

    @field_validator("id", "org_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID to string."""
        if hasattr(v, "hex"):
            return str(v)
        return v

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    """User registration request."""

    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")
    display_name: str | None = Field(None, description="Display name")
    org_name: str | None = Field(None, description="Organization name (optional)")


class LoginResponse(BaseModel):
    """Login response with user info and tokens."""

    user: UserResponse
    tokens: TokenResponse


# Helper functions
async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """Authenticate user by email and password.

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        User if authenticated, None otherwise
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        return None

    if not user.password_hash:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_or_create_default_org(db: AsyncSession) -> Org:
    """Get or create default organization for new registrations.

    Args:
        db: Database session

    Returns:
        Default organization
    """
    result = await db.execute(
        select(Org).where(Org.slug == "default")
    )
    org = result.scalar_one_or_none()

    if not org:
        org = Org(
            name="Default Organization",
            slug="default",
            status="active",
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)

    return org


# Endpoints
@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Login with email and password.

    Returns access and refresh tokens on successful authentication.
    """
    user = await authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or suspended",
        )

    # Update last login
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    user.login_count += 1
    await db.commit()

    # Generate tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=120 * 60,  # 2 hours in seconds
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
) -> TokenResponse:
    """Refresh access token using refresh token."""
    payload = decode_token(request.refresh_token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create new tokens
    # Note: In a full implementation, we'd verify the user still exists and is active
    token_data = {"sub": user_id}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=120 * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Register a new user account.

    Creates a new user and organization (if specified).
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Get or create organization
    if request.org_name:
        # Create new organization
        import re
        slug = re.sub(r'[^\w]+', '-', request.org_name.lower()).strip('-')

        # Check for duplicate slug
        result = await db.execute(select(Org).where(Org.slug == slug))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Organization name already taken",
            )

        org = Org(
            name=request.org_name,
            slug=slug,
            status="active",
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)
    else:
        org = await get_or_create_default_org(db)

    # Create user
    user = User(
        org_id=org.id,
        email=request.email,
        display_name=request.display_name or request.email.split("@")[0],
        password_hash=hash_password(request.password),
        role=UserRole.ORG_ADMIN if request.org_name else UserRole.DEVELOPER,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=120 * 60,
        ),
    )


@router.post("/logout")
async def logout(
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Logout current user and blacklist the access token."""
    settings = get_settings()
    try:
        redis = await get_redis()
        # Blacklist the user's current token for its remaining TTL
        ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await redis.setex(
            f"token_blacklist:{current_user.id}",
            ttl,
            "1",
        )
    except Exception:
        pass  # fail-open: if Redis is down, token expires naturally
    return {"message": "Successfully logged out"}
