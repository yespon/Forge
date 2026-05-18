"""Runtime interrupt models."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ApprovalInterrupt(BaseModel):
    """A normalized approval interrupt emitted by runtime kernels."""

    interrupt_id: str
    run_id: str
    task_id: str
    tool_name: str
    risk_level: str = "unknown"
    title: str = "Approval required"
    summary: str = ""
    input_payload: dict[str, Any] = Field(default_factory=dict)
    resumable: bool = True
    timeout_seconds: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
