"""Runtime context models for unified task execution."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class RuntimeContext(BaseModel):
    """Platform-level runtime context passed into kernels."""

    task_id: str
    session_id: Optional[str] = None
    thread_id: str
    user_id: str
    org_id: Optional[str] = None

    runtime_kind: str = "deerflow"
    model_name: str = "claude-sonnet-4-6"
    system_prompt: Optional[str] = None
    input_message: Optional[str] = None

    skill_ids: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    channel: Optional[str] = None
    channel_context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeRun(BaseModel):
    """A concrete runtime execution instance."""

    run_id: str
    task_id: str
    thread_id: str
    kernel: str
    status: str = "created"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeSnapshot(BaseModel):
    """Inspect-able runtime state."""

    run_id: str
    status: str
    current_step: Optional[str] = None
    waiting_reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
