"""Sandbox management endpoints."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.sandbox import SandboxRecord
from agent_platform.models.session import Session
from agent_platform.sandbox.docker import get_sandbox_provider
from agent_platform.sandbox.models import SandboxConfig, SandboxStatus

router = APIRouter(prefix="/sessions/{session_id}/sandbox", tags=["sandbox"])


# Schemas
class SandboxCreateRequest(BaseModel):
    """Create sandbox request."""

    image: str = Field(default="python:3.12-slim", description="Docker image")
    memory_limit: str = Field(default="512m", description="Memory limit")
    cpu_limit: float = Field(default=0.5, description="CPU limit (0.1-1.0)")
    allow_internet: bool = Field(default=False, description="Allow internet access")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Environment variables")


class SandboxResponse(BaseModel):
    """Sandbox response."""

    id: str
    session_id: str
    status: str
    container_id: str | None
    created_at: str
    started_at: str | None
    last_activity_at: str
    config: dict
    memory_usage_mb: float | None
    cpu_usage_percent: float | None


class ExecuteRequest(BaseModel):
    """Execute command request."""

    command: str = Field(..., min_length=1, description="Command to execute")
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds")
    working_dir: str | None = Field(None, description="Working directory")


class ExecuteResponse(BaseModel):
    """Execute command response."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool


class FileUploadRequest(BaseModel):
    """File upload request."""

    path: str = Field(..., description="Target path in sandbox")
    content: str = Field(..., description="File content (base64 encoded)")


class FileResponse(BaseModel):
    """File response."""

    path: str
    content: str
    size: int


class FileListResponse(BaseModel):
    """File list response."""

    files: list[dict[str, Any]]


# Endpoints
@router.get("", response_model=SandboxResponse)
async def get_sandbox(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SandboxResponse:
    """Get sandbox information for a session."""
    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get sandbox info
    provider = await get_sandbox_provider()
    sandbox_id = session.settings.get("sandbox_id")

    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox created for this session",
        )

    try:
        info = await provider.get_info(sandbox_id)
        return SandboxResponse(
            id=info.id,
            session_id=str(session_id),
            status=info.status.value,
            container_id=info.container_id,
            created_at=info.created_at.isoformat(),
            started_at=info.started_at.isoformat() if info.started_at else None,
            last_activity_at=info.last_activity_at.isoformat(),
            config={
                "image": info.config.image,
                "memory_limit": info.config.memory_limit,
                "cpu_limit": info.config.cpu_limit,
                "network_mode": info.config.network_mode,
            },
            memory_usage_mb=info.memory_usage_mb,
            cpu_usage_percent=info.cpu_usage_percent,
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )


