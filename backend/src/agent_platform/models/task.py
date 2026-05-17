"""Task model for async task scheduling.

This module defines the Task model for managing async tasks
with Redis Streams based task queue.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.session import Session
    from agent_platform.models.task_event import TaskEvent
    from agent_platform.models.user import User


class TaskType(str, Enum):
    """Task type enum."""

    SYNC = "sync"
    ASYNC = "async"
    SCHEDULED = "scheduled"
    RECURRING = "recurring"


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Task priority enum.

    Lower values = higher priority.
    """

    URGENT = 0
    NORMAL = 1
    BACKGROUND = 2


class Task(Base):
    """Task model for async task scheduling.

    Represents a task that can be executed synchronously or asynchronously
    via the Redis Streams based task queue.
    """

    __tablename__ = "tasks"

    # Primary key
    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    user_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Task configuration
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskType.ASYNC,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskStatus.PENDING,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=TaskPriority.NORMAL,
        index=True,
    )

    # Progress tracking
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # LangGraph integration
    thread_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Results
    result_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    token_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Additional metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Execution plan for task runtime
    execution_plan: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Parent task for subtask support
    parent_task_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Redis message ID (for tracking in queue)
    redis_message_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")
    session: Mapped["Session"] = relationship("Session", back_populates="tasks")
    parent_task: Mapped[Optional["Task"]] = relationship(
        "Task",
        remote_side="Task.id",
        back_populates="subtasks",
    )
    subtasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="parent_task",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["TaskEvent"]] = relationship(
        "TaskEvent",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskEvent.created_at",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        """Check if task is in an active state."""
        return self.status in (
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
            TaskStatus.RUNNING,
            TaskStatus.WAITING_HITL,
        )

    @property
    def is_cancellable(self) -> bool:
        """Check if task can be cancelled."""
        return self.status in (
            TaskStatus.PENDING,
            TaskStatus.QUEUED,
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate task duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return None

    def update_progress(self, progress: int) -> None:
        """Update task progress.

        Args:
            progress: Progress value between 0 and 100
        """
        self.progress = max(0, min(100, progress))

    def mark_queued(self) -> None:
        """Mark task as queued."""
        self.status = TaskStatus.QUEUED

    def mark_running(self) -> None:
        """Mark task as running."""
        self.status = TaskStatus.RUNNING
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc)

    def mark_waiting_hitl(self) -> None:
        """Mark task as waiting for HITL."""
        self.status = TaskStatus.WAITING_HITL

    def mark_completed(self, result_summary: Optional[str] = None) -> None:
        """Mark task as completed.

        Args:
            result_summary: Optional summary of results
        """
        self.status = TaskStatus.COMPLETED
        self.progress = 100
        self.completed_at = datetime.now(timezone.utc)
        if result_summary:
            self.result_summary = result_summary

    def mark_failed(self, error_message: str) -> None:
        """Mark task as failed.

        Args:
            error_message: Error message explaining the failure
        """
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.completed_at = datetime.now(timezone.utc)

    def mark_cancelled(self) -> None:
        """Mark task as cancelled."""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Convert task to dictionary representation."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "org_id": str(self.org_id),
            "session_id": str(self.session_id),
            "type": self.type,
            "status": self.status,
            "prompt": self.prompt,
            "priority": self.priority,
            "progress": self.progress,
            "thread_id": self.thread_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "token_used": self.token_used,
            "metadata": self.extra_metadata,
            "execution_plan": self.execution_plan,
            "parent_task_id": str(self.parent_task_id) if self.parent_task_id else None,
        }

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, status={self.status}, type={self.type})>"
