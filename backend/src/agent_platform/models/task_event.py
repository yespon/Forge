"""Task event model for tracking task execution.

This module defines the TaskEvent model for storing events
during task execution in the Task Runtime.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.task import Task


class TaskEventType(str, Enum):
    """Task event type enum."""

    # Lifecycle events
    CREATED = "created"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Planning events
    SKILL_RESOLVED = "skill_resolved"
    PLAN_CREATED = "plan_created"

    # Execution events
    AGENT_CREATED = "agent_created"
    CONTENT_CHUNK = "content_chunk"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    INTERRUPT = "interrupt"
    RESUMED = "resumed"

    # Progress events
    PROGRESS = "progress"
    STATUS_CHANGED = "status_changed"


class TaskEvent(Base):
    """Task event model.

    Represents an event during task execution. Events are stored
    for debugging, monitoring, and audit purposes.
    """

    __tablename__ = "task_events"

    # Primary key
    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign key to task
    task_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event type
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Event data (flexible JSON)
    data: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Optional message
    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="events")

    def to_dict(self) -> dict:
        """Convert event to dictionary representation."""
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "type": self.type,
            "data": self.data,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<TaskEvent(id={self.id}, type={self.type}, task_id={self.task_id})>"
