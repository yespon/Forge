"""Tests for Feishu notification system."""

import json
import pytest
from datetime import datetime, time
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from httpx import Response as HttpxResponse

from agent_platform.models.notification_settings import (
    NotificationChannel,
    NotificationSettings,
    NotificationType,
)
from agent_platform.models.approval import ApprovalStatus, RiskLevel
from agent_platform.services.feishu import FeishuClient, FeishuError
from agent_platform.services.notification import (
    FeishuNotificationProvider,
    InAppNotificationProvider,
    NotificationManager,
    NotificationProvider,
)
from agent_platform.templates.feishu_cards import (
    ApprovalCardBuilder,
    CardColor,
    CardTemplate,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    with patch("agent_platform.services.feishu.httpx.AsyncClient") as mock:
        # Create an async context manager mock
        client = AsyncMock()
        # Make client itself an async context manager
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        # Ensure all common HTTP methods are AsyncMock
        client.post = AsyncMock()
        client.get = AsyncMock()
        client.request = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def feishu_client(mock_httpx_client):
    """Create a FeishuClient with mocked HTTP client."""
    client = FeishuClient(
        app_id="test_app_id",
        app_secret="test_app_secret",
        bot_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/test-webhook",
    )
    # Pre-set a valid token to avoid triggering _refresh_token
    import time as time_module
    client._access_token = "test_access_token"
    client._token_expires_at = time_module.time() + 7200  # 2 hours from now
    return client


@pytest.fixture
def sample_approval_request():
    """Create a sample approval request for testing."""
    return {
        "id": str(uuid4()),
        "tool_name": "execute_bash",
        "tool_input": {"command": "rm -rf /important/data"},
        "risk_level": RiskLevel.CRITICAL,
        "description": "删除重要数据",
        "context_summary": "Agent 尝试删除系统目录",
        "approvers": [{"user_id": str(uuid4()), "role": "admin"}],
        "strategy": "single",
        "status": ApprovalStatus.PENDING,
        "requested_at": datetime.utcnow().isoformat(),
    }


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return {
        "id": str(uuid4()),
        "email": "test@example.com",
        "display_name": "Test User",
    }


# =============================================================================
# Feishu SDK Tests
# =============================================================================

class TestFeishuClient:
    """Tests for FeishuClient."""

    @pytest.mark.asyncio
    async def test_init(self, feishu_client):
        """Test FeishuClient initialization."""
        assert feishu_client.app_id == "test_app_id"
        assert feishu_client.app_secret == "test_app_secret"
        assert feishu_client.bot_webhook == "https://open.feishu.cn/open-apis/bot/v2/hook/test-webhook"

    @pytest.mark.asyncio
    async def test_send_text_message(self, feishu_client, mock_httpx_client):
        """Test sending text message via webhook."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"code": 0, "msg": "success"})
        mock_httpx_client.post.return_value = mock_response

        result = await feishu_client.send_text(
            open_id="user_open_id",
            content="Test message",
        )

        assert result is True
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args[0][0] == feishu_client.bot_webhook
        assert call_args[1]["json"]["msg_type"] == "text"
        assert "Test message" in call_args[1]["json"]["content"]["text"]

    @pytest.mark.asyncio
    async def test_send_interactive_card(self, feishu_client, mock_httpx_client):
        """Test sending interactive card."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"code": 0, "msg": "success"})
        mock_httpx_client.post.return_value = mock_response

        card_data = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": "Test"},
                    "template": "red",
                },
                "elements": [],
            },
        }

        result = await feishu_client.send_card(
            open_id="user_open_id",
            card=card_data,
        )

        assert result is True
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_failure(self, feishu_client, mock_httpx_client):
        """Test handling of send message failure."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"code": 9499, "msg": "Bad Request"})
        mock_httpx_client.post.return_value = mock_response

        with pytest.raises(FeishuError) as exc_info:
            await feishu_client.send_text(
                open_id="user_open_id",
                content="Test message",
            )

        assert exc_info.value.code == 9499
        assert "Bad Request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_id_by_email(self, feishu_client, mock_httpx_client):
        """Test getting user ID by email."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "code": 0,
            "data": {
                "user_list": [
                    {"user_id": "ou_12345", "email": "test@example.com"}
                ]
            },
        })
        mock_httpx_client.request.return_value = mock_response

        user_id = await feishu_client.get_user_id_by_email("test@example.com")

        assert user_id == "ou_12345"

    @pytest.mark.asyncio
    async def test_get_user_id_by_email_not_found(self, feishu_client, mock_httpx_client):
        """Test getting user ID by email when user not found."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "code": 0,
            "data": {"user_list": []},
        })
        mock_httpx_client.request.return_value = mock_response

        user_id = await feishu_client.get_user_id_by_email("nonexistent@example.com")

        assert user_id is None

    @pytest.mark.asyncio
    async def test_verify_webhook_signature(self, feishu_client):
        """Test webhook signature verification."""
        # Test with known signature
        timestamp = "1600245000"
        secret = "test_secret"
        body = '{"event_type":"card.action.trigger"}'

        # Calculate expected signature
        import hashlib
        import base64
        import hmac

        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hmac_code).decode("utf-8")

        is_valid = feishu_client.verify_webhook_signature(
            signature=expected_signature,
            timestamp=timestamp,
            body=body,
            secret=secret,
        )

        assert is_valid is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid(self, feishu_client):
        """Test webhook signature verification with invalid signature."""
        is_valid = feishu_client.verify_webhook_signature(
            signature="invalid_signature",
            timestamp="1600245000",
            body='{"event_type":"test"}',
            secret="test_secret",
        )

        assert is_valid is False


# =============================================================================
# Card Template Tests
# =============================================================================

class TestApprovalCardBuilder:
    """Tests for ApprovalCardBuilder."""

    def test_build_approval_request_card(self, sample_approval_request):
        """Test building approval request card."""
        card = ApprovalCardBuilder.build_approval_request_card(
            approval_id=sample_approval_request["id"],
            tool_name=sample_approval_request["tool_name"],
            tool_input=sample_approval_request["tool_input"],
            risk_level=sample_approval_request["risk_level"],
            description=sample_approval_request["description"],
            context_summary=sample_approval_request["context_summary"],
        )

        assert card["msg_type"] == "interactive"
        assert card["card"]["config"]["wide_screen_mode"] is True
        assert "Agent 请求审批" in card["card"]["header"]["title"]["content"]
        assert card["card"]["header"]["template"] == "red"
        assert len(card["card"]["elements"]) > 0

        # Check for action buttons
        action_element = next(
            (e for e in card["card"]["elements"] if e.get("tag") == "action"),
            None
        )
        assert action_element is not None
        actions = action_element.get("actions", [])
        assert len(actions) == 2  # Approve and Reject buttons

    def test_build_approval_request_card_medium_risk(self, sample_approval_request):
        """Test building approval request card with medium risk."""
        card = ApprovalCardBuilder.build_approval_request_card(
            approval_id=sample_approval_request["id"],
            tool_name="execute_sql",
            tool_input={"command": "SELECT * FROM users"},
            risk_level=RiskLevel.MEDIUM,
            description="查询用户数据",
            context_summary="Agent 执行查询操作",
        )

        assert card["card"]["header"]["template"] == "blue"

    def test_build_task_completed_card(self, sample_approval_request):
        """Test building task completed card."""
        card = ApprovalCardBuilder.build_task_completed_card(
            task_id=sample_approval_request["id"],
            task_name="数据分析任务",
            result_summary="成功处理了 1000 条记录",
        )

        assert card["card"]["header"]["template"] == "green"
        assert "任务完成" in card["card"]["header"]["title"]["content"]
        assert "数据分析任务" in str(card["card"]["elements"])

    def test_build_task_failed_card(self, sample_approval_request):
        """Test building task failed card."""
        card = ApprovalCardBuilder.build_task_failed_card(
            task_id=sample_approval_request["id"],
            task_name="数据分析任务",
            error_message="数据库连接超时",
        )

        assert card["card"]["header"]["template"] == "orange"
        assert "任务失败" in card["card"]["header"]["title"]["content"]
        assert "数据库连接超时" in str(card["card"]["elements"])

    def test_card_color_mapping(self):
        """Test risk level to card color mapping."""
        assert CardTemplate.risk_to_color(RiskLevel.CRITICAL) == CardColor.RED
        assert CardTemplate.risk_to_color(RiskLevel.HIGH) == CardColor.ORANGE
        assert CardTemplate.risk_to_color(RiskLevel.MEDIUM) == CardColor.BLUE
        assert CardTemplate.risk_to_color(RiskLevel.LOW) == CardColor.GREEN


# =============================================================================
# Notification Provider Tests
# =============================================================================

class TestNotificationProviders:
    """Tests for notification providers."""

    @pytest.mark.asyncio
    async def test_in_app_provider(self, sample_user):
        """Test InAppNotificationProvider."""
        from agent_platform.services.notification import NotificationMessage
        provider = InAppNotificationProvider()

        message = NotificationMessage(
            title="Test Notification",
            content="Test content",
            metadata={"key": "value"},
        )
        result = await provider.send(
            user_id=sample_user["id"],
            message=message,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_feishu_provider_send_text(self, sample_user, feishu_client, mock_httpx_client):
        """Test FeishuNotificationProvider sending text."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"code": 0, "msg": "success"})
        mock_httpx_client.post.return_value = mock_response

        provider = FeishuNotificationProvider(feishu_client)

        from agent_platform.services.notification import NotificationMessage
        message = NotificationMessage(
            title="Test Notification",
            content="Test content",
            notification_type=NotificationType.TEXT,
        )
        result = await provider.send(
            user_id=sample_user["id"],
            message=message,
            feishu_user_id="ou_test_user",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_feishu_provider_send_card(self, sample_user, feishu_client, mock_httpx_client):
        """Test FeishuNotificationProvider sending card."""
        mock_response = Mock(spec=HttpxResponse)
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={"code": 0, "msg": "success"})
        mock_httpx_client.post.return_value = mock_response

        provider = FeishuNotificationProvider(feishu_client)

        card_data = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "Test"},
                "template": "red",
            },
            "elements": [],
        }

        from agent_platform.services.notification import NotificationMessage
        message = NotificationMessage(
            title="Test",
            content="Test content",
            notification_type=NotificationType.INTERACTIVE_CARD,
            card_data=card_data,
        )
        result = await provider.send(
            user_id=sample_user["id"],
            message=message,
            feishu_user_id="ou_test_user",
        )

        assert result is True


