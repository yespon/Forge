"""Session management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.auth.rbac import require_permission
from agent_platform.database import get_db
from agent_platform.models.session import Session, SessionStatus
from agent_platform.models.user import User

router = APIRouter(prefix="/sessions", tags=["sessions"])


# Schemas
class SessionBase(BaseModel):
    """Base session schema."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    model: str = Field(default="claude-sonnet-4-6", max_length=50)
    system_prompt: str | None = None


class SessionCreate(SessionBase):
    """Create session request."""

    tools: list[str] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    """Update session request."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    status: SessionStatus | None = None
    settings: dict | None = None


class SessionResponse(BaseModel):
    """Session response."""

    id: str
    user_id: str
    name: str
    description: str | None
    status: str
    model: str
    system_prompt: str | None
    tools: list[str]
    settings: dict
    thread_id: str | None
    message_count: int
    token_usage: dict
    created_at: str
    updated_at: str
    last_activity_at: str

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Session list response."""

    items: list[SessionResponse]
    total: int
    page: int
    page_size: int


# Constants
MAX_ACTIVE_SESSIONS = 3


# Helper functions
async def check_session_limit(
    db: AsyncSession,
    user_id: str,
    exclude_session_id: str | None = None,
) -> int:
    """Check user's active session count.

    Args:
        db: Database session
        user_id: User ID
        exclude_session_id: Optional session ID to exclude from count

    Returns:
        Number of active sessions
    """
    query = select(func.count()).where(
        Session.user_id == user_id,
        Session.status.in_([SessionStatus.ACTIVE, SessionStatus.PAUSED]),
    )

    if exclude_session_id:
        query = query.where(Session.id != exclude_session_id)

    result = await db.execute(query)
    return result.scalar() or 0


# Endpoints
@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[SessionStatus | None, Query()] = None,
    include_terminated: Annotated[bool, Query()] = False,
) -> SessionListResponse:
    """List user's sessions.

    Returns sessions for the current user only.
    """
    # Build query
    query = select(Session).where(Session.user_id == current_user.id)

    # Filter by status
    if status:
        query = query.where(Session.status == status)
    elif not include_terminated:
        query = query.where(Session.status != SessionStatus.TERMINATED)

    # Count total
    count_query = select(func.count()).where(Session.user_id == current_user.id)
    if status:
        count_query = count_query.where(Session.status == status)
    elif not include_terminated:
        count_query = count_query.where(Session.status != SessionStatus.TERMINATED)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Pagination
    query = (
        query.order_by(Session.last_activity_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    sessions = result.scalars().all()

    return SessionListResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    current_user: CurrentUser,
    request: SessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    """Create a new session.

    Users are limited to 3 active sessions.
    """
    # Check session limit
    active_count = await check_session_limit(db, str(current_user.id))
    if active_count >= MAX_ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Maximum of {MAX_ACTIVE_SESSIONS} active sessions allowed. "
                   "Please terminate an existing session first.",
        )

    # Generate thread_id for checkpointing
    import uuid
    thread_id = f"user_{current_user.id}_session_{uuid.uuid4()}"

    # Create session
    session = Session(
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        model=request.model,
        system_prompt=request.system_prompt,
        tools=request.tools if request.tools else ["execute_bash", "read_file", "write_file"],
        settings=request.settings,
        status=SessionStatus.ACTIVE,
        thread_id=thread_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    """Get session by ID."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    current_user: CurrentUser,
    session_id: UUID,
    request: SessionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    """Update session."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Update fields
    if request.name is not None:
        session.name = request.name

    if request.description is not None:
        session.description = request.description

    if request.status is not None:
        # Handle status transitions
        if request.status == SessionStatus.TERMINATED:
            from datetime import datetime, timezone
            session.terminated_at = datetime.now(timezone.utc)
        session.status = request.status

    if request.settings is not None:
        session.settings.update(request.settings)

    await db.commit()
    await db.refresh(session)

    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Terminate and delete a session."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Soft delete (mark as terminated)
    from datetime import datetime, timezone
    session.status = SessionStatus.TERMINATED
    session.terminated_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/{session_id}/terminate", response_model=SessionResponse)
async def terminate_session(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    """Terminate a session."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session.status == SessionStatus.TERMINATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already terminated",
        )

    from datetime import datetime, timezone
    session.status = SessionStatus.TERMINATED
    session.terminated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    return SessionResponse.model_validate(session)
