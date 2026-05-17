"""Connector models for external service integrations."""

import enum
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from agent_platform.database import Base


class AuthType(str, enum.Enum):
    """Connector authentication type."""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"
    NONE = "none"


class ConnectorStatus(str, enum.Enum):
    """Connector registry status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"


class ConnectionStatus(str, enum.Enum):
    """Connection binding status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"
    PENDING = "pending"


class ConnectionVisibility(str, enum.Enum):
    """Visibility scope for a connection."""
    ORG = "org"
    TEAM = "team"
    USER = "user"


class Connector(Base):
    """Connector registry — describes an available external service."""

    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    auth_type = Column(
        Enum(AuthType, name="auth_type_enum"),
        nullable=False,
        default=AuthType.API_KEY,
    )
    supported_scopes = Column(JSONB, nullable=False, default=list)
    config_schema = Column(JSONB, nullable=True)
    status = Column(
        Enum(ConnectorStatus, name="connector_status_enum"),
        nullable=False,
        default=ConnectorStatus.ACTIVE,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "auth_type": self.auth_type,
            "supported_scopes": self.supported_scopes,
            "status": self.status,
        }


class ConnectorConnection(Base):
    """A binding between a connector and a user/org/team with credentials."""

    __tablename__ = "connector_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    connector_id = Column(
        UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    team_id = Column(UUID(as_uuid=True), nullable=True)
    visibility = Column(
        Enum(ConnectionVisibility, name="connection_visibility_enum"),
        nullable=False,
        default=ConnectionVisibility.ORG,
    )
    scopes = Column(JSONB, nullable=False, default=list)
    vault_ref = Column(String(500), nullable=True)
    status = Column(
        Enum(ConnectionStatus, name="connection_status_enum"),
        nullable=False,
        default=ConnectionStatus.PENDING,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    extra_metadata = Column(JSONB, nullable=True, default=dict)

    __table_args__ = (
        Index("ix_connections_connector_org", "connector_id", "org_id"),
        UniqueConstraint(
            "connector_id", "org_id", "user_id",
            name="uq_connection_per_user",
        ),
    )

    @property
    def is_active(self) -> bool:
        if self.status != ConnectionStatus.ACTIVE:
            return False
        if self.expires_at and self.expires_at < datetime.now(timezone.utc):
            return False
        return True

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "connector_id": str(self.connector_id),
            "org_id": str(self.org_id),
            "user_id": str(self.user_id) if self.user_id else None,
            "visibility": self.visibility,
            "scopes": self.scopes,
            "status": self.status,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }
