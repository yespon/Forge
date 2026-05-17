"""Audit log model for tracking all tool executions and system actions.

This module provides comprehensive audit logging for compliance and security.
All tool calls, approvals, and important system actions are recorded.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.session import Session
    from agent_platform.models.task import Task
    from agent_platform.models.user import User


class AuditAction(str, Enum):
    """Audit action types."""

    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_DECISION = "approval_decision"
    APPROVAL_ESCALATED = "approval_escalated"
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    SESSION_CREATED = "session_created"
    SESSION_TERMINATED = "session_terminated"


class ResourceType(str, Enum):
    """Resource types for audit logging."""

    TOOL = "tool"
    APPROVAL = "approval"
    TASK = "task"
    SESSION = "session"
    USER = "user"
    ORG = "org"


class AuditLog(Base):
    """Audit log entry for tracking all system actions.

    This model provides an immutable audit trail for compliance,
    security monitoring, and debugging purposes.
    """

    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Actor information
    user_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    org_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Context information
    session_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Detailed information (flexible JSON structure)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Execution result
    success: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Client information
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")
    session: Mapped[Optional["Session"]] = relationship("Session", back_populates="audit_logs")
    task: Mapped[Optional["Task"]] = relationship("Task", back_populates="audit_logs")

    # Composite indexes for common query patterns
    __table_args__ = (
        # Index for time-based queries
        {"sqlite_autoincrement": False},
    )

    @property
    def is_error(self) -> bool:
        """Check if this audit entry represents an error."""
        return self.success is False or self.action == AuditAction.TOOL_ERROR

    def to_dict(self) -> dict[str, Any]:
        """Convert audit log to dictionary representation."""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "user_id": str(self.user_id) if self.user_id else None,
            "org_id": str(self.org_id) if self.org_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "task_id": str(self.task_id) if self.task_id else None,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
        }

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action={self.action}, "
            f"resource_type={self.resource_type}, success={self.success})>"
        )
