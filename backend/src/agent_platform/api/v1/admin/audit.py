"""Audit log API endpoints for administrators.

This module provides endpoints for querying and managing audit logs.
All endpoints require admin privileges.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import get_current_user
from agent_platform.auth.rbac import require_admin
from agent_platform.database import get_db
from agent_platform.models.audit_log import AuditAction, AuditLog, ResourceType
from agent_platform.models.user import User
from agent_platform.services.audit_logger import AuditLogger

router = APIRouter(prefix="/audit-logs", tags=["admin", "audit"])


# =============================================================================
# Pydantic Schemas
# =============================================================================


class AuditLogResponse(BaseModel):
    """Audit log entry response schema."""

    id: str
    timestamp: str
    user_id: Optional[str]
    org_id: Optional[str]
    session_id: Optional[str]
    task_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: dict
    success: Optional[bool]
    error_message: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int


class AuditLogFilters(BaseModel):
    """Filters for querying audit logs."""

    user_id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    action: Optional[AuditAction] = None
    resource_type: Optional[ResourceType] = None
    success: Optional[bool] = None
    request_id: Optional[str] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None


class AuditLogStats(BaseModel):
    """Audit log statistics."""

    total_logs: int
    successful_actions: int
    failed_actions: int
    action_breakdown: dict[str, int]
    resource_type_breakdown: dict[str, int]


# =============================================================================
# Helper Functions
# =============================================================================


def _audit_log_to_response(audit_log: AuditLog) -> AuditLogResponse:
    """Convert AuditLog model to response schema."""
    return AuditLogResponse(
        id=str(audit_log.id),
        timestamp=audit_log.timestamp.isoformat() if audit_log.timestamp else "",
        user_id=str(audit_log.user_id) if audit_log.user_id else None,
        org_id=str(audit_log.org_id) if audit_log.org_id else None,
        session_id=str(audit_log.session_id) if audit_log.session_id else None,
        task_id=str(audit_log.task_id) if audit_log.task_id else None,
        action=audit_log.action,
        resource_type=audit_log.resource_type,
        resource_id=audit_log.resource_id,
        details=audit_log.details,
        success=audit_log.success,
        error_message=audit_log.error_message,
        ip_address=audit_log.ip_address,
        user_agent=audit_log.user_agent,
        request_id=audit_log.request_id,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@router.get(
    "",
    response_model=AuditLogListResponse,
    dependencies=[Depends(require_admin)],
)
async def list_audit_logs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    org_id: Optional[UUID] = Query(None, description="Filter by organization ID"),
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    task_id: Optional[UUID] = Query(None, description="Filter by task ID"),
    action: Optional[AuditAction] = Query(None, description="Filter by action type"),
    resource_type: Optional[ResourceType] = Query(
        None, description="Filter by resource type"
    ),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    request_id: Optional[str] = Query(None, description="Filter by request ID"),
    from_date: Optional[datetime] = Query(
        None, description="Filter from this date (inclusive)"
    ),
    to_date: Optional[datetime] = Query(
        None, description="Filter to this date (inclusive)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit logs with optional filters.

    This endpoint requires admin privileges. It returns a paginated list
    of audit log entries matching the specified filters.

    Args:
        user_id: Filter by user ID
        org_id: Filter by organization ID
        session_id: Filter by session ID
        task_id: Filter by task ID
        action: Filter by action type
        resource_type: Filter by resource type
        success: Filter by success status
        request_id: Filter by request ID
        from_date: Filter from this date
        to_date: Filter to this date
        limit: Maximum number of results
        offset: Offset for pagination
        db: Database session

    Returns:
        Paginated list of audit log entries
    """
    audit_logger = AuditLogger(db=db)

    # Build filters dictionary
    filters = {}
    if user_id:
        filters["user_id"] = str(user_id)
    if org_id:
        filters["org_id"] = str(org_id)
    if session_id:
        filters["session_id"] = str(session_id)
    if task_id:
        filters["task_id"] = str(task_id)
    if action:
        filters["action"] = action.value
    if resource_type:
        filters["resource_type"] = resource_type.value
    if success is not None:
        filters["success"] = success
    if request_id:
        filters["request_id"] = request_id
    if from_date:
        filters["from_date"] = from_date
    if to_date:
        filters["to_date"] = to_date

    # Query logs
    logs = await audit_logger.query_logs(
        filters=filters if filters else None,
        limit=limit,
        offset=offset,
    )

    # Get total count
    total = await audit_logger.count_logs(filters=filters if filters else None)

    # Convert to response format
    items = [_audit_log_to_response(log) for log in logs]

    return AuditLogListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{log_id}",
    response_model=AuditLogResponse,
    dependencies=[Depends(require_admin)],
)
async def get_audit_log(
    log_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Get a single audit log entry by ID.

    Args:
        log_id: The audit log ID
        db: Database session

    Returns:
        The audit log entry

    Raises:
        HTTPException: If the audit log is not found
    """
    audit_logger = AuditLogger(db=db)
    log = await audit_logger.get_log_by_id(str(log_id))

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit log not found: {log_id}",
        )

    return _audit_log_to_response(log)


@router.get(
    "/stats/summary",
    response_model=AuditLogStats,
    dependencies=[Depends(require_admin)],
)
async def get_audit_stats(
    from_date: Optional[datetime] = Query(
        None, description="Start date for statistics"
    ),
    to_date: Optional[datetime] = Query(None, description="End date for statistics"),
    org_id: Optional[UUID] = Query(None, description="Filter by organization"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogStats:
    """Get audit log statistics.

    Returns summary statistics about audit logs including totals
    and breakdowns by action type and resource type.

    Args:
        from_date: Start date for statistics
        to_date: End date for statistics
        org_id: Filter by organization
        db: Database session

    Returns:
        Audit log statistics
    """
    from sqlalchemy import func, select

    # Build base query
    query = select(AuditLog)

    if from_date:
        query = query.where(AuditLog.timestamp >= from_date)
    if to_date:
        query = query.where(AuditLog.timestamp <= to_date)
    if org_id:
        query = query.where(AuditLog.org_id == str(org_id))

    # Get total count
    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total_logs = total_result.scalar() or 0

    # Get success/failure counts
    success_result = await db.execute(
        select(func.count())
        .select_from(query.subquery())
        .where(AuditLog.success == True)  # noqa: E712
    )
    successful_actions = success_result.scalar() or 0

    failed_actions = total_logs - successful_actions

    # Get action breakdown
    action_result = await db.execute(
        select(AuditLog.action, func.count())
        .select_from(query.subquery())
        .group_by(AuditLog.action)
    )
    action_breakdown = {row[0]: row[1] for row in action_result.all()}

    # Get resource type breakdown
    resource_result = await db.execute(
        select(AuditLog.resource_type, func.count())
        .select_from(query.subquery())
        .group_by(AuditLog.resource_type)
    )
    resource_type_breakdown = {row[0]: row[1] for row in resource_result.all()}

    return AuditLogStats(
        total_logs=total_logs,
        successful_actions=successful_actions,
        failed_actions=failed_actions,
        action_breakdown=action_breakdown,
        resource_type_breakdown=resource_type_breakdown,
    )


@router.get(
    "/actions/list",
    response_model=list[str],
    dependencies=[Depends(require_admin)],
)
async def list_audit_actions() -> list[str]:
    """List all available audit action types.

    Returns:
        List of audit action type values
    """
    return [action.value for action in AuditAction]


@router.get(
    "/resource-types/list",
    response_model=list[str],
    dependencies=[Depends(require_admin)],
)
async def list_resource_types() -> list[str]:
    """List all available resource types.

    Returns:
        List of resource type values
    """
    return [rt.value for rt in ResourceType]
