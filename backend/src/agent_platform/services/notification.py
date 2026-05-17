"""Notification service abstraction layer.

Provides a pluggable notification system supporting multiple channels:
in-app, Feishu, email, SMS, and webhooks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from agent_platform.models.approval import ApprovalStatus, RiskLevel
from agent_platform.models.notification_settings import (
    NotificationChannel,
    NotificationEvent,
    NotificationType,
)
from agent_platform.services.feishu import FeishuClient, FeishuError, get_feishu_client
from agent_platform.templates.feishu_cards import ApprovalCardBuilder


@dataclass
class NotificationMessage:
    """Notification message data structure."""

    title: str
    content: str
    notification_type: NotificationType = NotificationType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)
    card_data: Optional[dict] = None
    priority: str = "normal"  # low, normal, high, urgent
    action_url: Optional[str] = None
    image_url: Optional[str] = None


class NotificationProvider(ABC):
    """Abstract base class for notification providers."""

    @property
    @abstractmethod
    def channel(self) -> NotificationChannel:
        """Return the notification channel this provider handles."""
        pass

    @abstractmethod
    async def send(
        self,
        user_id: str,
        message: NotificationMessage,
        **kwargs: Any,
    ) -> bool:
        """Send notification to user.

        Args:
            user_id: Target user ID
            message: Notification message
            **kwargs: Additional provider-specific arguments

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    async def is_available(self, user_id: str) -> bool:
        """Check if provider is available for the user.

        Args:
            user_id: User ID to check

        Returns:
            True if provider can send to this user
        """
        pass


class InAppNotificationProvider(NotificationProvider):
    """In-app notification provider.

    Stores notifications in the database for display in the UI.
    """

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.IN_APP

    async def send(
        self,
        user_id: str,
        message: NotificationMessage,
        **kwargs: Any,
    ) -> bool:
        """Store notification for in-app display.

        Args:
            user_id: Target user ID
            message: Notification message
            **kwargs: Additional arguments (db_session, etc.)

        Returns:
            True if stored successfully
        """
        from agent_platform.models.notification_settings import NotificationLog

        db_session = kwargs.get("db_session")
        if not db_session:
            # For now, just log the notification
            # In production, this would store in the database
            return True

        # Create notification log entry
        log = NotificationLog(
            user_id=UUID(user_id),
            channel=self.channel.value,
            event_type=kwargs.get("event_type", "unknown"),
            title=message.title,
            content=message.content,
            status="sent",
            metadata=message.metadata,
        )

        try:
            db_session.add(log)
            await db_session.flush()
            return True
        except Exception:
            return False

    async def is_available(self, user_id: str) -> bool:
        """In-app is always available for logged-in users."""
        return True


