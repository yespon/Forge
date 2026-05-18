"""User feedback model.

Stores thumbs up/down and textual feedback on run outputs.
Compatible with DeerFlow's persistence/feedback/ module.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from agent_platform.database import Base


class Feedback(Base):
    """User feedback on a run or message.

    Supports:
    - Thumbs up/down (score: 1 / -1)
    - Textual feedback (comment)
    - Metadata for fine-grained tracking
    """

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Context
    run_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    task_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Feedback content
    score: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="1 = positive, -1 = negative, 0 = neutral",
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="Feedback category key (e.g., 'accuracy', 'helpfulness')",
    )

    # Extra metadata
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