# =============================================================================
# Notification Manager Tests
# =============================================================================

class TestNotificationManager:
    """Tests for NotificationManager."""

    @pytest.mark.asyncio
    async def test_register_provider(self):
        """Test registering a provider."""
        manager = NotificationManager()
        provider = InAppNotificationProvider()

        manager.register_provider(NotificationChannel.IN_APP, provider)

        assert NotificationChannel.IN_APP in manager._providers

    @pytest.mark.asyncio
    async def test_send_to_single_channel(self, sample_user):
        """Test sending notification to single channel."""
        manager = NotificationManager()
        provider = InAppNotificationProvider()
        manager.register_provider(NotificationChannel.IN_APP, provider)

        from agent_platform.services.notification import NotificationMessage
        message = NotificationMessage(
            title="Test",
            content="Test content",
        )
        result = await manager.send(
            user_id=sample_user["id"],
            channels=[NotificationChannel.IN_APP],
            message=message,
        )

        assert result[NotificationChannel.IN_APP] is True

    @pytest.mark.asyncio
    async def test_send_to_multiple_channels(self, sample_user):
        """Test sending notification to multiple channels."""
        manager = NotificationManager()
        in_app_provider = InAppNotificationProvider()
        manager.register_provider(NotificationChannel.IN_APP, in_app_provider)

        with patch.object(
            FeishuNotificationProvider, "send", return_value=True
        ) as mock_send:
            mock_feishu = Mock(spec=FeishuNotificationProvider)
            mock_send.return_value = True
            manager.register_provider(NotificationChannel.FEISHU, mock_feishu)

            from agent_platform.services.notification import NotificationMessage
            message = NotificationMessage(
                title="Test",
                content="Test content",
            )
            result = await manager.send(
                user_id=sample_user["id"],
                channels=[NotificationChannel.IN_APP, NotificationChannel.FEISHU],
                message=message,
            )

            assert NotificationChannel.IN_APP in result

    @pytest.mark.asyncio
    async def test_send_approval_notification(self, sample_user, sample_approval_request):
        """Test sending approval notification."""
        manager = NotificationManager()

        mock_feishu = AsyncMock(spec=FeishuNotificationProvider)
        mock_feishu.send_approval_request = AsyncMock(return_value=True)
        manager.register_provider(NotificationChannel.FEISHU, mock_feishu)

        result = await manager.send_approval_request(
            user_id=sample_user["id"],
            channels=[NotificationChannel.FEISHU],
            approval_request=sample_approval_request,
            feishu_user_id="ou_test_user",
        )

        assert result[NotificationChannel.FEISHU] is True
        mock_feishu.send_approval_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_task_status_notification(self, sample_user):
        """Test sending task status notification."""
        manager = NotificationManager()

        mock_provider = AsyncMock(spec=FeishuNotificationProvider)
        mock_provider.send_task_status = AsyncMock(return_value=True)
        manager.register_provider(NotificationChannel.FEISHU, mock_provider)

        result = await manager.send_task_status(
            user_id=sample_user["id"],
            channels=[NotificationChannel.FEISHU],
            task_id=str(uuid4()),
            task_name="测试任务",
            status="completed",
            result_summary="任务成功完成",
            feishu_user_id="ou_test_user",
        )

        assert result[NotificationChannel.FEISHU] is True