class FeishuNotificationProvider(NotificationProvider):
    """Feishu (Lark) notification provider.

    Sends notifications via Feishu Bot webhook or Open API.
    """

    def __init__(
        self,
        feishu_client: Optional[FeishuClient] = None,
        default_webhook: Optional[str] = None,
    ):
        """Initialize Feishu notification provider.

        Args:
            feishu_client: FeishuClient instance
            default_webhook: Default webhook URL
        """
        self.client = feishu_client or get_feishu_client()
        self.default_webhook = default_webhook

    @property
    def channel(self) -> NotificationChannel:
        return NotificationChannel.FEISHU

    async def send(
        self,
        user_id: str,
        message: NotificationMessage,
        **kwargs: Any,
    ) -> bool:
        """Send notification via Feishu.

        Args:
            user_id: Target user ID (used to lookup Feishu ID)
            message: Notification message
            **kwargs: Additional arguments (feishu_user_id, webhook, etc.)

        Returns:
            True if sent successfully
        """
        feishu_user_id = kwargs.get("feishu_user_id")
        webhook = kwargs.get("webhook") or self.default_webhook

        try:
            if message.notification_type == NotificationType.INTERACTIVE_CARD:
                # Send interactive card
                card = message.card_data or self._build_default_card(message)
                await self.client.send_card(
                    card=card,
                    open_id=feishu_user_id,
                    webhook=webhook,
                )
            elif message.notification_type == NotificationType.MARKDOWN:
                # Send markdown message
                await self.client.send_text(
                    content=message.content,
                    open_id=feishu_user_id,
                    webhook=webhook,
                )
            else:
                # Send plain text
                full_content = f"**{message.title}**\n\n{message.content}"
                await self.client.send_text(
                    content=full_content,
                    open_id=feishu_user_id,
                    webhook=webhook,
                )

            return True
        except FeishuError as e:
            # Log error but don't raise - notification failures shouldn't break workflows
            print(f"Failed to send Feishu notification: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Feishu notification: {e}")
            return False

    def _build_default_card(self, message: NotificationMessage) -> dict:
        """Build a default card from message.

        Args:
            message: Notification message

        Returns:
            Card JSON data
        """
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": message.title,
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": message.content,
                    },
                },
            ],
        }

    async def is_available(self, user_id: str) -> bool:
        """Check if Feishu is configured.

        Args:
            user_id: User ID (not used for this check)

        Returns:
            True if Feishu client is configured
        """
        return bool(
            self.client and
            (self.client.bot_webhook or self.client.app_id)
        )

    async def send_approval_request(
        self,
        feishu_user_id: str,
        approval_request: dict[str, Any],
        webhook: Optional[str] = None,
    ) -> bool:
        """Send approval request card to user.

        Args:
            feishu_user_id: Feishu user open_id
            approval_request: Approval request data
            webhook: Optional webhook URL

        Returns:
            True if sent successfully
        """
        try:
            card = ApprovalCardBuilder.build_approval_request_card(
                approval_id=approval_request["id"],
                tool_name=approval_request["tool_name"],
                tool_input=approval_request["tool_input"],
                risk_level=RiskLevel(approval_request.get("risk_level", "medium")),
                description=approval_request.get("description"),
                context_summary=approval_request.get("context_summary"),
            )

            await self.client.send_card(
                card=card["card"],
                open_id=feishu_user_id,
                webhook=webhook,
            )
            return True
        except Exception as e:
            print(f"Failed to send approval request: {e}")
            return False

    async def send_task_status(
        self,
        feishu_user_id: str,
        task_id: str,
        task_name: str,
        status: str,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        webhook: Optional[str] = None,
    ) -> bool:
        """Send task status notification.

        Args:
            feishu_user_id: Feishu user open_id
            task_id: Task ID
            task_name: Task name
            status: Task status (completed, failed, etc.)
            result_summary: Optional result summary
            error_message: Optional error message
            webhook: Optional webhook URL

        Returns:
            True if sent successfully
        """
        try:
            if status == "completed":
                card = ApprovalCardBuilder.build_task_completed_card(
                    task_id=task_id,
                    task_name=task_name,
                    result_summary=result_summary,
                )
            else:
                card = ApprovalCardBuilder.build_task_failed_card(
                    task_id=task_id,
                    task_name=task_name,
                    error_message=error_message or "未知错误",
                )

            await self.client.send_card(
                card=card["card"],
                open_id=feishu_user_id,
                webhook=webhook,
            )
            return True
        except Exception as e:
            print(f"Failed to send task status: {e}")
            return False

    async def send_approval_status_change(
        self,
        feishu_user_id: str,
        approval_id: str,
        status: ApprovalStatus,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
        webhook: Optional[str] = None,
    ) -> bool:
        """Send approval status change notification.

        Args:
            feishu_user_id: Feishu user open_id
            approval_id: Approval request ID
            status: New status
            decided_by: Who made the decision
            reason: Optional reason
            webhook: Optional webhook URL

        Returns:
            True if sent successfully
        """
        try:
            if status == ApprovalStatus.APPROVED:
                title = "审批已通过"
                template = "green"
                emoji = ""
            elif status == ApprovalStatus.REJECTED:
                title = "审批已拒绝"
                template = "red"
                emoji = ""
            elif status == ApprovalStatus.ESCALATED:
                title = "审批已升级"
                template = "orange"
                emoji = ""
            else:
                title = f"审批状态更新: {status}"
                template = "blue"
                emoji = ""

            content_parts = [f"{emoji} **{title}**"]
            content_parts.append(f"**审批 ID**: {approval_id}")

            if decided_by:
                content_parts.append(f"**处理人**: {decided_by}")
            if reason:
                content_parts.append(f"**原因**: {reason}")

            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template,
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": "\n".join(content_parts),
                        },
                    },
                ],
            }

            await self.client.send_card(
                card=card,
                open_id=feishu_user_id,
                webhook=webhook,
            )
            return True
        except Exception as e:
            print(f"Failed to send approval status change: {e}")
            return False


