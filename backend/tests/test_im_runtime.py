"""Focused IM runtime tests for enhanced channel capabilities."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.integration.channels import (
    MessageBus, InboundMessage, OutboundMessage,
    FeishuChannel, SlackChannel, TelegramChannel, DingTalkChannel,
    WeChatChannel, WeComChannel, DiscordChannel,
    ChannelManager, MockChannel, ChannelType,
)


def test_channel_registry_all_7():
    from agent_platform.integration.channels import CHANNEL_REGISTRY
    for k in [ChannelType.FEISHU, ChannelType.SLACK, ChannelType.TELEGRAM, ChannelType.DINGTALK, ChannelType.WECHAT, ChannelType.WECOM, ChannelType.DISCORD]:
        assert k in CHANNEL_REGISTRY


def test_feishu_parse_event():
    msg = FeishuChannel.parse_inbound_event({
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {"chat_id": "c1", "content": "hello"},
            "sender": {"sender_id": {"user_id": "u1"}},
        },
    })
    assert msg and msg.chat_id == 'c1' and msg.user_id == 'u1'


def test_slack_parse_event():
    msg = SlackChannel.parse_inbound_event({"channel": "c2", "user": "u2", "text": "hello"})
    assert msg and msg.chat_id == 'c2' and msg.user_id == 'u2'


def test_telegram_parse_event():
    msg = TelegramChannel.parse_inbound_event({"message": {"chat": {"id": 123}, "from": {"id": 456}, "text": "hi"}})
    assert msg and msg.chat_id == '123' and msg.user_id == '456'


def test_dingtalk_parse_event():
    msg = DingTalkChannel.parse_inbound_event({"conversationId": "cv", "senderId": "u", "text": {"content": "hi"}})
    assert msg and msg.chat_id == 'cv' and msg.user_id == 'u'


def test_message_bus_nowait():
    bus = MessageBus()
    n = bus.publish_inbound_nowait(InboundMessage(channel_type='mock', chat_id='c', user_id='u', text='t'))
    assert n >= 1


@pytest.mark.asyncio
async def test_message_bus_drain():
    bus = MessageBus()
    await bus.publish_inbound(InboundMessage(channel_type='mock', chat_id='c1', user_id='u1', text='a'))
    await bus.publish_inbound(InboundMessage(channel_type='mock', chat_id='c2', user_id='u2', text='b'))
    msgs = await bus.drain_inbound()
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_mock_channel_roundtrip():
    bus = MessageBus()
    ch = MockChannel(bus, {})
    await ch.start()
    await bus.publish_outbound(OutboundMessage(channel_type='mock', chat_id='c', text='reply'))
    assert len(ch.sent_messages) == 1
    assert ch.sent_messages[0].text == 'reply'


@pytest.mark.asyncio
async def test_channel_manager_inject_nowait():
    mgr = ChannelManager()
    n = mgr.inject_inbound_nowait(InboundMessage(channel_type='mock', chat_id='c', user_id='u', text='hello'))
    assert n >= 1


@pytest.mark.asyncio
async def test_channel_manager_handle_webhook_feishu():
    mgr = ChannelManager()
    ok = await mgr.handle_webhook('feishu', {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {"message": {"chat_id": "c1", "content": "hello"}, "sender": {"sender_id": {"user_id": "u1"}}},
    })
    assert ok is True


@pytest.mark.asyncio
async def test_channel_manager_handle_webhook_slack():
    mgr = ChannelManager()
    ok = await mgr.handle_webhook('slack', {"channel": "c1", "user": "u1", "text": "hello"})
    assert ok is True
