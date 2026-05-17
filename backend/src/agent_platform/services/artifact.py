"""Artifact storage service."""

import os
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.artifact import Artifact

# Default local storage path (for development; production uses S3/MinIO)
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "/tmp/forge-artifacts"))


class ArtifactService:
    """Service for managing task artifacts."""

    def __init__(self, db: AsyncSession, base_dir: Path = ARTIFACTS_DIR):
        self.db = db
        self.base_dir = base_dir

    async def create(
        self,
        task_id: UUID,
        user_id: UUID,
        org_id: UUID,
        name: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
        artifact_type: str = "file",
        metadata: Optional[dict] = None,
    ) -> Artifact:
        """Store an artifact and record it in the database."""
        artifact_id = uuid4()

        # Store file on disk (local dev); in production swap for S3 client
        org_dir = self.base_dir / str(org_id) / str(task_id)
        org_dir.mkdir(parents=True, exist_ok=True)
        file_path = org_dir / f"{artifact_id}_{name}"
        file_path.write_bytes(content)

        artifact = Artifact(
            id=artifact_id,
            task_id=task_id,
            user_id=user_id,
            org_id=org_id,
            name=name,
            mime_type=mime_type,
            size=len(content),
            storage_path=str(file_path),
            artifact_type=artifact_type,
            extra_metadata=metadata or {},
        )
        self.db.add(artifact)
        await self.db.commit()
        await self.db.refresh(artifact)
        return artifact

    async def list_by_task(self, task_id: UUID) -> list[Artifact]:
        """List all artifacts for a task."""
        result = await self.db.execute(
            select(Artifact)
            .where(Artifact.task_id == task_id)
            .order_by(Artifact.created_at)
        )
        return list(result.scalars().all())

    async def get(self, artifact_id: UUID) -> Artifact | None:
        """Get a single artifact by ID."""
        result = await self.db.execute(
            select(Artifact).where(Artifact.id == artifact_id)
        )
        return result.scalar_one_or_none()

    def read_content(self, artifact: Artifact) -> bytes:
        """Read artifact content from storage."""
        path = Path(artifact.storage_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact file not found: {path}")
        return path.read_bytes()
