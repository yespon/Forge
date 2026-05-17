"""Webhook handlers for external integrations.

Handles callbacks from Feishu (Lark), including card button clicks
and event notifications.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.config import get_settings
from agent_platform.database import get_db
from agent_platform.models.approval import ApprovalDecision, ApprovalRequest, ApprovalStatus
from agent_platform.models.user import User
from agent_platform.services.feishu import FeishuError, get_feishu_client

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================================================
# Pydantic Schemas
# =============================================================================

class FeishuEventPayload(BaseModel):
    """Feishu event payload schema."""

    event_type: str
    token: Optional[str] = None
    challenge: Optional[str] = None
    open_id: Optional[str] = None
    open_message_id: Optional[str] = None
    action: Optional[dict] = None
    event: Optional[dict] = None


class FeishuCardActionResponse(BaseModel):
    """Response schema for Feishu card action."""

    success: bool
    message: str
    approval_id: Optional[str] = None
    status: Optional[str] = None


class WebhookResponse(BaseModel):
    """Generic webhook response."""

    code: int = 0
    msg: str = "success"
    challenge: Optional[str] = None


# =============================================================================
# Signature Verification
# =============================================================================

def verify_feishu_signature(
    signature: str,
    timestamp: str,
    nonce: str,
    body: str,
    secret: str,
) -> bool:
    """Verify Feishu webhook signature.

    Feishu uses HMAC-SHA256 for signature verification.
    Signature format: base64(hmac_sha256(timestamp\nsecret\nbody))

    Args:
        signature: Signature from X-Lark-Signature header
        timestamp: Timestamp from X-Lark-Request-Timestamp header
        nonce: Nonce from X-Lark-Request-Nonce header
        body: Raw request body
        secret: Webhook verification secret

    Returns:
        True if signature is valid
    """
    try:
        # Build string to sign (Feishu format)
        string_to_sign = f"{timestamp}\n{nonce}\n{secret}\n{body}"

        # Calculate HMAC-SHA256
        hmac_code = hmac.new(
            key=secret.encode("utf-8"),
            msg=string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        expected_signature = base64.b64encode(hmac_code).decode("utf-8")

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


def verify_feishu_signature_legacy(
    signature: str,
    timestamp: str,
    body: str,
    secret: str,
) -> bool:
    """Verify Feishu webhook signature (legacy format without nonce).

    Args:
        signature: Signature from header
        timestamp: Timestamp from header
        body: Raw request body
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    try:
        # Legacy format: timestamp\nsecret
        string_to_sign = f"{timestamp}\n{secret}"

        hmac_code = hmac.new(
            key=string_to_sign.encode("utf-8"),
            msg=body.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()

        expected_signature = base64.b64encode(hmac_code).decode("utf-8")

        return hmac.compare_digest(expected_signature, signature)
    except Exception:
        return False


# =============================================================================
# Event Parsing
# =============================================================================

def parse_card_action(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Parse card action from webhook payload.

    Args:
        payload: Feishu event payload

    Returns:
        Parsed action data or None if not a card action
    """
    event_type = payload.get("event_type", "")

    if event_type != "card.action.trigger":
        return None

    action_data = payload.get("action", {})
    action_value = action_data.get("value", {})

    if not action_value:
        return None

    return {
        "action_type": action_value.get("action"),
        "approval_id": action_value.get("approval_id"),
        "user_id": action_value.get("user_id"),
        "open_id": payload.get("open_id"),
        "open_message_id": payload.get("open_message_id"),
        "token": payload.get("token"),
        "tag": action_data.get("tag"),
        "option": action_data.get("option"),
    }


def parse_url_verification(payload: dict[str, Any]) -> Optional[str]:
    """Parse URL verification challenge.

    Args:
        payload: Feishu event payload

    Returns:
        Challenge string or None if not a verification request
    """
    if payload.get("type") == "url_verification":
        return payload.get("challenge")
    return None


# =============================================================================
# Approval Action Handlers
# =============================================================================

async def handle_approval_action(
    action_type: str,
    approval_id: str,
    user_id: Optional[str],
    db: AsyncSession,
) -> FeishuCardActionResponse:
    """Handle approval action from Feishu card.

    Args:
        action_type: Action type (approve/reject)
        approval_id: Approval request ID
        user_id: User ID making the decision
        db: Database session

    Returns:
        Action response
    """
    from sqlalchemy import select

    # Get approval request
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        return FeishuCardActionResponse(
            success=False,
            message="审批请求不存在",
            approval_id=approval_id,
        )

    # Check if already decided
    if approval.status != ApprovalStatus.PENDING:
        return FeishuCardActionResponse(
            success=False,
            message=f"审批请求已被处理，当前状态: {approval.status.value}",
            approval_id=approval_id,
            status=approval.status.value,
        )

    # Check if expired
    if approval.is_expired:
        approval.status = ApprovalStatus.EXPIRED
        await db.commit()
        return FeishuCardActionResponse(
            success=False,
            message="审批请求已过期",
            approval_id=approval_id,
            status=ApprovalStatus.EXPIRED.value,
        )

    # Map action to decision
    decision_map = {
        "approve": ApprovalDecision.APPROVED,
        "reject": ApprovalDecision.REJECTED,
    }

    if action_type not in decision_map:
        return FeishuCardActionResponse(
            success=False,
            message=f"未知的操作类型: {action_type}",
            approval_id=approval_id,
        )

    # Check if user can make decision
    if user_id:
        approver_ids = [
            a.get("user_id") for a in approval.approvers if a.get("user_id")
        ]
        existing_decisions = [d.get("user_id") for d in approval.decisions]

        if user_id not in approver_ids and user_id not in existing_decisions:
            return FeishuCardActionResponse(
                success=False,
                message="您没有权限处理此审批请求",
                approval_id=approval_id,
            )

    # Add decision
    decision = decision_map[action_type]
    approval.add_decision(
        user_id=user_id or "feishu_user",
        decision=decision,
        reason=f"通过飞书卡片操作 ({action_type})",
    )

    await db.commit()
    await db.refresh(approval)

    # Determine success message
    if decision == ApprovalDecision.APPROVED:
        message = "✅ 审批已通过"
    else:
        message = "❌ 审批已拒绝"

    return FeishuCardActionResponse(
        success=True,
        message=message,
        approval_id=approval_id,
        status=approval.status.value,
    )


async def handle_retry_task_action(
    task_id: str,
    user_id: Optional[str],
) -> FeishuCardActionResponse:
    """Handle retry task action from Feishu card.

    Args:
        task_id: Task ID
        user_id: User ID

    Returns:
        Action response
    """
    # TODO: Implement task retry logic
    # This would typically trigger a background job to retry the task

    return FeishuCardActionResponse(
        success=True,
        message=f"🔄 任务 {task_id} 已加入重试队列",
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post(
    "/feishu",
    response_model=WebhookResponse,
    summary="Feishu webhook handler",
    description="Handle callbacks from Feishu, including card button clicks and events.",
)
async def handle_feishu_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_lark_signature: Optional[str] = Header(None, alias="X-Lark-Signature"),
    x_lark_request_timestamp: Optional[str] = Header(None, alias="X-Lark-Request-Timestamp"),
    x_lark_request_nonce: Optional[str] = Header(None, alias="X-Lark-Request-Nonce"),
) -> WebhookResponse:
    """Handle Feishu webhook events.

    This endpoint handles:
    - URL verification (challenge-response)
    - Card action triggers (button clicks)
    - Event callbacks

    Signature verification is performed using the Feishu webhook secret.
    """
    # Get raw body
    body = await request.body()
    body_str = body.decode("utf-8")

    # Parse payload
    try:
        payload = json.loads(body_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in request body",
        )

    # URL verification (no signature check needed for initial setup)
    challenge = parse_url_verification(payload)
    if challenge:
        return WebhookResponse(challenge=challenge)

    # Verify signature
    settings = get_settings()
    feishu_secret = getattr(settings, "FEISHU_WEBHOOK_SECRET", None)

    if feishu_secret and x_lark_signature:
        # Try new format with nonce
        if x_lark_request_nonce:
            is_valid = verify_feishu_signature(
                signature=x_lark_signature,
                timestamp=x_lark_request_timestamp or "",
                nonce=x_lark_request_nonce,
                body=body_str,
                secret=feishu_secret,
            )
        else:
            # Try legacy format
            is_valid = verify_feishu_signature_legacy(
                signature=x_lark_signature,
                timestamp=x_lark_request_timestamp or "",
                body=body_str,
                secret=feishu_secret,
            )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

    # Handle card action
    card_action = parse_card_action(payload)
    if card_action:
        action_type = card_action.get("action_type")
        approval_id = card_action.get("approval_id")
        task_id = card_action.get("task_id")
        user_id = card_action.get("user_id")

        if action_type in ("approve", "reject") and approval_id:
            response = await handle_approval_action(
                action_type=action_type,
                approval_id=approval_id,
                user_id=user_id,
                db=db,
            )

            if response.success:
                return WebhookResponse(
                    code=0,
                    msg=response.message,
                )
            else:
                return WebhookResponse(
                    code=400,
                    msg=response.message,
                )

        elif action_type == "retry_task" and task_id:
            response = await handle_retry_task_action(
                task_id=task_id,
                user_id=user_id,
            )
            return WebhookResponse(
                code=0 if response.success else 400,
                msg=response.message,
            )

        elif action_type == "view_task" and task_id:
            # Just acknowledge the view action
            return WebhookResponse(
                code=0,
                msg="已跳转到任务详情",
            )

    # Handle other event types
    event_type = payload.get("event_type", "")

    if event_type == "im.message.receive_v1":
        # Handle incoming message
        event = payload.get("event", {})
        message = event.get("message", {})
        sender = event.get("sender", {})

        # TODO: Handle bot mentions or commands
        # For now, just acknowledge
        return WebhookResponse(
            code=0,
            msg="Message received",
        )

    # Default response for unhandled events
    return WebhookResponse(
        code=0,
        msg="Event received",
    )


@router.get(
    "/feishu/config",
    summary="Get Feishu webhook configuration",
    description="Get the webhook URL and verification token for Feishu setup.",
)
async def get_feishu_webhook_config() -> dict[str, Any]:
    """Get Feishu webhook configuration.

    Returns webhook URL and verification information for setting up
    the Feishu Bot webhook.
    """
    settings = get_settings()

    # Build webhook URL
    base_url = getattr(settings, "APP_BASE_URL", "https://api.example.com")
    webhook_url = f"{base_url}/api/v1/webhooks/feishu"

    return {
        "webhook_url": webhook_url,
        "events_supported": [
            "card.action.trigger",
            "im.message.receive_v1",
        ],
        "verification": {
            "method": "HMAC-SHA256",
            "headers": [
                "X-Lark-Signature",
                "X-Lark-Request-Timestamp",
                "X-Lark-Request-Nonce",
            ],
        },
    }


# =============================================================================
# Card Response Helpers
# =============================================================================

def build_card_update_response(
    message: str,
    replace_card: Optional[dict] = None,
) -> dict[str, Any]:
    """Build response to update card after action.

    Args:
        message: Status message to display
        replace_card: Optional new card to replace the current one

    Returns:
        Response payload for Feishu
    """
    response: dict[str, Any] = {
        "code": 0,
        "msg": "success",
    }

    if replace_card:
        response["data"] = {
            "toast": {
                "type": "success",
                "content": message,
            },
            "card": replace_card,
        }
    else:
        response["data"] = {
            "toast": {
                "type": "success",
                "content": message,
            },
        }

    return response


def build_card_error_response(
    error_message: str,
) -> dict[str, Any]:
    """Build error response for card action.

    Args:
        error_message: Error message to display

    Returns:
        Error response payload
    """
    return {
        "code": 400,
        "msg": error_message,
        "data": {
            "toast": {
                "type": "error",
                "content": error_message,
            },
        },
    }
