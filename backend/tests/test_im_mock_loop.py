"""IM mock loop runtime validation."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.integration.channels import MessageBus, MockChannel, InboundMessage, OutboundMessage, ChannelManager


@pytest.mark.asyncio
async def test_mock_channel_emit_and_send_roundtrip():
    bus = MessageBus()
    mock = MockChannel(bus, {})
    await mock.start()
    await mock.emit("hello", chat_id="c1", user_id="u1")
    pending = await bus.drain_inbound()
    assert len(pending) == 1
    assert pending[0].text == "hello"
    await bus.publish_outbound(OutboundMessage(channel_type="mock", chat_id="c1", text="reply"))
    assert len(mock.sent_messages) == 1
    assert mock.sent_messages[0].text == "reply"


@pytest.mark.asyncio
async def test_manager_handle_webhook_slack_enqueues_message():
    mgr = ChannelManager()
    ok = await mgr.handle_webhook("slack", {"channel": "c1", "user": "u1", "text": "hello"})
    assert ok is True
    items = await mgr.bus.drain_inbound()
    assert len(items) == 1
    assert items[0].chat_id == "c1"


@pytest.mark.asyncio
async def test_manager_inject_nowait():
    mgr = ChannelManager()
    n = mgr.inject_inbound_nowait(InboundMessage(channel_type="mock", chat_id="c2", user_id="u2", text="hello2"))
    assert n >= 1
    items = await mgr.bus.drain_inbound()
    assert len(items) == 1
    assert items[0].text == "hello2"
