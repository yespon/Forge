"""IM channel tests."""
import os, sys; from pathlib import Path; import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

@pytest.mark.asyncio
class TestMessageBus:
    async def test_01_publish_inbound(self):
        from agent_platform.integration.channels import MessageBus, InboundMessage
        b = MessageBus()
        await b.publish_inbound(InboundMessage(text="hello", channel_type="test"))
        assert b.inbound_pending >= 1
    async def test_02_consume_inbound(self):
        from agent_platform.integration.channels import MessageBus, InboundMessage
        b = MessageBus()
        await b.publish_inbound(InboundMessage(text="msg1", channel_type="test"))
        m = await b.consume_inbound()
        assert m.text == "msg1"
    def test_03_subscribe_outbound(self):
        from agent_platform.integration.channels import MessageBus
        b = MessageBus()
        seen=[]
        b.subscribe_outbound('feishu', lambda msg: seen.append(msg))
        assert 'feishu' in b._outbound_callbacks

class TestChannelImpls:
    def test_01_feishu(self):
        from agent_platform.integration.channels import FeishuChannel, MessageBus
        c = FeishuChannel(MessageBus(), {"app_id":"x","app_secret":"y"})
        assert c.channel_type == 'feishu'
    def test_02_slack(self):
        from agent_platform.integration.channels import SlackChannel, MessageBus
        c = SlackChannel(MessageBus(), {"bot_token":"x","app_token":"y"})
        assert c.channel_type == 'slack'
    def test_03_telegram(self):
        from agent_platform.integration.channels import TelegramChannel, MessageBus
        c = TelegramChannel(MessageBus(), {"bot_token":"x"})
        assert c.channel_type == 'telegram'
    def test_04_dingtalk(self):
        from agent_platform.integration.channels import DingTalkChannel, MessageBus
        c = DingTalkChannel(MessageBus(), {"client_id":"x","client_secret":"y"})
        assert c.channel_type == 'dingtalk'
    def test_05_wechat(self):
        from agent_platform.integration.channels import WeChatChannel
        c = WeChatChannel({"app_id":"x","app_secret":"y"})
        assert c.channel_type == 'wechat'
    def test_06_discord(self):
        from agent_platform.integration.channels import DiscordChannel
        c = DiscordChannel({"bot_token":"x"})
        assert c.channel_type == 'discord'
    def test_07_wecom(self):
        from agent_platform.integration.channels import WeComChannel
        c = WeComChannel({"webhook_url":"x","corp_id":"y","corp_secret":"z"})
        assert c.channel_type == 'wecom'
