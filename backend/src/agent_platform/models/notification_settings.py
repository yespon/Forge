"""Notification settings models for user notification preferences."""

from datetime import datetime, time
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.org import Org
    from agent_platform.models.user import User


class NotificationChannel(str, Enum):
    """Notification channel enumeration."""

    IN_APP = "in_app"
    FEISHU = "feishu"
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


class NotificationType(str, Enum):
    """Notification type enumeration."""

    TEXT = "text"
    MARKDOWN = "markdown"
    INTERACTIVE_CARD = "interactive_card"
    IMAGE = "image"


class NotificationEvent(str, Enum):
    """Notification event type enumeration."""

    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_APPROVED = "approval_approved"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_ESCALATED = "approval_escalated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    SYSTEM_ALERT = "system_alert"


class NotificationSettings(Base):
    """User notification settings model.

    Stores user preferences for notification channels, quiet hours,
    and channel-specific settings (e.g., Feishu user ID binding).
    """

    __tablename__ = "notification_settings"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    org_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Enabled notification channels
    enabled_channels: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: [NotificationChannel.IN_APP],
        nullable=False,
    )

    # Enabled notification events
    enabled_events: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: [e.value for e in NotificationEvent],
        nullable=False,
    )

    # Quiet hours configuration
    quiet_hours_start: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Start time for quiet hours (no notifications)"
    )
    quiet_hours_end: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="End time for quiet hours"
    )
    quiet_hours_timezone: Mapped[str] = mapped_column(
        String(50),
        default="UTC",
        nullable=False,
    )

    # Channel-specific settings
    # Feishu
    feishu_user_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Feishu open_id for the user"
    )
    feishu_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Email
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    email_address_override: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Override email address for notifications"
    )

    # Webhook
    webhook_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Custom webhook URL for notifications"
    )
    webhook_secret: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Secret for webhook signature verification"
    )

    # Event-specific settings (JSON for flexibility)
    event_settings: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
        comment="Per-event notification settings"
    )

    # Extra metadata for extensibility (renamed to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notification_settings")
    org: Mapped["Org"] = relationship("Org", back_populates="notification_settings")

    def is_channel_enabled(self, channel: NotificationChannel) -> bool:
        """Check if a notification channel is enabled.

        Args:
            channel: The notification channel to check

        Returns:
            True if the channel is enabled, False otherwise
        """
        return channel.value in self.enabled_channels

    def is_event_enabled(self, event: NotificationEvent) -> bool:
        """Check if a notification event type is enabled.

        Args:
            event: The notification event to check

        Returns:
            True if the event is enabled, False otherwise
        """
        return event.value in self.enabled_events

    def is_quiet_hours(self, current_time: Optional[time] = None) -> bool:
        """Check if current time is within quiet hours.

        Args:
            current_time: Time to check (defaults to now)

        Returns:
            True if within quiet hours, False otherwise
        """
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False

        if current_time is None:
            from datetime import datetime as dt
            current_time = dt.now().time()

        # Handle overnight quiet hours (e.g., 22:00 to 08:00)
        if self.quiet_hours_start > self.quiet_hours_end:
            return current_time >= self.quiet_hours_start or current_time <= self.quiet_hours_end
        else:
            return self.quiet_hours_start <= current_time <= self.quiet_hours_end

    def get_enabled_channels_for_event(
        self,
        event: NotificationEvent,
    ) -> list[NotificationChannel]:
        """Get enabled channels for a specific event type.

        Args:
            event: The notification event

        Returns:
            List of enabled notification channels
        """
        if not self.is_event_enabled(event):
            return []

        # Check event-specific overrides
        event_config = self.event_settings.get(event.value, {})
        if "channels" in event_config:
            channels = [
                NotificationChannel(c) for c in event_config["channels"]
                if c in self.enabled_channels
            ]
            return channels

        return [NotificationChannel(c) for c in self.enabled_channels]

    def to_dict(self) -> dict:
        """Convert notification settings to dictionary.

        Returns:
            Dictionary representation of notification settings
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "org_id": str(self.org_id),
            "enabled_channels": self.enabled_channels,
            "enabled_events": self.enabled_events,
            "quiet_hours_start": self.quiet_hours_start.isoformat() if self.quiet_hours_start else None,
            "quiet_hours_end": self.quiet_hours_end.isoformat() if self.quiet_hours_end else None,
            "quiet_hours_timezone": self.quiet_hours_timezone,
            "feishu_user_id": self.feishu_user_id,
            "feishu_enabled": self.feishu_enabled,
            "email_enabled": self.email_enabled,
            "email_address_override": self.email_address_override,
            "webhook_url": self.webhook_url,
            "event_settings": self.event_settings,
            "metadata": self.extra_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class NotificationLog(Base):
    """Notification log model for tracking sent notifications.

    Records all sent notifications for auditing and debugging purposes.
    """

    __tablename__ = "notification_logs"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification details
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        String(4000),
        nullable=False,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )  # pending, sent, failed, read

    # External tracking
    external_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="External ID from notification provider (e.g., Feishu message ID)"
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Extra metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def mark_as_sent(self, external_id: Optional[str] = None) -> None:
        """Mark notification as sent.

        Args:
            external_id: Optional external ID from provider
        """
        self.status = "sent"
        self.sent_at = datetime.utcnow()
        if external_id:
            self.external_id = external_id

    def mark_as_failed(self, error_message: str) -> None:
        """Mark notification as failed.

        Args:
            error_message: Error message explaining failure
        """
        self.status = "failed"
        self.error_message = error_message

    def mark_as_read(self) -> None:
        """Mark notification as read."""
        self.status = "read"
        self.read_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert notification log to dictionary.

        Returns:
            Dictionary representation of notification log
        """
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "channel": self.channel,
            "event_type": self.event_type,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "external_id": self.external_id,
            "error_message": self.error_message,
            "metadata": self.extra_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }
