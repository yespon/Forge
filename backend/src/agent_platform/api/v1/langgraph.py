"""LangGraph-compatible Gateway API for Forge.

Provides DeerFlow/LangGraph protocol compatibility so that:
- DeerFlow IM channels can connect directly to Forge
- LangGraph Studio / LangSmith can trace Forge runs
- claude-to-deerflow skill works with Forge
- Any LangGraph-compatible client can interact with Forge

Endpoints follow the LangGraph Platform API spec:
- POST   /threads                    → Create thread (maps to Forge Session)
- GET    /threads/{id}               → Get thread state
- DELETE /threads/{id}               → Delete thread
- POST   /threads/{id}/runs          → Create run (maps to Forge Task)
- POST   /threads/{id}/runs/stream   → Stream run (SSE)
- GET    /threads/{id}/runs/{run_id} → Get run status
- POST   /threads/{id}/runs/{run_id}/cancel → Cancel run
- GET    /assistants                 → List assistants
- GET    /assistants/{id}            → Get assistant info
"""

import json
import logging
import time
from typing import Annotated, Any, AsyncGenerator, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import get_current_user
from agent_platform.database import get_db
from agent_platform.models.session import Session, SessionStatus
from agent_platform.models.task import Task, TaskStatus, TaskType
from agent_platform.models.user import User
from agent_platform.services.task_runtime import TaskRuntime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/langgraph", tags=["langgraph"])


# ============================================================================
# Request / Response Schemas (LangGraph Protocol)
# ============================================================================


class ThreadCreate(BaseModel):
    """Create thread request."""
    metadata: dict = Field(default_factory=dict)


class ThreadResponse(BaseModel):
    """Thread response (LangGraph format)."""
    thread_id: str
    metadata: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str
    status: str = "idle"


class RunCreate(BaseModel):
    """Create run request."""
    assistant_id: str = "lead_agent"
    input: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    stream_mode: list[str] = Field(default_factory=lambda: ["values"])
    multitask_strategy: str = "reject"


class RunResponse(BaseModel):
    """Run response."""
    run_id: str
    thread_id: str
    assistant_id: str
    status: str  # pending, running, success, error, interrupted
    created_at: str
    updated_at: str
    metadata: dict = Field(default_factory=dict)


class AssistantResponse(BaseModel):
    """Assistant response."""
    assistant_id: str
    name: str
    description: str = ""
    metadata: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    version: int = 1


# ============================================================================
# Helpers
# ============================================================================


def _task_status_to_run_status(task_status: str) -> str:
    """Map Forge TaskStatus to LangGraph run status."""
    mapping = {
        TaskStatus.PENDING: "pending",
        TaskStatus.RUNNING: "running",
        TaskStatus.COMPLETED: "success",
        TaskStatus.FAILED: "error",
        TaskStatus.CANCELLED: "cancelled",
        TaskStatus.WAITING_APPROVAL: "interrupted",
    }
    return mapping.get(task_status, "pending")


def _session_to_thread(session: Session) -> dict:
    """Convert Forge Session to LangGraph Thread response."""
    return {
        "thread_id": str(session.id),
        "metadata": {
            "name": session.name,
            "model": session.model,
            "message_count": session.message_count,
            **(session.settings or {}),
        },
        "created_at": session.created_at.isoformat() if session.created_at else "",
        "updated_at": session.updated_at.isoformat() if session.updated_at else "",
        "status": "idle" if session.status == SessionStatus.ACTIVE else session.status,
    }


def _task_to_run(task: Task) -> dict:
    """Convert Forge Task to LangGraph Run response."""
    return {
        "run_id": str(task.id),
        "thread_id": str(task.session_id),
        "assistant_id": "lead_agent",
        "status": _task_status_to_run_status(task.status),
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "updated_at": task.updated_at.isoformat() if hasattr(task, "updated_at") and task.updated_at else "",
        "metadata": {
            "prompt": task.prompt,
            "progress": task.progress,
        },
    }


