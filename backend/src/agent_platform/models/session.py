"""Session model for Agent Runtime."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

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
    from agent_platform.models.approval import ApprovalRequest
    from agent_platform.models.task import Task
    from agent_platform.models.user import User


class SessionStatus(str, Enum):
    """Session status enum."""

    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


class Session(Base):
    """Agent session model.

    Represents a running agent instance with its configuration and state.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session configuration
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=SessionStatus.ACTIVE,
        nullable=False,
    )

    # Agent configuration
    model: Mapped[str] = mapped_column(
        String(50),
        default="claude-sonnet-4-6",
        nullable=False,
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tools: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    settings: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Runtime state (stored in PostgreSQL via checkpointer)
    thread_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    # Usage tracking
    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    token_usage: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {"input": 0, "output": 0, "total": 0},
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    terminated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.ACTIVE

    @property
    def is_terminated(self) -> bool:
        """Check if session is terminated."""
        return self.status == SessionStatus.TERMINATED

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = datetime.now()

    def increment_message_count(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        """Increment message count and token usage."""
        self.message_count += 1
        self.token_usage["input"] += input_tokens
        self.token_usage["output"] += output_tokens
        self.token_usage["total"] += input_tokens + output_tokens
        self.touch()
