"""Chat endpoints for agent conversations.

This module provides chat endpoints that use the Task Runtime
for execution while maintaining backward-compatible SSE output.
"""

import json
from typing import Annotated, Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.session import Session, SessionStatus
from agent_platform.models.task import TaskType
from agent_platform.models.user import User
from agent_platform.services.task_runtime import TaskRuntime

router = APIRouter(prefix="/sessions/{session_id}/chat", tags=["chat"])


# Schemas
class ChatMessage(BaseModel):
    """Chat message."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Chat request."""

    message: str = Field(..., min_length=1, max_length=10000)
    stream: bool = Field(default=True, description="Stream response")


class ChatResponseChunk(BaseModel):
    """Chat response chunk for streaming."""

    type: str = Field(..., pattern="^(content|tool_call|tool_result|error|done)$")
    content: str | None = None
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: str | None = None
    error: str | None = None


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: str
    role: str
    content: str
    tool_calls: list[dict] | None = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    """Chat history response."""

    session_id: str
    messages: list[ChatMessageResponse]
    total: int


# Endpoints
async def _get_validated_session(
    session_id: UUID,
    user: User,
    db: AsyncSession,
) -> Session:
    """Get and validate session for chat.

    Args:
        session_id: Session ID
        user: Current user
        db: Database session

    Returns:
        Validated session

    Raises:
        HTTPException: If session not found or invalid
    """
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user.id,
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
            detail="Session has been terminated",
        )

    if session.status == SessionStatus.ERROR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is in error state",
        )

    # Resume session if paused
    if session.status == SessionStatus.PAUSED:
        session.status = SessionStatus.ACTIVE

    return session


@router.post("/completions")
async def chat_completion(
    current_user: CurrentUser,
    session_id: UUID,
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Send a message to the agent and get a streaming response.

    Streams the agent's response as Server-Sent Events (SSE).
    This endpoint uses Task Runtime internally while maintaining
    backward-compatible SSE output format.
    """
    # Get and validate session
    session = await _get_validated_session(session_id, current_user, db)

    # Update last activity
    session.touch()
    await db.commit()

    # Create TaskRuntime
    task_runtime = TaskRuntime(db=db)

    # Create task (implicit - user doesn't see this)
    task = await task_runtime.create_task(
        session_id=session.id,
        user_id=current_user.id,
        prompt=request.message,
        task_type=TaskType.SYNC,  # Chat is always sync
        org_id=current_user.org_id,
        enable_hitl=True,
    )

    # Stream response using Task Runtime
    async def stream_response() -> AsyncGenerator[str, None]:
        """Stream response chunks."""
        try:
            async for event in task_runtime.execute_task(task.id):
                # Convert TaskRuntime events to backward-compatible SSE format
                if event.type == "content":
                    yield f"data: {json.dumps({
                        'type': 'content',
                        'content': event.content,
                    })}\n\n"
                elif event.type == "error":
                    yield f"data: {json.dumps({
                        'type': 'error',
                        'error': event.error,
                    })}\n\n"
                elif event.type == "done":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                # Note: tool_call and tool_result are not exposed in chat API
                # They are tracked in task events for debugging

        except Exception as e:
            yield f"data: {json.dumps({
                'type': 'error',
                'error': str(e),
            })}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages", response_model=ChatMessageResponse)
async def send_message(
    current_user: CurrentUser,
    session_id: UUID,
    request: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatMessageResponse:
    """Send a message to the agent and get a non-streaming response.

    Use /completions for streaming responses.
    """
    session = await _get_validated_session(session_id, current_user, db)

    # Update activity
    session.touch()
    await db.commit()

    try:
        task_runtime = TaskRuntime(db=db)
        task = await task_runtime.create_task(
            session_id=session.id,
            user_id=current_user.id,
            prompt=request.message,
            task_type=TaskType.SYNC,
            org_id=current_user.org_id,
            enable_hitl=True,
        )

        content_parts: list[str] = []
        async for event in task_runtime.execute_task(task.id):
            if event.type == "content" and event.content:
                content_parts.append(event.content)
            elif event.type == "error":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Agent error: {event.error}",
                )

        # Update message count
        session.increment_message_count()
        await db.commit()

        return ChatMessageResponse(
            id=str(task.id),
            role="assistant",
            content="".join(content_parts),
            tool_calls=None,
            created_at=str(session.last_activity_at),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}",
        )


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
) -> ChatHistoryResponse:
    """Get chat history for a session.

    Retrieves conversation history from PostgreSQL checkpointer.
    """
    # Get session
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

    try:
        # Create checkpointer and retrieve state
        from agent_platform.agent.factory import create_checkpointer
        from langchain_core.messages import AIMessage, HumanMessage

        checkpointer = await create_checkpointer()

        config = {"configurable": {"thread_id": session.thread_id or str(session.id)}}
        state = await checkpointer.aget(config)

        if not state or "messages" not in state:
            return ChatHistoryResponse(
                session_id=str(session_id),
                messages=[],
                total=0,
            )

        # Convert messages to response format
        messages = []
        for msg in state["messages"][-limit:]:
            if isinstance(msg, (HumanMessage, AIMessage)):
                messages.append(
                    ChatMessageResponse(
                        id=str(session.id),
                        role="user" if isinstance(msg, HumanMessage) else "assistant",
                        content=msg.content,
                        tool_calls=None,
                        created_at=str(session.last_activity_at),
                    )
                )

        return ChatHistoryResponse(
            session_id=str(session_id),
            messages=messages,
            total=len(messages),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve history: {str(e)}",
        )


@router.post("/clear")
async def clear_chat_history(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Clear chat history for a session.

    This resets the conversation thread while keeping the session.
    """
    # Get session
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

    try:
        # Generate new thread_id
        import uuid
        session.thread_id = f"user_{current_user.id}_session_{uuid.uuid4()}"
        session.message_count = 0
        session.token_usage = {"input": 0, "output": 0, "total": 0}

        await db.commit()

        return {
            "message": "Chat history cleared",
            "session_id": str(session_id),
            "new_thread_id": session.thread_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear history: {str(e)}",
        )