class NotificationManager:
    """Notification manager coordinating multiple providers.

    Routes notifications to appropriate channels based on user preferences.
    """

    def __init__(self):
        """Initialize notification manager."""
        self._providers: dict[NotificationChannel, NotificationProvider] = {}

    def register_provider(
        self,
        channel: NotificationChannel,
        provider: NotificationProvider,
    ) -> None:
        """Register a notification provider.

        Args:
            channel: Notification channel
            provider: Provider instance
        """
        self._providers[channel] = provider

    def unregister_provider(self, channel: NotificationChannel) -> None:
        """Unregister a notification provider.

        Args:
            channel: Notification channel to remove
        """
        if channel in self._providers:
            del self._providers[channel]

    async def send(
        self,
        user_id: str,
        channels: list[NotificationChannel],
        message: NotificationMessage,
        **kwargs: Any,
    ) -> dict[NotificationChannel, bool]:
        """Send notification through multiple channels.

        Args:
            user_id: Target user ID
            channels: List of channels to use
            message: Notification message
            **kwargs: Additional provider arguments

        Returns:
            Dictionary mapping channels to success status
        """
        results: dict[NotificationChannel, bool] = {}

        for channel in channels:
            provider = self._providers.get(channel)
            if not provider:
                results[channel] = False
                continue

            if not await provider.is_available(user_id):
                results[channel] = False
                continue

            success = await provider.send(user_id, message, **kwargs)
            results[channel] = success

        return results

    async def send_approval_request(
        self,
        user_id: str,
        channels: list[NotificationChannel],
        approval_request: dict[str, Any],
        **kwargs: Any,
    ) -> dict[NotificationChannel, bool]:
        """Send approval request notification.

        Args:
            user_id: Target user ID
            channels: List of channels to use
            approval_request: Approval request data
            **kwargs: Additional arguments (feishu_user_id, etc.)

        Returns:
            Dictionary mapping channels to success status
        """
        results: dict[NotificationChannel, bool] = {}

        for channel in channels:
            provider = self._providers.get(channel)
            if not provider:
                results[channel] = False
                continue

            if channel == NotificationChannel.FEISHU:
                if isinstance(provider, FeishuNotificationProvider):
                    feishu_user_id = kwargs.get("feishu_user_id")
                    if feishu_user_id:
                        success = await provider.send_approval_request(
                            feishu_user_id=feishu_user_id,
                            approval_request=approval_request,
                            webhook=kwargs.get("webhook"),
                        )
                        results[channel] = success
                    else:
                        results[channel] = False
                else:
                    results[channel] = False
            else:
                # Generic notification for other channels
                message = NotificationMessage(
                    title="Agent 请求审批",
                    content=f"新的审批请求: {approval_request.get('description', '无描述')}",
                    notification_type=NotificationType.TEXT,
                    metadata={"approval_id": approval_request.get("id")},
                )
                success = await provider.send(user_id, message, **kwargs)
                results[channel] = success

        return results

    async def send_task_status(
        self,
        user_id: str,
        channels: list[NotificationChannel],
        task_id: str,
        task_name: str,
        status: str,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[NotificationChannel, bool]:
        """Send task status notification.

        Args:
            user_id: Target user ID
            channels: List of channels to use
            task_id: Task ID
            task_name: Task name
            status: Task status
            result_summary: Optional result summary
            error_message: Optional error message
            **kwargs: Additional arguments

        Returns:
            Dictionary mapping channels to success status
        """
        results: dict[NotificationChannel, bool] = {}

        for channel in channels:
            provider = self._providers.get(channel)
            if not provider:
                results[channel] = False
                continue

            if channel == NotificationChannel.FEISHU:
                if isinstance(provider, FeishuNotificationProvider):
                    feishu_user_id = kwargs.get("feishu_user_id")
                    if feishu_user_id:
                        success = await provider.send_task_status(
                            feishu_user_id=feishu_user_id,
                            task_id=task_id,
                            task_name=task_name,
                            status=status,
                            result_summary=result_summary,
                            error_message=error_message,
                            webhook=kwargs.get("webhook"),
                        )
                        results[channel] = success
                    else:
                        results[channel] = False
                else:
                    results[channel] = False
            else:
                # Generic notification for other channels
                if status == "completed":
                    title = f"任务完成: {task_name}"
                    content = result_summary or "任务已成功完成"
                else:
                    title = f"任务失败: {task_name}"
                    content = error_message or "任务执行失败"

                message = NotificationMessage(
                    title=title,
                    content=content,
                    notification_type=NotificationType.TEXT,
                    metadata={"task_id": task_id, "status": status},
                )
                success = await provider.send(user_id, message, **kwargs)
                results[channel] = success

        return results

    async def send_approval_status_change(
        self,
        user_id: str,
        channels: list[NotificationChannel],
        approval_id: str,
        status: ApprovalStatus,
        decided_by: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[NotificationChannel, bool]:
        """Send approval status change notification.

        Args:
            user_id: Target user ID
            channels: List of channels to use
            approval_id: Approval request ID
            status: New status
            decided_by: Who made the decision
            reason: Optional reason
            **kwargs: Additional arguments

        Returns:
            Dictionary mapping channels to success status
        """
        results: dict[NotificationChannel, bool] = {}

        for channel in channels:
            provider = self._providers.get(channel)
            if not provider:
                results[channel] = False
                continue

            if channel == NotificationChannel.FEISHU:
                if isinstance(provider, FeishuNotificationProvider):
                    feishu_user_id = kwargs.get("feishu_user_id")
                    if feishu_user_id:
                        success = await provider.send_approval_status_change(
                            feishu_user_id=feishu_user_id,
                            approval_id=approval_id,
                            status=status,
                            decided_by=decided_by,
                            reason=reason,
                            webhook=kwargs.get("webhook"),
                        )
                        results[channel] = success
                    else:
                        results[channel] = False
                else:
                    results[channel] = False
            else:
                # Generic notification
                status_text = "已通过" if status == ApprovalStatus.APPROVED else "已拒绝"
                message = NotificationMessage(
                    title=f"审批状态更新: {status_text}",
                    content=f"审批 ID: {approval_id}",
                    notification_type=NotificationType.TEXT,
                    metadata={"approval_id": approval_id, "status": status.value},
                )
                success = await provider.send(user_id, message, **kwargs)
                results[channel] = success

        return results

    def get_available_channels(self, user_id: str) -> list[NotificationChannel]:
        """Get list of available channels for a user.

        Args:
            user_id: User ID

        Returns:
            List of available notification channels
        """
        available = []
        for channel, provider in self._providers.items():
            # Use a simple synchronous check for availability
            # In production, this might need to be async
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, schedule the check
                    # For simplicity, assume available
                    available.append(channel)
                else:
                    if asyncio.run(provider.is_available(user_id)):
                        available.append(channel)
            except Exception:
                # If check fails, assume not available
                pass
        return available


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get or create notification manager singleton.

    Returns:
        NotificationManager instance with default providers registered
    """
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()

        # Register default providers
        _notification_manager.register_provider(
            NotificationChannel.IN_APP,
            InAppNotificationProvider(),
        )

        # Try to register Feishu provider if configured
        try:
            feishu_client = get_feishu_client()
            if feishu_client.bot_webhook or feishu_client.app_id:
                _notification_manager.register_provider(
                    NotificationChannel.FEISHU,
                    FeishuNotificationProvider(feishu_client),
                )
        except Exception:
            # Feishu not configured, skip
            pass

    return _notification_manager


def set_notification_manager(manager: NotificationManager) -> None:
    """Set notification manager singleton (for testing).

    Args:
        manager: NotificationManager instance
    """
    global _notification_manager
    _notification_manager = manager
