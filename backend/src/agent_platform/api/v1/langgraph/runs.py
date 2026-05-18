"""LangGraph-compatible Runs API.

Implements the LangGraph Platform run execution endpoints:
- POST   /threads/{thread_id}/runs          — Create a run (blocking)
- POST   /threads/{thread_id}/runs/stream   — Create a run (SSE streaming)
- GET    /threads/{thread_id}/runs           — List runs for a thread
- GET    /threads/{thread_id}/runs/{run_id}  — Get run status
- POST   /threads/{thread_id}/runs/{run_id}/cancel — Cancel a run
- POST   /runs/stream                       — Stateless streaming run
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.database import get_db
from agent_platform.auth.dependencies import get_current_user

router = APIRouter(tags=["langgraph-runs"])


# --- Request/Response schemas ---


class RunCreate(BaseModel):
    """Request body for creating a run."""

    assistant_id: str = "lead_agent"
    input: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    stream_mode: list[str] = Field(default_factory=lambda: ["values"])
    multitask_strategy: str = "reject"  # "reject" | "rollback" | "interrupt" | "enqueue"


class RunResponse(BaseModel):
    run_id: str
    thread_id: str
    assistant_id: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class RunOutput(BaseModel):
    run_id: str
    thread_id: str
    status: str
    output: Optional[dict[str, Any]] = None


# --- Helper ---


async def _execute_run_stream(
    thread_id: str,
    body: RunCreate,
    user: Any,
    db: AsyncSession,
):
    """Execute a run and yield SSE events."""
    from langchain_core.messages import HumanMessage

    from agent_platform.integration.agent_factory import create_forge_agent
    from agent_platform.runtime.checkpointer import get_checkpointer

    run_id = str(uuid4())
    checkpointer = get_checkpointer()

    # Build agent with checkpointer
    agent = create_forge_agent(
        model_name=body.config.get("model_name", "claude-sonnet-4-6"),
        system_prompt=body.config.get("system_prompt"),
        session=None,
        user=user,
        db=db,
        hitl_enabled=body.config.get("enable_hitl", False),
    )

    # Prepare input
    input_data = body.input or {}
    messages = input_data.get("messages", [])
    if not messages and isinstance(input_data.get("message"), str):
        messages = [HumanMessage(content=input_data["message"])]
    elif messages and isinstance(messages[0], dict):
        messages = [HumanMessage(content=m.get("content", "")) for m in messages]

    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        },
        "recursion_limit": body.config.get("recursion_limit", 100),
    }

    # Emit metadata event
    yield _sse_event("metadata", {"run_id": run_id})

    try:
        async for chunk in agent.astream(
            {"messages": messages},
            config=config,
            stream_mode="updates",
        ):
            if isinstance(chunk, dict):
                for node_name, node_data in chunk.items():
                    if not isinstance(node_data, dict):
                        continue

                    # Stream based on stream_mode
                    if "values" in body.stream_mode:
                        yield _sse_event("values", {
                            "node": node_name,
                            "values": _serialize_node_data(node_data),
                        })

                    if "messages-tuple" in body.stream_mode:
                        node_messages = node_data.get("messages", [])
                        for msg in node_messages:
                            yield _sse_event("messages/partial", [
                                _serialize_message(msg)
                            ])

        yield _sse_event("end", {"run_id": run_id, "status": "success"})

    except Exception as e:
        yield _sse_event("error", {"message": str(e), "run_id": run_id})


def _sse_event(event: str, data: Any) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _serialize_node_data(data: dict) -> dict:
    """Serialize node output data for SSE transmission."""
    result = {}
    for key, value in data.items():
        if key == "messages":
            result[key] = [_serialize_message(m) for m in value]
        else:
            result[key] = value
    return result


def _serialize_message(msg: Any) -> dict:
    """Serialize a LangChain message to dict."""
    return {
        "type": getattr(msg, "type", "unknown"),
        "content": getattr(msg, "content", ""),
        "id": getattr(msg, "id", None),
        "name": getattr(msg, "name", None),
        "tool_calls": getattr(msg, "tool_calls", None),
    }


# --- Thread-scoped Run Endpoints ---


@router.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(
    thread_id: str,
    body: RunCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a streaming run (SSE). Primary endpoint for LangGraph clients."""
    return StreamingResponse(
        _execute_run_stream(thread_id, body, user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/threads/{thread_id}/runs", response_model=RunOutput)
async def create_run_wait(
    thread_id: str,
    body: RunCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a run and wait for completion (blocking)."""
    from langchain_core.messages import HumanMessage

    from agent_platform.integration.agent_factory import create_forge_agent
    from agent_platform.runtime.checkpointer import get_checkpointer

    run_id = str(uuid4())

    agent = create_forge_agent(
        model_name=body.config.get("model_name", "claude-sonnet-4-6"),
        system_prompt=body.config.get("system_prompt"),
        session=None,
        user=user,
        db=db,
        hitl_enabled=body.config.get("enable_hitl", False),
    )

    input_data = body.input or {}
    messages = input_data.get("messages", [])
    if not messages and isinstance(input_data.get("message"), str):
        messages = [HumanMessage(content=input_data["message"])]
    elif messages and isinstance(messages[0], dict):
        messages = [HumanMessage(content=m.get("content", "")) for m in messages]

    config = {
        "configurable": {"thread_id": thread_id, "checkpoint_ns": ""},
        "recursion_limit": body.config.get("recursion_limit", 100),
    }

    result = await agent.ainvoke({"messages": messages}, config=config)

    return RunOutput(
        run_id=run_id,
        thread_id=thread_id,
        status="success",
        output={"messages": [_serialize_message(m) for m in result.get("messages", [])]},
    )


@router.get("/threads/{thread_id}/runs", response_model=list[RunResponse])
async def list_runs(
    thread_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List runs for a thread."""
    from sqlalchemy import select

    from agent_platform.models.task import Task

    result = await db.execute(
        select(Task)
        .where(Task.session_id == thread_id, Task.user_id == user.id)
        .order_by(Task.created_at.desc())
        .limit(50)
    )
    tasks = result.scalars().all()

    return [
        RunResponse(
            run_id=str(t.id),
            thread_id=thread_id,
            assistant_id="lead_agent",
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            metadata={},
            created_at=t.created_at.isoformat() if t.created_at else None,
        )
        for t in tasks
    ]


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=RunResponse)
async def get_run(
    thread_id: str,
    run_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get run status."""
    from sqlalchemy import select

    from agent_platform.models.task import Task

    result = await db.execute(
        select(Task).where(Task.id == run_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        run_id=str(task.id),
        thread_id=thread_id,
        assistant_id="lead_agent",
        status=task.status.value if hasattr(task.status, "value") else str(task.status),
        metadata={},
        created_at=task.created_at.isoformat() if task.created_at else None,
    )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: str,
    run_id: str,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running run."""
    from sqlalchemy import select

    from agent_platform.models.task import Task, TaskStatus

    result = await db.execute(
        select(Task).where(Task.id == run_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Run not found")

    task.status = TaskStatus.CANCELLED
    await db.commit()
    return {"status": "ok"}


# --- Stateless Run Endpoint ---


@router.post("/runs/stream")
async def create_stateless_run_stream(
    body: RunCreate,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a stateless streaming run (no thread persistence)."""
    thread_id = str(uuid4())
    return StreamingResponse(
        _execute_run_stream(thread_id, body, user, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
