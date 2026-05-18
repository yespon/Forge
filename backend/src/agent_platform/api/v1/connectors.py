"""Connector management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.dependencies import CurrentUser
from agent_platform.database import get_db
from agent_platform.models.connector import (
    AuthType,
    ConnectionStatus,
    ConnectionVisibility,
    Connector,
    ConnectorConnection,
    ConnectorStatus,
)

router = APIRouter(prefix="/connectors", tags=["connectors"])


# --- Schemas ---

class ConnectorResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None
    auth_type: str
    supported_scopes: list[str]
    status: str
    authorized: bool = False


class ConnectorListResponse(BaseModel):
    items: list[ConnectorResponse]


class AuthorizeRequest(BaseModel):
    scopes: list[str] = Field(default_factory=list)
    vault_ref: str | None = Field(None, description="Vault reference for stored credential")
    visibility: str = Field(default="org")


class ConnectionStatusResponse(BaseModel):
    connector_id: str
    status: str
    scopes: list[str]
    is_active: bool
    expires_at: str | None


# --- Endpoints ---


class WebhookAck(BaseModel):
    ok: bool = True
    channel: str
    accepted: bool = True
    pending_messages: int = 0


class MockEmitRequest(BaseModel):
    text: str
    chat_id: str = "mock-chat"
    user_id: str = "mock-user"
    channel: str = "mock"


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectorListResponse:
    """List available connectors with user authorization status."""
    result = await db.execute(
        select(Connector).where(Connector.status == ConnectorStatus.ACTIVE)
    )
    connectors = result.scalars().all()

    # Check which connectors the user has active connections for
    conn_result = await db.execute(
        select(ConnectorConnection.connector_id).where(
            ConnectorConnection.org_id == current_user.org_id,
            ConnectorConnection.status == ConnectionStatus.ACTIVE,
        )
    )
    authorized_ids = {row[0] for row in conn_result.all()}

    items = [
        ConnectorResponse(
            id=str(c.id),
            name=c.name,
            display_name=c.display_name,
            description=c.description,
            auth_type=c.auth_type,
            supported_scopes=c.supported_scopes or [],
            status=c.status,
            authorized=c.id in authorized_ids,
        )
        for c in connectors
    ]

    return ConnectorListResponse(items=items)


@router.post("/{connector_id}/authorize", status_code=status.HTTP_201_CREATED)
async def authorize_connector(
    current_user: CurrentUser,
    connector_id: UUID,
    request: AuthorizeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionStatusResponse:
    """Authorize a connector — bind credentials for the org/user."""
    result = await db.execute(
        select(Connector).where(Connector.id == connector_id)
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Check for existing connection
    existing = await db.execute(
        select(ConnectorConnection).where(
            ConnectorConnection.connector_id == connector_id,
            ConnectorConnection.org_id == current_user.org_id,
            ConnectorConnection.user_id == current_user.id,
        )
    )
    connection = existing.scalar_one_or_none()

    if connection:
        connection.scopes = request.scopes or connector.supported_scopes or []
        connection.vault_ref = request.vault_ref
        connection.status = ConnectionStatus.ACTIVE
    else:
        connection = ConnectorConnection(
            connector_id=connector_id,
            org_id=current_user.org_id,
            user_id=current_user.id,
            visibility=ConnectionVisibility(request.visibility),
            scopes=request.scopes or connector.supported_scopes or [],
            vault_ref=request.vault_ref,
            status=ConnectionStatus.ACTIVE,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)

    return ConnectionStatusResponse(
        connector_id=str(connector_id),
        status=connection.status,
        scopes=connection.scopes or [],
        is_active=connection.is_active,
        expires_at=connection.expires_at.isoformat() if connection.expires_at else None,
    )


@router.get("/{connector_id}/status", response_model=ConnectionStatusResponse)
async def get_connector_status(
    current_user: CurrentUser,
    connector_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConnectionStatusResponse:
    """Get authorization status for a connector."""
    result = await db.execute(
        select(ConnectorConnection).where(
            ConnectorConnection.connector_id == connector_id,
            ConnectorConnection.org_id == current_user.org_id,
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return ConnectionStatusResponse(
            connector_id=str(connector_id),
            status="not_connected",
            scopes=[],
            is_active=False,
            expires_at=None,
        )

    return ConnectionStatusResponse(
        connector_id=str(connector_id),
        status=connection.status,
        scopes=connection.scopes or [],
        is_active=connection.is_active,
        expires_at=connection.expires_at.isoformat() if connection.expires_at else None,
    )


@router.post('/feishu/webhook', response_model=WebhookAck, include_in_schema=True)
async def feishu_webhook(payload: dict) -> WebhookAck:
    """Public webhook receiver for Feishu events."""
    from agent_platform.integration.channels import get_channel_service
    svc = get_channel_service()
    accepted = await svc.manager.handle_webhook('feishu', payload)
    return WebhookAck(channel='feishu', accepted=accepted, pending_messages=svc.manager.bus.inbound_pending)


@router.post('/slack/webhook', response_model=WebhookAck, include_in_schema=True)
async def slack_webhook(payload: dict) -> WebhookAck:
    """Public webhook receiver for Slack events."""
    from agent_platform.integration.channels import get_channel_service
    svc = get_channel_service()
    accepted = await svc.manager.handle_webhook('slack', payload)
    return WebhookAck(channel='slack', accepted=accepted, pending_messages=svc.manager.bus.inbound_pending)


@router.post('/telegram/webhook', response_model=WebhookAck, include_in_schema=True)
async def telegram_webhook(payload: dict) -> WebhookAck:
    """Public webhook receiver for Telegram updates."""
    from agent_platform.integration.channels import get_channel_service
    svc = get_channel_service()
    accepted = await svc.manager.handle_webhook('telegram', payload)
    return WebhookAck(channel='telegram', accepted=accepted, pending_messages=svc.manager.bus.inbound_pending)


@router.post('/dingtalk/webhook', response_model=WebhookAck, include_in_schema=True)
async def dingtalk_webhook(payload: dict) -> WebhookAck:
    """Public webhook receiver for DingTalk events."""
    from agent_platform.integration.channels import get_channel_service
    svc = get_channel_service()
    accepted = await svc.manager.handle_webhook('dingtalk', payload)
    return WebhookAck(channel='dingtalk', accepted=accepted, pending_messages=svc.manager.bus.inbound_pending)


@router.post('/mock/emit', response_model=WebhookAck, include_in_schema=True)
async def mock_emit(request: MockEmitRequest) -> WebhookAck:
    """Runtime validation endpoint: inject a mock IM message into the channel bus."""
    from agent_platform.integration.channels import InboundMessage, get_channel_service
    svc = get_channel_service()
    svc.manager.inject_inbound_nowait(InboundMessage(
        channel_type=request.channel,
        chat_id=request.chat_id,
        user_id=request.user_id,
        text=request.text,
    ))
    return WebhookAck(channel=request.channel, accepted=True, pending_messages=svc.manager.bus.inbound_pending)