@router.post("/create", response_model=SandboxResponse, status_code=status.HTTP_201_CREATED)
async def create_sandbox(
    current_user: CurrentUser,
    session_id: UUID,
    request: SandboxCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SandboxResponse:
    """Create a sandbox for the session."""
    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Check if sandbox already exists
    if session.settings.get("sandbox_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sandbox already exists for this session",
        )

    # Create sandbox
    provider = await get_sandbox_provider()
    config = SandboxConfig(
        image=request.image,
        memory_limit=request.memory_limit,
        cpu_limit=request.cpu_limit,
        allow_internet=request.allow_internet,
        env_vars=request.env_vars,
    )

    try:
        info = await provider.create(
            session_id=str(session_id),
            config=config,
        )

        # Store sandbox ID in session settings (reassign for JSON change tracking)
        updated_settings = dict(session.settings)
        updated_settings["sandbox_id"] = info.id
        session.settings = updated_settings

        # Persist sandbox record to DB
        record = SandboxRecord(
            id=info.id,
            session_id=session_id,
            user_id=current_user.id,
            org_id=current_user.org_id,
            image=request.image,
            resources={
                "memory_limit": request.memory_limit,
                "cpu_limit": request.cpu_limit,
            },
        )
        record.mark_running()
        db.add(record)
        await db.commit()

        return SandboxResponse(
            id=info.id,
            session_id=str(session_id),
            status=info.status.value,
            container_id=info.container_id,
            created_at=info.created_at.isoformat(),
            started_at=info.started_at.isoformat() if info.started_at else None,
            last_activity_at=info.last_activity_at.isoformat(),
            config={
                "image": info.config.image,
                "memory_limit": info.config.memory_limit,
                "cpu_limit": info.config.cpu_limit,
                "network_mode": info.config.network_mode,
            },
            memory_usage_mb=info.memory_usage_mb,
            cpu_usage_percent=info.cpu_usage_percent,
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sandbox: {e}",
        )


@router.post("/destroy", status_code=status.HTTP_204_NO_CONTENT)
async def destroy_sandbox(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Destroy the session's sandbox."""
    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    sandbox_id = session.settings.get("sandbox_id")
    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox exists for this session",
        )

    # Destroy sandbox
    provider = await get_sandbox_provider()
    try:
        await provider.destroy(sandbox_id)
        updated_settings = {k: v for k, v in session.settings.items() if k != "sandbox_id"}
        session.settings = updated_settings

        # Update DB record
        record_result = await db.execute(
            select(SandboxRecord).where(SandboxRecord.id == sandbox_id)
        )
        record = record_result.scalar_one_or_none()
        if record:
            record.mark_terminated()

        await db.commit()

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to destroy sandbox: {e}",
        )


@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(
    current_user: CurrentUser,
    session_id: UUID,
    request: ExecuteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExecuteResponse:
    """Execute a command in the sandbox."""
    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    sandbox_id = session.settings.get("sandbox_id")
    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox created for this session. Create one first.",
        )

    # Execute command
    provider = await get_sandbox_provider()
    try:
        exec_result = await provider.execute(
            sandbox_id=sandbox_id,
            command=request.command,
            timeout=request.timeout,
            working_dir=request.working_dir,
        )

        return ExecuteResponse(
            success=exec_result.success,
            exit_code=exec_result.exit_code,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            duration_ms=exec_result.duration_ms,
            timed_out=exec_result.timed_out,
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )


@router.post("/files/upload")
async def upload_file(
    current_user: CurrentUser,
    session_id: UUID,
    request: FileUploadRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Upload a file to the sandbox."""
    import base64

    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    sandbox_id = session.settings.get("sandbox_id")
    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox created for this session",
        )

    # Decode content
    try:
        content = base64.b64decode(request.content)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 content",
        )

    # Upload file
    provider = await get_sandbox_provider()
    try:
        await provider.upload_file(
            sandbox_id=sandbox_id,
            path=request.path,
            content=content,
        )

        return {
            "message": "File uploaded successfully",
            "path": request.path,
            "size": len(content),
        }

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {e}",
        )


@router.get("/files/download")
async def download_file(
    current_user: CurrentUser,
    session_id: UUID,
    path: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    """Download a file from the sandbox."""
    import base64

    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    sandbox_id = session.settings.get("sandbox_id")
    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox created for this session",
        )

    # Download file
    provider = await get_sandbox_provider()
    try:
        content = await provider.download_file(
            sandbox_id=sandbox_id,
            path=path,
        )

        return FileResponse(
            path=path,
            content=base64.b64encode(content).decode(),
            size=len(content),
        )

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {e}",
        )


@router.get("/files/list")
async def list_files(
    current_user: CurrentUser,
    session_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    path: str = "/",
) -> FileListResponse:
    """List files in the sandbox."""
    # Verify session ownership
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    sandbox_id = session.settings.get("sandbox_id")
    if not sandbox_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sandbox created for this session",
        )

    # List files
    provider = await get_sandbox_provider()
    try:
        files = await provider.list_files(
            sandbox_id=sandbox_id,
            path=path,
        )

        return FileListResponse(files=files)

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sandbox not found",
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {e}",
        )
