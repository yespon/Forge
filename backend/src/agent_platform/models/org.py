"""Organization and team models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.approval import HITLRule
    from agent_platform.models.notification_settings import NotificationSettings
    from agent_platform.models.user import User


class Org(Base):
    """Organization model."""

    __tablename__ = "orgs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    quota: Mapped[dict] = mapped_column(JSON, default=dict)
    billing_info: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="org")
    teams: Mapped[list["Team"]] = relationship("Team", back_populates="org")
    hitl_rules: Mapped[list["HITLRule"]] = relationship(
        "HITLRule",
        back_populates="org",
        cascade="all, delete-orphan",
    )
    notification_settings: Mapped[list["NotificationSettings"]] = relationship(
        "NotificationSettings",
        back_populates="org",
        cascade="all, delete-orphan",
    )


class Team(Base):
    """Team model."""

    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    org_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="teams")
    members: Mapped[list["UserTeam"]] = relationship("UserTeam", back_populates="team")
    hitl_rules: Mapped[list["HITLRule"]] = relationship(
        "HITLRule",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("org_id", "slug"),)


class UserTeam(Base):
    """User-Team association."""

    __tablename__ = "user_teams"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    team_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(20), default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="teams")
    team: Mapped["Team"] = relationship("Team", back_populates="members")
