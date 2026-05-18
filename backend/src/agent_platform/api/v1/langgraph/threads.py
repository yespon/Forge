"""LangGraph-compatible Threads API.

Implements the LangGraph Platform thread management endpoints:
- POST   /threads          — Create a thread
- GET    /threads/{id}     — Get thread state
- GET    /threads          — List threads
- DELETE /threads/{id}     — Delete a thread
- GET    /threads/{id}/state — Get thread checkpoint state
- POST   /threads/{id}/state — Update thread state
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.database import get_db
from agent_platform.models.session import Session
from agent_platform.auth.dependencies import get_current_user

router = APIRouter(prefix="/threads", tags=["langgraph-threads"])


# --- Request/Response schemas ---


class ThreadCreate(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)
    if_exists: Optional[str] = None  # "raise" | "update" | None


class ThreadResponse(BaseModel):
    thread_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    status: str = "idle"

    class Config:
        from_attributes = True


class ThreadState(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    next: list[str] = Field(default_factory=list)
    checkpoint: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# --- Endpoints ---


@router.post("", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new thread (maps to Forge session)."""
    from sqlalchemy import select

    thread_id = str(uuid4())

    session = Session(
        id=thread_id,
        user_id=user.id,
        name=body.metadata.get("name", "LangGraph Thread"),
        description=body.metadata.get("description", ""),
        thread_id=thread_id,
        settings={"langgraph_metadata": body.metadata},
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return ThreadResponse(
        thread_id=thread_id,
        metadata=body.metadata,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        status="idle",
    )


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    metadata: Optional[str] = None,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List threads for the current user."""
    from sqlalchemy import select

    query = (
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    return [
        ThreadResponse(
            thread_id=str(s.id),
            metadata=s.settings.get("langgraph_metadata", {}) if s.settings else {},
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            status="idle" if s.is_active else "interrupted",
        )
        for s in sessions
    ]


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific thread."""
    from sqlalchemy import select

    result = await db.execute(
        select(Session).where(Session.id == thread_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    return ThreadResponse(
        thread_id=str(session.id),
        metadata=session.settings.get("langgraph_metadata", {}) if session.settings else {},
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
        status="idle" if session.is_active else "interrupted",
    )


@router.delete("/{thread_id}")
async def delete_thread(
    thread_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a thread."""
    from sqlalchemy import select

    result = await db.execute(
        select(Session).where(Session.id == thread_id, Session.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    await db.delete(session)
    await db.commit()
    return {"status": "ok"}


@router.get("/{thread_id}/state", response_model=ThreadState)
async def get_thread_state(
    thread_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the checkpoint state of a thread."""
    from agent_platform.runtime.checkpointer import get_checkpointer

    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        checkpoint = await checkpointer.aget(config)
    except Exception:
        checkpoint = None

    if checkpoint is None:
        return ThreadState(values={}, next=[], checkpoint=None, metadata={})

    return ThreadState(
        values=checkpoint.get("channel_values", {}),
        next=checkpoint.get("pending_sends", []),
        checkpoint={"id": checkpoint.get("id"), "ts": checkpoint.get("ts")},
        metadata=checkpoint.get("metadata", {}),
    )


@router.post("/{thread_id}/state")
async def update_thread_state(
    thread_id: str,
    body: dict[str, Any],
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update thread state (add messages, etc.)."""
    from agent_platform.runtime.checkpointer import get_checkpointer

    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}

    values = body.get("values", {})
    as_node = body.get("as_node", "__input__")

    try:
        checkpoint = await checkpointer.aget(config)
        # Merge values into channel_values
        if checkpoint:
            channel_values = checkpoint.get("channel_values", {})
            if "messages" in values and "messages" in channel_values:
                channel_values["messages"].extend(values["messages"])
            else:
                channel_values.update(values)
    except Exception:
        pass

    return {"status": "ok"}