# =============================================================================
# Notification Settings Tests
# =============================================================================

class TestNotificationSettings:
    """Tests for notification settings models."""

    def test_notification_settings_creation(self):
        """Test creating notification settings."""
        settings = NotificationSettings(
            id=uuid4(),
            user_id=uuid4(),
            org_id=uuid4(),
            enabled_channels=[NotificationChannel.IN_APP],
            extra_metadata={},
        )

        assert settings.enabled_channels == [NotificationChannel.IN_APP]
        assert settings.quiet_hours_start is None
        assert settings.quiet_hours_end is None
        assert settings.extra_metadata == {}

    def test_notification_settings_with_channels(self):
        """Test notification settings with specific channels."""
        settings = NotificationSettings(
            id=uuid4(),
            user_id=uuid4(),
            org_id=uuid4(),
            enabled_channels=[NotificationChannel.IN_APP, NotificationChannel.FEISHU],
            feishu_user_id="ou_12345",
        )

        assert NotificationChannel.FEISHU in settings.enabled_channels
        assert settings.feishu_user_id == "ou_12345"

    def test_is_channel_enabled(self):
        """Test checking if a channel is enabled."""
        settings = NotificationSettings(
            id=uuid4(),
            user_id=uuid4(),
            org_id=uuid4(),
            enabled_channels=[NotificationChannel.IN_APP, NotificationChannel.FEISHU],
        )

        assert settings.is_channel_enabled(NotificationChannel.IN_APP) is True
        assert settings.is_channel_enabled(NotificationChannel.FEISHU) is True
        assert settings.is_channel_enabled(NotificationChannel.EMAIL) is False

    def test_is_quiet_hours(self):
        """Test quiet hours checking."""
        settings = NotificationSettings(
            id=uuid4(),
            user_id=uuid4(),
            org_id=uuid4(),
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(8, 0),
        )

        # Test within quiet hours
        assert settings.is_quiet_hours(time(23, 0)) is True
        assert settings.is_quiet_hours(time(3, 0)) is True

        # Test outside quiet hours
        assert settings.is_quiet_hours(time(12, 0)) is False
        assert settings.is_quiet_hours(time(9, 0)) is False

    def test_is_quiet_hours_no_settings(self):
        """Test quiet hours checking with no settings."""
        settings = NotificationSettings(
            id=uuid4(),
            user_id=uuid4(),
            org_id=uuid4(),
        )

        assert settings.is_quiet_hours(time(23, 0)) is False


