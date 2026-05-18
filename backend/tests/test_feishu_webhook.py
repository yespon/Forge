"""Feishu webhook route-level behavior tests (unit-level)."""
import sys
from pathlib import Path
import pytest
from fastapi import Request
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent_platform.api.v1.connectors import feishu_webhook, FeishuChallengeResponse


class DummyReceive:
    def __init__(self, body: bytes):
        self.body = body
        self.sent = False
    async def __call__(self):
        if self.sent:
            return {"type": "http.disconnect"}
        self.sent = True
        return {"type": "http.request", "body": self.body, "more_body": False}


def make_request(payload: dict) -> Request:
    import json
    body = json.dumps(payload).encode('utf-8')
    scope = {
        'type': 'http',
        'method': 'POST',
        'path': '/api/v1/connectors/feishu/webhook',
        'headers': [(b'content-type', b'application/json')],
    }
    return Request(scope, receive=DummyReceive(body))


@pytest.mark.asyncio
async def test_feishu_url_verification_challenge():
    req = make_request({"type": "url_verification", "challenge": "abc123"})
    resp = await feishu_webhook(req)
    assert isinstance(resp, FeishuChallengeResponse)
    assert resp.challenge == 'abc123'


@pytest.mark.asyncio
async def test_feishu_event_enqueues_message():
    req = make_request({
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {"chat_id": "c1", "content": "hello"},
            "sender": {"sender_id": {"user_id": "u1"}},
        },
    })
    resp = await feishu_webhook(req)
    assert resp.ok is True
    assert resp.channel == 'feishu'
    assert resp.pending_messages >= 1
