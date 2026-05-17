"""Skill model for the Skill-based tool system."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.user import User


class SkillVisibility(str, Enum):
    """Skill visibility enum."""

    BUILTIN = "builtin"
    ORG = "org"
    PRIVATE = "private"
    PUBLIC = "public"


class Skill(Base):
    """Skill model.

    Represents a skill that provides tools to agents.
    Skills can be builtin (system-provided) or custom (user-created).
    """

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Skill metadata
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="0.1.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Visibility determines who can access the skill
    visibility: Mapped[str] = mapped_column(
        String(20),
        default=SkillVisibility.PRIVATE,
        nullable=False,
    )

    # Manifest stores the skill.yaml content as JSON
    manifest: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Path to the skill directory (for builtin skills)
    # e.g., "skills/builtin/file_ops"
    source_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Ownership
    # For builtin skills, owner_id is None
    owner_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    org_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Skill flags
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    is_restricted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Restriction configuration (stored as JSON)
    # e.g., {"default_enabled": false, "allowed_roles": ["platform_admin", "org_admin"]}
    restrictions: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    # Relationships
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="skills")
    grants: Mapped[list["SkillGrant"]] = relationship(
        "SkillGrant",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("name", "version", name="uix_skill_name_version"),
    )

    @property
    def is_enabled_by_default(self) -> bool:
        """Check if skill is enabled by default."""
        if not self.is_restricted:
            return True
        return self.restrictions.get("default_enabled", False)

    def get_allowed_roles(self) -> list[str]:
        """Get list of roles allowed to use this skill."""
        if not self.is_restricted:
            return []
        return self.restrictions.get("allowed_roles", [])

    def can_be_used_by(self, user: "User") -> bool:
        """Check if a user can use this skill based on restrictions."""
        if not self.is_active:
            return False

        if not self.is_restricted:
            return True

        allowed_roles = self.get_allowed_roles()
        if not allowed_roles:
            return True

        return user.role in allowed_roles


class SkillGrant(Base):
    """Skill grant model.

    Represents an explicit grant of a skill to a user or session.
    Used for restricted skills that require authorization.
    """

    __tablename__ = "skill_grants"

    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    skill_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Grant can be for a user or a session
    user_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Grant metadata
    granted_by: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Optional expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    skill: Mapped["Skill"] = relationship("Skill", back_populates="grants")

    @property
    def is_expired(self) -> bool:
        """Check if the grant has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
