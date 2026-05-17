"""Approval API endpoints for HITL (Human-in-the-Loop) system."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import get_current_user
from agent_platform.database import get_db
from agent_platform.models.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    HITLRule,
    RiskLevel,
)
from agent_platform.models.notification_settings import NotificationChannel, NotificationSettings
from agent_platform.models.user import User
from agent_platform.services.hitl_rules import HITLRulesEngine
from agent_platform.services.notification import (
    FeishuNotificationProvider,
    NotificationManager,
    get_notification_manager,
)
from sqlalchemy import select

router = APIRouter(prefix="/approvals", tags=["approvals"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ApprovalDecisionRequest(BaseModel):
    """Request schema for submitting an approval decision."""

    decision: ApprovalDecision
    reason: Optional[str] = Field(None, description="Reason for the decision")
    user_id: Optional[str] = Field(
        None,
        description="Deprecated. Decision identity comes from authenticated user.",
    )


class ApprovalDecisionResponse(BaseModel):
    """Response schema for approval decision."""

    id: str
    status: ApprovalStatus
    decisions: list[dict]
    approval_count: int
    rejection_count: int
    requires_more_approvals: bool
    decided_at: Optional[str] = None


class ApprovalRequestDetail(BaseModel):
    """Detailed approval request response."""

    id: str
    task_id: Optional[str]
    session_id: str
    thread_id: Optional[str]
    checkpoint_ns: Optional[str]
    tool_name: str
    tool_input: dict
    tool_input_hash: str
    risk_level: str
    description: Optional[str]
    context_summary: Optional[str]
    approvers: list[dict]
    strategy: str
    min_approvals_required: int
    status: ApprovalStatus
    decisions: list[dict]
    approval_count: int
    rejection_count: int
    is_expired: bool
    requires_more_approvals: bool
    requested_at: str
    expires_at: str
    decided_at: Optional[str]

    class Config:
        from_attributes = True


class ApprovalListItem(BaseModel):
    """Simplified approval item for list views."""

    id: str
    tool_name: str
    risk_level: str
    status: ApprovalStatus
    description: Optional[str]
    approval_count: int
    rejection_count: int
    requested_at: str
    expires_at: str
    is_expired: bool

    class Config:
        from_attributes = True


class ApprovalListResponse(BaseModel):
    """Response for listing approvals."""

    items: list[ApprovalListItem]
    total: int
    page: int
    page_size: int


class HITLRuleResponse(BaseModel):
    """Response schema for HITL rule."""

    id: str
    name: str
    description: Optional[str]
    tool_name_pattern: str
    argument_patterns: dict
    risk_level: str
    strategy: str
    min_approvals_required: int
    is_active: bool
    priority: int

    class Config:
        from_attributes = True


class HITLRulesListResponse(BaseModel):
    """Response for listing HITL rules."""

    rules: list[HITLRuleResponse]
    default_rules: list[dict]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================

async def get_approval_request(
    approval_id: str,
    db: AsyncSession,
    current_user: User,
) -> ApprovalRequest:
    """Get an approval request by ID with permission check.

    Args:
        approval_id: ID of the approval request
        db: Database session
        current_user: Current authenticated user

    Returns:
        ApprovalRequest if found and accessible

    Raises:
        HTTPException: If not found or no permission
    """
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )

    # Permission check: user must be in approvers list, same org, or admin
    approver_ids = [str(a.get("user_id")) for a in approval.approvers if a.get("user_id")]
    same_org = str(current_user.org_id) == str(approval.org_id) if hasattr(approval, 'org_id') and approval.org_id else True
    if str(current_user.id) not in approver_ids and not current_user.is_admin and not same_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this approval request",
        )

    return approval


def can_decide_approval(approval: ApprovalRequest, user_id: str) -> bool:
    """Check if a user can submit a decision for an approval.

    Args:
        approval: Approval request
        user_id: User ID to check

    Returns:
        True if user can decide
    """
    # Check if already decided
    if approval.is_decided:
        return False

    # Check if expired
    if approval.is_expired:
        return False

    # Check if user is in approvers list
    approver_ids = [str(a.get("user_id")) for a in approval.approvers if a.get("user_id")]
    if str(user_id) not in approver_ids:
        # Check if user already made a decision
        existing_decisions = [str(d.get("user_id")) for d in approval.decisions]
        if str(user_id) in existing_decisions:
            return False

    return True


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "/pending",
    response_model=ApprovalListResponse,
    summary="List pending approval requests",
    description="Get a list of pending approval requests that require action.",
)
async def list_pending_approvals(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalListResponse:
    """List pending approval requests.

    Returns approval requests that are pending and not expired,
    filtered by the current user's permissions.
    """
    # Build base query
    query = select(ApprovalRequest).where(
        ApprovalRequest.status == ApprovalStatus.PENDING
    )

    # Filter by session if provided
    if session_id:
        query = query.where(ApprovalRequest.session_id == session_id)

    # Filter by risk level if provided
    if risk_level:
        query = query.where(ApprovalRequest.risk_level == risk_level)

    # Filter by org membership — show approvals where user is an approver or same org
    # In production, JSONB querying can be used for exact approver matching

    # Order by requested_at descending (newest first)
    query = query.order_by(desc(ApprovalRequest.requested_at))

    # Execute query with pagination
    result = await db.execute(query)
    all_items = result.scalars().all()

    # Filter expired items in Python (since is_expired is a property)
    valid_items = [item for item in all_items if not item.is_expired]

    # Apply pagination
    total = len(valid_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = valid_items[start_idx:end_idx]

    return ApprovalListResponse(
        items=[
            ApprovalListItem(
                id=str(item.id),
                tool_name=item.tool_name,
                risk_level=item.risk_level,
                status=item.status,
                description=item.description,
                approval_count=item.approval_count,
                rejection_count=item.rejection_count,
                requested_at=item.requested_at.isoformat() if item.requested_at else "",
                expires_at=item.expires_at.isoformat() if item.expires_at else "",
                is_expired=item.is_expired,
            )
            for item in paginated_items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/rules",
    response_model=HITLRulesListResponse,
    summary="List HITL rules",
    description="Get a list of all HITL rules including default and custom rules.",
)
async def list_hitl_rules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HITLRulesListResponse:
    """List all HITL rules.

    Returns both default system rules and organization-specific rules.
    """
    # Get custom rules for user's organization
    result = await db.execute(
        select(HITLRule)
        .where(HITLRule.org_id == current_user.org_id)
        .where(HITLRule.is_active == True)
        .order_by(HITLRule.priority.desc())
    )
    custom_rules = result.scalars().all()

    # Get default rules from engine
    engine = HITLRulesEngine()
    default_rules = engine.default_rules

    return HITLRulesListResponse(
        rules=[
            HITLRuleResponse(
                id=rule.id,
                name=rule.name,
                description=rule.description,
                tool_name_pattern=rule.tool_name_pattern,
                argument_patterns=rule.argument_patterns,
                risk_level=rule.risk_level,
                strategy=rule.strategy,
                min_approvals_required=rule.min_approvals_required,
                is_active=rule.is_active,
                priority=rule.priority,
            )
            for rule in custom_rules
        ],
        default_rules=default_rules,
        total=len(custom_rules) + len(default_rules),
    )


@router.get(
    "/history",
    response_model=ApprovalListResponse,
    summary="List approval history",
    description="Get a list of completed (approved/rejected/expired) approval requests.",
)
async def list_approval_history(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    approval_status: Optional[ApprovalStatus] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalListResponse:
    """List completed approval requests (history).

    Returns approved, rejected, or expired approval requests.
    """
    # Build base query for non-pending statuses
    query = select(ApprovalRequest).where(
        ApprovalRequest.status.in_([
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.EXPIRED,
            ApprovalStatus.ESCALATED,
        ])
    )

    # Filter by session if provided
    if session_id:
        query = query.where(ApprovalRequest.session_id == session_id)

    # Filter by status if provided
    if approval_status:
        query = query.where(ApprovalRequest.status == approval_status)

    # Order by decided_at descending (most recent first)
    query = query.order_by(desc(ApprovalRequest.decided_at or ApprovalRequest.requested_at))

    # Execute query with pagination
    result = await db.execute(query)
    all_items = result.scalars().all()

    # Apply pagination
    total = len(all_items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_items = all_items[start_idx:end_idx]

    return ApprovalListResponse(
        items=[
            ApprovalListItem(
                id=str(item.id),
                tool_name=item.tool_name,
                risk_level=item.risk_level,
                status=item.status,
                description=item.description,
                approval_count=item.approval_count,
                rejection_count=item.rejection_count,
                requested_at=item.requested_at.isoformat() if item.requested_at else "",
                expires_at=item.expires_at.isoformat() if item.expires_at else "",
                is_expired=item.is_expired,
            )
            for item in paginated_items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalRequestDetail,
    summary="Get approval request details",
    description="Get detailed information about a specific approval request.",
)
async def get_approval_detail(
    approval_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalRequestDetail:
    """Get detailed information about an approval request."""
    approval = await get_approval_request(str(approval_id), db, current_user)

    return ApprovalRequestDetail(
        id=str(approval.id),
        task_id=str(approval.task_id) if approval.task_id else None,
        session_id=str(approval.session_id),
        thread_id=approval.thread_id,
        checkpoint_ns=approval.checkpoint_ns,
        tool_name=approval.tool_name,
        tool_input=approval.tool_input,
        tool_input_hash=approval.tool_input_hash,
        risk_level=approval.risk_level,
        description=approval.description,
        context_summary=approval.context_summary,
        approvers=approval.approvers,
        strategy=approval.strategy,
        min_approvals_required=approval.min_approvals_required,
        status=approval.status,
        decisions=approval.decisions,
        approval_count=approval.approval_count,
        rejection_count=approval.rejection_count,
        is_expired=approval.is_expired,
        requires_more_approvals=approval.requires_more_approvals,
        requested_at=approval.requested_at.isoformat() if approval.requested_at else "",
        expires_at=approval.expires_at.isoformat() if approval.expires_at else "",
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
    )


async def _send_approval_notification(
    approval: ApprovalRequest,
    db: AsyncSession,
) -> None:
    """Send notification for new approval request.

    Args:
        approval: The approval request
        db: Database session
    """
    try:
        notification_manager = get_notification_manager()

        for approver in approval.approvers:
            user_id = approver.get("user_id")
            if not user_id:
                continue

            # Get user's notification settings
            result = await db.execute(
                select(NotificationSettings).where(
                    NotificationSettings.user_id == user_id
                )
            )
            settings = result.scalar_one_or_none()

            if not settings:
                continue

            # Get enabled channels for this event
            channels = settings.get_enabled_channels_for_event(
                NotificationSettings.NotificationEvent.APPROVAL_REQUESTED
            )

            if not channels:
                continue

            # Prepare approval data
            approval_data = {
                "id": approval.id,
                "tool_name": approval.tool_name,
                "tool_input": approval.tool_input,
                "risk_level": approval.risk_level,
                "description": approval.description,
                "context_summary": approval.context_summary,
            }

            # Send notification
            await notification_manager.send_approval_request(
                user_id=user_id,
                channels=channels,
                approval_request=approval_data,
                feishu_user_id=settings.feishu_user_id,
            )
    except Exception:
        # Notification failures should not break the approval flow
        pass


async def _send_approval_status_notification(
    approval: ApprovalRequest,
    db: AsyncSession,
    decided_by: str,
) -> None:
    """Send notification for approval status change.

    Args:
        approval: The approval request
        db: Database session
        decided_by: Email or name of who made the decision
    """
    try:
        notification_manager = get_notification_manager()

        # Get the session to find the creator
        result = await db.execute(
            select(NotificationSettings).where(
                NotificationSettings.user_id == approval.session.user_id
            )
        )
        settings = result.scalar_one_or_none()

        if not settings:
            return

        channels = settings.get_enabled_channels_for_event(
            NotificationSettings.NotificationEvent.APPROVAL_APPROVED
            if approval.status == ApprovalStatus.APPROVED
            else NotificationSettings.NotificationEvent.APPROVAL_REJECTED
        )

        if not channels:
            return

        # Find decision reason
        reason = None
        for decision in approval.decisions:
            if decision.get("user_id") == decided_by:
                reason = decision.get("reason")
                break

        await notification_manager.send_approval_status_change(
            user_id=approval.session.user_id,
            channels=channels,
            approval_id=approval.id,
            status=approval.status,
            decided_by=decided_by,
            reason=reason,
            feishu_user_id=settings.feishu_user_id,
        )
    except Exception:
        # Notification failures should not break the approval flow
        pass


@router.post(
    "/{approval_id}",
    response_model=ApprovalDecisionResponse,
    summary="Submit approval decision",
    description="Submit a decision (approve/reject) for an approval request.",
)
async def submit_approval_decision(
    approval_id: UUID,
    decision_request: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalDecisionResponse:
    """Submit a decision for an approval request.

    This endpoint allows authorized users to approve or reject
    pending approval requests.
    """
    approval = await get_approval_request(str(approval_id), db, current_user)

    # Check if approval request is still pending
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval request is already {approval.status}",
        )

    # Check if expired
    if approval.is_expired:
        approval.status = ApprovalStatus.EXPIRED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has expired",
        )

    # Always use authenticated user identity, ignore body user_id
    decision_user_id = str(current_user.id)

    # Verify user can make this decision
    if not can_decide_approval(approval, decision_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit decision for this approval request",
        )

    # Add the decision
    approval.add_decision(
        user_id=decision_user_id,
        decision=decision_request.decision,
        reason=decision_request.reason,
    )

    # Commit changes
    await db.commit()
    await db.refresh(approval)

    # Send status change notification if decided
    if approval.is_decided:
        await _send_approval_status_notification(
            approval=approval,
            db=db,
            decided_by=current_user.email or current_user.display_name or str(current_user.id),
        )

    return ApprovalDecisionResponse(
        id=str(approval.id),
        status=approval.status,
        decisions=approval.decisions,
        approval_count=approval.approval_count,
        rejection_count=approval.rejection_count,
        requires_more_approvals=approval.requires_more_approvals,
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
    )


@router.post(
    "/{approval_id}/cancel",
    response_model=ApprovalDecisionResponse,
    summary="Cancel approval request",
    description="Cancel a pending approval request (creator or admin only).",
)
async def cancel_approval_request(
    approval_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ApprovalDecisionResponse:
    """Cancel a pending approval request.

    Only the creator or an admin can cancel an approval request.
    """
    approval = await get_approval_request(str(approval_id), db, current_user)

    # Check if can be cancelled
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel approval request with status: {approval.status}",
        )

    # Check permissions: approval creator (task owner) or admin can cancel
    task_user_id = str(approval.task.user_id) if approval.task else None
    if not current_user.is_admin and str(current_user.id) != task_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can cancel approval requests",
        )

    # Cancel the request
    approval.status = ApprovalStatus.CANCELLED
    approval.decided_at = datetime.utcnow()
    approval.decisions = [*approval.decisions, {
        "user_id": str(current_user.id),
        "decision": "cancelled",
        "timestamp": datetime.utcnow().isoformat(),
        "reason": "Cancelled by user",
    }]

    await db.commit()
    await db.refresh(approval)

    return ApprovalDecisionResponse(
        id=str(approval.id),
        status=approval.status,
        decisions=approval.decisions,
        approval_count=approval.approval_count,
        rejection_count=approval.rejection_count,
        requires_more_approvals=False,
        decided_at=approval.decided_at.isoformat(),
    )
