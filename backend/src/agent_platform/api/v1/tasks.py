"""Task management endpoints."""

import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.session import Session
from agent_platform.models.artifact import Artifact
from agent_platform.models.task import Task, TaskPriority, TaskStatus, TaskType
from agent_platform.models.task_event import TaskEvent

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    """Create task request."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    session_id: UUID
    type: TaskType = TaskType.ASYNC
    priority: TaskPriority = TaskPriority.NORMAL


class ScheduledTaskCreate(BaseModel):
    """Create scheduled task request."""

    prompt: str = Field(..., min_length=1, max_length=10000)
    session_id: UUID
    cron: str = Field(..., description="Cron expression, e.g. '0 9 * * 1-5'")
    timezone: str = Field(default="UTC")
    enabled: bool = Field(default=True)


class TaskResponse(BaseModel):
    """Task response."""

    id: str
    user_id: str
    org_id: str
    session_id: str
    type: str
    status: str
    prompt: str
    priority: int
    progress: int
    stream_url: str
    artifacts_url: str
    created_at: str | None
    started_at: str | None
    completed_at: str | None
    result_summary: str | None
    error_message: str | None
    redis_message_id: str | None


class TaskListResponse(BaseModel):
    """Task list response."""

    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


class ArtifactResponse(BaseModel):
    """Single artifact."""

    id: str
    name: str
    mime_type: str
    size: int
    artifact_type: str
    created_at: str | None
    url: str


class TaskArtifactsResponse(BaseModel):
    """Task artifacts response."""

    items: list[ArtifactResponse]


class TaskResumeRequest(BaseModel):
    """Resume a paused HITL task."""

    decision: str = Field(..., pattern="^(approved|rejected)$")
    reason: str | None = None


class TaskEventResponse(BaseModel):
    """Single task event."""

    id: str
    type: str
    data: dict[str, Any]
    message: str | None
    created_at: str | None


class TaskEventsListResponse(BaseModel):
    """Task events list."""

    items: list[TaskEventResponse]
    total: int


def task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        user_id=str(task.user_id),
        org_id=str(task.org_id),
        session_id=str(task.session_id),
        type=task.type.value if hasattr(task.type, 'value') else str(task.type),
        status=task.status.value if hasattr(task.status, 'value') else str(task.status),
        prompt=task.prompt,
        priority=int(task.priority),
        progress=task.progress,
        stream_url=f"/api/v1/tasks/{task.id}/stream",
        artifacts_url=f"/api/v1/tasks/{task.id}/artifacts",
        created_at=task.created_at.isoformat() if task.created_at else None,
        started_at=task.started_at.isoformat() if task.started_at else None,
        completed_at=task.completed_at.isoformat() if task.completed_at else None,
        result_summary=task.result_summary,
        error_message=task.error_message,
        redis_message_id=task.redis_message_id,
    )


async def get_user_task(db: AsyncSession, task_id: UUID, user_id: UUID) -> Task:
    result = await db.execute(
        select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    current_user: CurrentUser,
    request: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Create a task."""
    result = await db.execute(
        select(Session).where(
            Session.id == request.session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    task = Task(
        user_id=current_user.id,
        org_id=current_user.org_id,
        session_id=session.id,
        type=request.type,
        status=TaskStatus.PENDING,
        prompt=request.prompt,
        priority=request.priority,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return task_response(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
) -> TaskListResponse:
    """List tasks for the current user."""
    query = select(Task).where(Task.user_id == current_user.id)
    count_query = select(func.count()).where(Task.user_id == current_user.id)
    if task_status:
        query = query.where(Task.status == task_status)
        count_query = count_query.where(Task.status == task_status)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tasks = result.scalars().all()

    return TaskListResponse(
        items=[task_response(task) for task in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/scheduled", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    current_user: CurrentUser,
    request: ScheduledTaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Create a scheduled or recurring task."""
    result = await db.execute(
        select(Session).where(
            Session.id == request.session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    task = Task(
        user_id=current_user.id,
        org_id=current_user.org_id,
        session_id=session.id,
        type=TaskType.SCHEDULED if not request.cron.startswith("@") else TaskType.RECURRING,
        status=TaskStatus.PENDING,
        prompt=request.prompt,
        priority=TaskPriority.NORMAL,
        extra_metadata={
            "schedule": {
                "cron": request.cron,
                "timezone": request.timezone,
                "enabled": request.enabled,
            }
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    return task_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Get a task by id."""
    task = await get_user_task(db, task_id, current_user.id)
    return task_response(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Cancel a pending or queued task."""
    task = await get_user_task(db, task_id, current_user.id)
    if not task.is_cancellable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task cannot be cancelled",
        )

    task.mark_cancelled()
    await db.commit()
    await db.refresh(task)
    return task_response(task)


@router.get("/{task_id}/stream")
async def stream_task(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Stream task execution events as SSE.

    For running tasks, streams real-time events from TaskRuntime.
    For completed/failed tasks, replays event history.
    """
    task = await get_user_task(db, task_id, current_user.id)

    async def events():
        if task.is_active:
            # Stream live events from TaskRuntime
            from agent_platform.services.task_runtime import TaskRuntime

            runtime = TaskRuntime(db=db)
            async for event in runtime.execute_task(task_id):
                yield f"event: {event.type}\ndata: {json.dumps({'type': event.type, 'content': event.content, 'tool_name': event.tool_name, 'error': event.error, 'metadata': event.metadata})}\n\n"
        else:
            # Replay recorded events for finished tasks
            result = await db.execute(
                select(TaskEvent)
                .where(TaskEvent.task_id == task_id)
                .order_by(TaskEvent.created_at.asc())
            )
            for e in result.scalars().all():
                yield f"event: {e.type}\ndata: {json.dumps({'type': e.type, 'data': e.data or {}, 'message': e.message})}\n\n"

        # Final status
        await db.refresh(task)
        yield f"event: done\ndata: {json.dumps({'status': task.status.value if hasattr(task.status, 'value') else str(task.status), 'progress': task.progress})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/{task_id}/artifacts", response_model=TaskArtifactsResponse)
async def get_task_artifacts(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskArtifactsResponse:
    """Return artifacts produced by a task."""
    await get_user_task(db, task_id, current_user.id)

    result = await db.execute(
        select(Artifact)
        .where(Artifact.task_id == task_id)
        .order_by(Artifact.created_at.asc())
    )
    artifacts = result.scalars().all()

    return TaskArtifactsResponse(
        items=[
            ArtifactResponse(
                id=str(a.id),
                name=a.name,
                mime_type=a.mime_type,
                size=a.size,
                artifact_type=a.artifact_type,
                created_at=a.created_at.isoformat() if a.created_at else None,
                url=f"/api/v1/tasks/{task_id}/artifacts/{a.id}",
            )
            for a in artifacts
        ]
    )


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(
    current_user: CurrentUser,
    task_id: UUID,
    request: TaskResumeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Resume a task that is waiting for HITL approval."""
    task = await get_user_task(db, task_id, current_user.id)

    if task.status != TaskStatus.WAITING_HITL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is not waiting for approval",
        )

    # Store the decision in metadata so the worker can pick it up
    updated = dict(task.extra_metadata or {})
    updated["hitl_decision"] = {
        "decision": request.decision,
        "reason": request.reason,
        "decided_by": str(current_user.id),
    }
    task.extra_metadata = updated

    if request.decision == "rejected":
        task.mark_cancelled()
    else:
        # Re-queue to worker for resumed execution
        task.status = TaskStatus.QUEUED

    await db.commit()
    await db.refresh(task)
    return task_response(task)


@router.get("/{task_id}/events", response_model=TaskEventsListResponse)
async def get_task_events(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> TaskEventsListResponse:
    """Return the event history for a task."""
    # Verify ownership
    await get_user_task(db, task_id, current_user.id)

    count_result = await db.execute(
        select(func.count()).where(TaskEvent.task_id == task_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(TaskEvent)
        .where(TaskEvent.task_id == task_id)
        .order_by(TaskEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()

    return TaskEventsListResponse(
        items=[
            TaskEventResponse(
                id=str(e.id),
                type=str(e.type),
                data=e.data or {},
                message=e.message,
                created_at=e.created_at.isoformat() if e.created_at else None,
            )
            for e in events
        ],
        total=total,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    current_user: CurrentUser,
    task_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a task and its history."""
    task = await get_user_task(db, task_id, current_user.id)
    if task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an active task",
        )
    await db.delete(task)
    await db.commit()