# ============================================================================
# Thread Endpoints
# ============================================================================


@router.post("/threads", response_model=ThreadResponse)
async def create_thread(
    request: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new thread (LangGraph-compatible).

    Maps to creating a Forge Session internally.
    """
    name = request.metadata.get("name", "LangGraph Thread")
    model = request.metadata.get("model", "claude-sonnet-4-6")

    session = Session(
        user_id=current_user.id,
        name=name,
        model=model,
        settings=request.metadata,
        tools=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    return _session_to_thread(session)


@router.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get thread state."""
    result = await db.execute(
        select(Session).where(
            Session.id == thread_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    return _session_to_thread(session)


@router.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a thread and its associated data."""
    result = await db.execute(
        select(Session).where(
            Session.id == thread_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    session.status = SessionStatus.TERMINATED
    await db.commit()

    return {"status": "ok"}


# ============================================================================
# Run Endpoints
# ============================================================================


@router.post("/threads/{thread_id}/runs", response_model=RunResponse)
async def create_run(
    thread_id: UUID,
    request: RunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a run (non-streaming).

    Maps to creating and executing a Forge Task.
    """
    # Validate thread
    result = await db.execute(
        select(Session).where(
            Session.id == thread_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Extract message from input
    messages = request.input.get("messages", [])
    prompt = ""
    if messages:
        last_msg = messages[-1]
        prompt = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
    if not prompt:
        prompt = request.input.get("message", request.input.get("query", ""))

    if not prompt:
        raise HTTPException(status_code=400, detail="No input message provided")

    # Apply context config
    context = request.config.get("configurable", {}).get("context", {})
    enable_hitl = context.get("hitl_enabled", True)

    # Create task
    runtime = TaskRuntime(db=db)
    task = await runtime.create_task(
        session_id=session.id,
        user_id=current_user.id,
        prompt=prompt,
        task_type=TaskType.ASYNC,
        org_id=current_user.org_id,
        enable_hitl=enable_hitl,
    )

    return _task_to_run(task)


@router.post("/threads/{thread_id}/runs/stream")
async def stream_run(
    thread_id: UUID,
    request: RunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a run and stream results (LangGraph SSE protocol).

    Streams events in LangGraph format:
    - event: metadata      (run metadata)
    - event: messages      (AI message chunks)
    - event: values        (state snapshots)
    - event: end           (run completed)

    Stream modes supported:
    - "messages-tuple": Stream individual message chunks
    - "values": Stream full state after each step
    """
    # Validate thread
    result = await db.execute(
        select(Session).where(
            Session.id == thread_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Extract message
    messages = request.input.get("messages", [])
    prompt = ""
    if messages:
        last_msg = messages[-1]
        prompt = last_msg.get("content", "") if isinstance(last_msg, dict) else str(last_msg)
    if not prompt:
        prompt = request.input.get("message", request.input.get("query", ""))

    if not prompt:
        raise HTTPException(status_code=400, detail="No input message provided")

    # Apply config
    context = request.config.get("configurable", {}).get("context", {})
    enable_hitl = context.get("hitl_enabled", True)
    stream_modes = set(request.stream_mode or ["values"])

    # Create task
    runtime = TaskRuntime(db=db)
    task = await runtime.create_task(
        session_id=session.id,
        user_id=current_user.id,
        prompt=prompt,
        task_type=TaskType.SYNC,
        org_id=current_user.org_id,
        enable_hitl=enable_hitl,
    )

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate LangGraph-compatible SSE stream."""
        run_id = str(task.id)

        # Emit metadata event
        yield _sse_event("metadata", {
            "run_id": run_id,
            "thread_id": str(thread_id),
            "assistant_id": request.assistant_id,
        })

        accumulated_content = ""

        try:
            async for event in runtime.execute_task(task.id):
                if event.type == "content" and event.content:
                    accumulated_content += event.content

                    # Stream as messages-tuple if requested
                    if "messages-tuple" in stream_modes or "messages" in stream_modes:
                        yield _sse_event("messages", [
                            {
                                "type": "ai",
                                "content": event.content,
                                "id": run_id,
                            }
                        ])

                elif event.type == "tool_call":
                    if "messages-tuple" in stream_modes or "messages" in stream_modes:
                        yield _sse_event("messages", [
                            {
                                "type": "ai",
                                "content": "",
                                "tool_calls": [{
                                    "name": event.tool_name,
                                    "args": event.tool_input or {},
                                    "id": str(uuid4()),
                                }],
                                "id": run_id,
                            }
                        ])

                elif event.type == "tool_result":
                    if "messages-tuple" in stream_modes or "messages" in stream_modes:
                        yield _sse_event("messages", [
                            {
                                "type": "tool",
                                "content": event.tool_output or "",
                                "name": event.tool_name,
                                "id": str(uuid4()),
                            }
                        ])

                elif event.type == "hitl_required":
                    # Emit interrupt event
                    yield _sse_event("messages", [
                        {
                            "type": "ai",
                            "content": "[Awaiting human approval]",
                            "id": run_id,
                            "interrupt": event.metadata,
                        }
                    ])

                elif event.type == "error":
                    yield _sse_event("error", {
                        "message": event.error or "Unknown error",
                    })

                elif event.type == "done":
                    pass  # handled below

            # Emit values snapshot if requested
            if "values" in stream_modes:
                yield _sse_event("values", {
                    "messages": [
                        {"type": "human", "content": prompt},
                        {"type": "ai", "content": accumulated_content},
                    ],
                })

        except Exception as e:
            logger.exception("Stream run error: %s", e)
            yield _sse_event("error", {"message": str(e)})

        # Always emit end event
        yield _sse_event("end", None)

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    thread_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get run (task) status."""
    result = await db.execute(
        select(Task).where(
            Task.id == str(run_id),
            Task.session_id == str(thread_id),
            Task.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Run not found")

    return _task_to_run(task)


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: UUID,
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running task."""
    runtime = TaskRuntime(db=db)
    success = await runtime.cancel_task(str(run_id))
    if not success:
        raise HTTPException(status_code=404, detail="Run not found or cannot be cancelled")

    return {"status": "ok"}


# ============================================================================
# Assistant Endpoints
# ============================================================================


@router.get("/assistants")
async def list_assistants(
    current_user: User = Depends(get_current_user),
):
    """List available assistants.

    Maps to Forge's available models + integration config.
    """
    from agent_platform.integration import get_available_models

    models = get_available_models()

    assistants = [
        {
            "assistant_id": "lead_agent",
            "name": "Lead Agent",
            "description": "Default Forge agent with full capabilities",
            "metadata": {"models": [m["name"] for m in models]},
            "config": {},
            "version": 1,
        }
    ]

    # Add model-specific assistants
    for model in models:
        assistants.append({
            "assistant_id": f"agent_{model['name'].replace('-', '_').replace('.', '_')}",
            "name": model.get("display_name", model["name"]),
            "description": f"Agent using {model['name']}",
            "metadata": {
                "model": model["name"],
                "supports_thinking": model.get("supports_thinking", False),
                "supports_vision": model.get("supports_vision", False),
            },
            "config": {"model": model["name"]},
            "version": 1,
        })

    return assistants


@router.get("/assistants/{assistant_id}")
async def get_assistant(
    assistant_id: str,
    current_user: User = Depends(get_current_user),
):
    """Get assistant details."""
    assistants = await list_assistants(current_user)
    for a in assistants:
        if a["assistant_id"] == assistant_id:
            return a
    raise HTTPException(status_code=404, detail="Assistant not found")


# ============================================================================
# Utility
# ============================================================================


def _sse_event(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event in LangGraph protocol format."""
    payload = json.dumps(data) if data is not None else ""
    return f"event: {event_type}\ndata: {payload}\n\n"
