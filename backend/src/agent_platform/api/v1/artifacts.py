"""Artifact management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.task import Task
from agent_platform.services.artifact import ArtifactService

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class ArtifactResponse(BaseModel):
    id: str
    task_id: str
    name: str
    mime_type: str
    size: int
    artifact_type: str
    created_at: str | None
    download_url: str


class ArtifactListResponse(BaseModel):
    items: list[ArtifactResponse]


@router.post("/upload/{task_id}", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def upload_artifact(
    current_user: CurrentUser,
    task_id: UUID,
    file: UploadFile,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ArtifactResponse:
    """Upload an artifact for a task."""
    from sqlalchemy import select

    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    content = await file.read()
    svc = ArtifactService(db=db)
    artifact = await svc.create(
        task_id=task_id,
        user_id=current_user.id,
        org_id=current_user.org_id,
        name=file.filename or "unnamed",
        content=content,
        mime_type=file.content_type or "application/octet-stream",
    )

    d = artifact.to_dict()
    return ArtifactResponse(**d)


@router.get("/{artifact_id}/download")
async def download_artifact(
    current_user: CurrentUser,
    artifact_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Download an artifact file."""
    svc = ArtifactService(db=db)
    artifact = await svc.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    # Permission check: user must be in the same org
    if artifact.org_id != current_user.org_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        content = svc.read_content(artifact)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Artifact file not found on storage")

    return Response(
        content=content,
        media_type=artifact.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.name}"',
        },
    )