# =============================================================================
# Webhook Handler Tests
# =============================================================================

class TestWebhookHandlers:
    """Tests for webhook handlers."""

    def test_verify_feishu_signature(self):
        """Test Feishu webhook signature verification."""
        from agent_platform.api.v1.webhooks import verify_feishu_signature

        # Create test signature
        import hashlib
        import base64
        import hmac

        timestamp = "1600245000"
        nonce = "nonce123"
        secret = "test_secret"
        body = '{"event_type":"card.action.trigger"}'

        # Calculate expected signature (Feishu format: key is secret, msg is timestamp\nnonce\nsecret\nbody)
        string_to_sign = f"{timestamp}\n{nonce}\n{secret}\n{body}"
        hmac_code = hmac.new(
            key=secret.encode("utf-8"),
            msg=string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        expected_signature = base64.b64encode(hmac_code).decode("utf-8")

        is_valid = verify_feishu_signature(
            signature=expected_signature,
            timestamp=timestamp,
            nonce=nonce,
            body=body,
            secret=secret,
        )

        assert is_valid is True

    def test_parse_card_action(self):
        """Test parsing card action from webhook payload."""
        from agent_platform.api.v1.webhooks import parse_card_action

        payload = {
            "event_type": "card.action.trigger",
            "token": "test_token",
            "open_id": "ou_12345",
            "open_message_id": "om_67890",
            "action": {
                "value": {
                    "action": "approve",
                    "approval_id": "uuid-123",
                    "user_id": "user-456",
                },
                "tag": "button",
            },
        }

        action = parse_card_action(payload)

        assert action is not None
        assert action["action_type"] == "approve"
        assert action["approval_id"] == "uuid-123"
        assert action["user_id"] == "user-456"
        assert action["open_id"] == "ou_12345"

    def test_parse_card_action_invalid(self):
        """Test parsing invalid card action."""
        from agent_platform.api.v1.webhooks import parse_card_action

        # Missing action value
        payload = {
            "event_type": "card.action.trigger",
            "action": {"tag": "button"},
        }

        action = parse_card_action(payload)

        assert action is None


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_notification_flow(
    sample_user, sample_approval_request, mock_httpx_client
):
    """Test complete notification flow from approval to notification."""
    # Mock Feishu API responses
    mock_response = Mock(spec=HttpxResponse)
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0, "msg": "success"}
    mock_httpx_client.post.return_value = mock_response

    # Create notification manager with Feishu provider
    manager = NotificationManager()
    feishu_client = FeishuClient(
        app_id="test_app_id",
        app_secret="test_app_secret",
        bot_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/test",
    )
    feishu_provider = FeishuNotificationProvider(feishu_client)
    manager.register_provider(NotificationChannel.FEISHU, feishu_provider)

    # Send approval notification
    import time as time_module
    feishu_client._access_token = "test_access_token"
    feishu_client._token_expires_at = time_module.time() + 7200

    result = await manager.send_approval_request(
        user_id=sample_user["id"],
        channels=[NotificationChannel.FEISHU],
        approval_request=sample_approval_request,
        feishu_user_id="ou_test_user",
    )

    assert result[NotificationChannel.FEISHU] is True
    mock_httpx_client.post.assert_called()


@pytest.mark.asyncio
async def test_approval_status_change_notification(sample_user, mock_httpx_client):
    """Test notification on approval status change."""
    mock_response = Mock(spec=HttpxResponse)
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0, "msg": "success"}
    mock_httpx_client.post.return_value = mock_response

    manager = NotificationManager()
    feishu_client = FeishuClient(
        app_id="test_app_id",
        app_secret="test_app_secret",
        bot_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/test",
    )
    feishu_provider = FeishuNotificationProvider(feishu_client)
    manager.register_provider(NotificationChannel.FEISHU, feishu_provider)

    # Pre-set token to avoid refresh
    import time as time_module
    feishu_client._access_token = "test_access_token"
    feishu_client._token_expires_at = time_module.time() + 7200

    # Send approval status change notification
    result = await manager.send_approval_status_change(
        user_id=sample_user["id"],
        channels=[NotificationChannel.FEISHU],
        approval_id=str(uuid4()),
        status=ApprovalStatus.APPROVED,
        decided_by="admin@example.com",
        feishu_user_id="ou_test_user",
    )

    assert result[NotificationChannel.FEISHU] is True
