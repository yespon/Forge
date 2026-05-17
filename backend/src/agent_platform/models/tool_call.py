"""Tool call and result models for standardized tool execution.

This module provides standardized data models for tool calls and their results,
enabling consistent handling across the Tool Gateway and audit logging.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class ToolCallStatus(str, Enum):
    """Tool call execution status."""

    PENDING = "pending"
    APPROVAL_REQUIRED = "approval_required"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class ToolCall:
    """Standardized tool call representation.

    This dataclass provides a consistent format for representing
    tool invocations across the system.
    """

    tool_name: str
    tool_input: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    call_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: Optional[str] = None
    task_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert tool call to dictionary."""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "task_id": self.task_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolCall":
        """Create tool call from dictionary."""
        return cls(
            call_id=data.get("call_id", str(uuid4())),
            tool_name=data["tool_name"],
            tool_input=data.get("tool_input", {}),
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(),
            session_id=data.get("session_id"),
            task_id=data.get("task_id"),
        )


@dataclass
class ToolResult:
    """Standardized tool execution result.

    This dataclass provides a consistent format for representing
    tool execution results across the system.
    """

    success: bool
    output: Any = None
    execution_time_ms: int = 0
    error: Optional[str] = None
    call_id: Optional[str] = None
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set status based on success after initialization."""
        if isinstance(self.status, str):
            self.status = ToolCallStatus(self.status)
        if self.error and self.success:
            self.success = False
            self.status = ToolCallStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        """Convert tool result to dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "call_id": self.call_id,
            "status": self.status.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolResult":
        """Create tool result from dictionary."""
        return cls(
            success=data.get("success", False),
            output=data.get("output"),
            execution_time_ms=data.get("execution_time_ms", 0),
            error=data.get("error"),
            call_id=data.get("call_id"),
            status=ToolCallStatus(data.get("status", "success")),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def success_result(
        cls,
        output: Any,
        execution_time_ms: int = 0,
        call_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create a successful tool result."""
        return cls(
            success=True,
            output=output,
            execution_time_ms=execution_time_ms,
            call_id=call_id,
            status=ToolCallStatus.SUCCESS,
            metadata=metadata or {},
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        execution_time_ms: int = 0,
        call_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> "ToolResult":
        """Create an error tool result."""
        return cls(
            success=False,
            output=None,
            execution_time_ms=execution_time_ms,
            error=error,
            call_id=call_id,
            status=ToolCallStatus.ERROR,
            metadata=metadata or {},
        )


@dataclass
class HITLCheckResult:
    """HITL check result for tool calls.

    This dataclass represents the result of checking HITL rules
    for a tool call.
    """

    requires_approval: bool
    risk_level: Optional[str] = None
    matched_rule: Optional[str] = None
    description: Optional[str] = None
    strategy: Optional[str] = None
    min_approvals_required: int = 1
    approval_request_id: Optional[str] = None
    matched_patterns: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert HITL check result to dictionary."""
        return {
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "matched_rule": self.matched_rule,
            "description": self.description,
            "strategy": self.strategy,
            "min_approvals_required": self.min_approvals_required,
            "approval_request_id": self.approval_request_id,
            "matched_patterns": self.matched_patterns,
        }

    @classmethod
    def no_approval_required(cls) -> "HITLCheckResult":
        """Create a result indicating no approval is required."""
        return cls(requires_approval=False)

    @classmethod
    def from_rules_engine_result(cls, result: dict[str, Any]) -> "HITLCheckResult":
        """Create from HITL rules engine result."""
        return cls(
            requires_approval=result.get("requires_approval", False),
            risk_level=result.get("risk_level"),
            matched_rule=result.get("matched_rule"),
            description=result.get("description"),
            strategy=result.get("strategy"),
            min_approvals_required=result.get("min_approvals_required", 1),
            matched_patterns=result.get("matched_patterns"),
        )


class HITLInterrupt(Exception):
    """Exception raised when HITL approval is required.

    This exception is used to interrupt tool execution and
    request human approval before continuing.
    """

    def __init__(
        self,
        hitl_result: HITLCheckResult,
        approval_request_id: Optional[str] = None,
        message: Optional[str] = None,
    ):
        self.hitl_result = hitl_result
        self.approval_request_id = approval_request_id
        self.message = message or f"HITL approval required: {hitl_result.description}"
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert interrupt to dictionary."""
        return {
            "type": "hitl_interrupt",
            "message": self.message,
            "hitl_result": self.hitl_result.to_dict(),
            "approval_request_id": self.approval_request_id,
        }
