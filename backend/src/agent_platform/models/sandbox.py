"""Sandbox persistence model."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

from agent_platform.database import Base


class SandboxRecord(Base):
    """Persistent record of a sandbox container."""

    __tablename__ = "sandboxes"

    id = Column(String(100), primary_key=True)  # container/pod ID
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id"),
        nullable=False,
    )
    template = Column(String(50), nullable=False, default="default")
    image = Column(String(200), nullable=False, default="python:3.12-slim")
    resources = Column(JSONB, nullable=False, default=dict)
    network_policy = Column(JSONB, nullable=True)
    status = Column(String(20), nullable=False, default="creating")
    node_name = Column(String(100), nullable=True)
    pod_ip = Column(INET, nullable=True)
    volume_name = Column(String(200), nullable=True)
    volume_size = Column(String(20), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    terminated_at = Column(DateTime(timezone=True), nullable=True)

    def mark_running(self):
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        self.last_active_at = datetime.now(timezone.utc)

    def mark_terminated(self):
        self.status = "terminated"
        self.terminated_at = datetime.now(timezone.utc)

    def touch(self):
        self.last_active_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": str(self.session_id),
            "status": self.status,
            "image": self.image,
            "resources": self.resources,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
        }
