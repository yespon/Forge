"""Unified runtime event models."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


RuntimeEventType = Literal[
    "run_started",
    "message_delta",
    "message_completed",
    "tool_call_requested",
    "tool_call_completed",
    "approval_required",
    "artifact_created",
    "run_waiting",
    "run_resumed",
    "run_completed",
    "run_failed",
]


class RuntimeEvent(BaseModel):
    """Standard event emitted by runtime kernels."""

    type: RuntimeEventType
    run_id: str
    task_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


def make_runtime_event(
    event_type: RuntimeEventType,
    *,
    run_id: str,
    task_id: str,
    **data: Any,
) -> RuntimeEvent:
    """Helper to construct runtime events consistently."""
    return RuntimeEvent(type=event_type, run_id=run_id, task_id=task_id, data=data)
