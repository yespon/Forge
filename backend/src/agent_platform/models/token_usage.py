"""Token usage tracking model.

Stores per-run token consumption for cost monitoring and analytics.
Compatible with DeerFlow's persistence/run/ token usage tracking.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from agent_platform.database import Base


class TokenUsage(Base):
    """Token usage record per run/model invocation.

    Tracks input/output tokens and cost per LLM call within a run.
    Aggregatable by run, thread, user, model, and time range.
    """

    __tablename__ = "token_usage"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Context identifiers
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
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Model info
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Token counts
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Optional cost calculation (in USD cents)
    cost_cents: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Extra metadata (cache hit info, reasoning tokens, etc.)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
