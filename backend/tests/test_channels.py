"""IM channel tests (20 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestChannelTypes:
    def test_01_all_types(self):
        from agent_platform.integration.channels import ChannelType
        names = [e.name for e in ChannelType]
        for n in ["FEISHU","SLACK","TELEGRAM","DINGTALK","WECHAT","DISCORD","WECOM"]:
            assert n in names
    def test_02_type_count(self):
        from agent_platform.integration.channels import ChannelType
        assert len(ChannelType) >= 7

class TestMessageBus:
    def test_init(self):
        from agent_platform.integration.channels import MessageBus
        b = MessageBus()
        assert b is not None
    def test_03_publish_inbound(self):
        from agent_platform.integration.channels import MessageBus
        b = MessageBus()
        n = b.publish_inbound({"text": "hello"})
        assert n >= 0
    def test_04_consume_inbound(self):
        from agent_platform.integration.channels import MessageBus
        b = MessageBus()
        b.publish_inbound({"text": "msg1"})
        b.publish_inbound({"text": "msg2"})
        msgs = b.consume_inbound()
        assert len(msgs) >= 1
    def test_05_subscribe_outbound(self):
        from agent_platform.integration.channels import MessageBus
        b = MessageBus()
        received = []
        def cb(msg): received.append(msg)
        cb = b.subscribe_outbound(cb)
        assert cb is not None

class TestChannel:
    def test_01_base_channel(self):
        from agent_platform.integration.channels import Channel, ChannelType
        c = Channel(channel_type=ChannelType.FEISHU)
        assert c.channel_type == ChannelType.FEISHU
    def test_02_feishu_channel(self):
        from agent_platform.integration.channels import FeishuChannel
        c = FeishuChannel({"app_id": "test", "app_secret": "secret"})
        assert c is not None
    def test_03_slack_channel(self):
        from agent_platform.integration.channels import SlackChannel
        c = SlackChannel({"bot_token": "token", "app_token": "app_token"})
        assert c is not None
    def test_04_telegram_channel(self):
        from agent_platform.integration.channels import TelegramChannel
        c = TelegramChannel({"bot_token": "token"})
        assert c is not None
    def test_05_dingtalk_channel(self):
        from agent_platform.integration.channels import DingTalkChannel
        c = DingTalkChannel({"client_id": "id", "client_secret": "secret"})
        assert c is not None
    def test_06_wechat_channel(self):
        from agent_platform.integration.channels import WeChatChannel
        c = WeChatChannel({"app_id": "id", "app_secret": "secret"})
        assert c is not None
    def test_07_discord_channel(self):
        from agent_platform.integration.channels import DiscordChannel
        c = DiscordChannel({"bot_token": "token"})
        assert c is not None
    def test_08_wecom_channel(self):
        from agent_platform.integration.channels import WeComChannel
        c = WeComChannel({"webhook_url": "url", "corp_id": "id", "corp_secret": "secret"})
        assert c is not None

class TestChannelService:
    def test_01_service(self):
        from agent_platform.integration.channels import ChannelService
        s = ChannelService()
        assert not s.is_available()
        assert "stopped" in s.get_status()
    def test_02_service_status(self):
        from agent_platform.integration.channels import ChannelService
        s = ChannelService
        s = ChannelService()
        assert isinstance(s.get_status(), str)
