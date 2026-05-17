"""Artifact model for task outputs."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from agent_platform.database import Base


class Artifact(Base):
    """An output file or data produced by a task execution."""

    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
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
    name = Column(String(500), nullable=False)
    mime_type = Column(String(200), nullable=False, default="application/octet-stream")
    size = Column(Integer, nullable=False, default=0)
    storage_path = Column(Text, nullable=False)
    artifact_type = Column(String(50), nullable=False, default="file")
    extra_metadata = Column(JSONB, nullable=True, default=dict)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "name": self.name,
            "mime_type": self.mime_type,
            "size": self.size,
            "artifact_type": self.artifact_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "download_url": f"/api/v1/artifacts/{self.id}/download",
        }
