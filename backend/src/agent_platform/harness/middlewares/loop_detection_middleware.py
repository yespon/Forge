"""LoopDetectionMiddleware - detects and breaks repetitive tool call loops."""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class LoopDetectionMiddleware(AgentMiddleware):
    """Detects repeated identical tool calls and interrupts loops."""

    def __init__(
        self,
        warn_threshold: int = 3,
        hard_limit: int = 5,
        window_size: int = 20,
        tool_freq_warn: int = 30,
        tool_freq_hard_limit: int = 50,
        tool_freq_overrides: Optional[dict] = None,
    ):
        super().__init__()
        self.warn_threshold = warn_threshold
        self.hard_limit = hard_limit
        self.window_size = window_size
        self.tool_freq_warn = tool_freq_warn
        self.tool_freq_hard_limit = tool_freq_hard_limit
        self.tool_freq_overrides = tool_freq_overrides or {}
        self._history: list[dict] = []
        self._warned_hashes: set[str] = set()

    def _hash_call(self, name: str, args: dict) -> str:
        normalized = json.dumps({"name": name, "args": args}, sort_keys=True, default=str)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _check_loop(self, tool_name: str, tool_input: dict) -> Optional[dict]:
        h = self._hash_call(tool_name, tool_input)
        self._history.append({"hash": h, "tool_name": tool_name, "ts": time.time()})
        if len(self._history) > self.window_size:
            self._history = self._history[-self.window_size:]

        recent = [c for c in self._history if c["hash"] == h]
        count = len(recent)

        if count >= self.hard_limit:
            self._warned_hashes.add(h)
            return {"blocked": True, "count": count, "hash": h,
                    "message": f"Loop detected: {tool_name} called {count}x with identical args"}

        if count >= self.warn_threshold and h not in self._warned_hashes:
            self._warned_hashes.add(h)
            return {"warning": True, "count": count, "hash": h,
                    "message": f"Repeated: {tool_name} called {count}x with same args"}

        # Check tool frequency
        tool_count = sum(1 for c in self._history if c["tool_name"] == tool_name)
        limit = self.tool_freq_overrides.get(tool_name, {}).get("hard_limit", self.tool_freq_hard_limit)
        if tool_count >= limit:
            return {"blocked": True, "count": tool_count, "message":
                    f"Tool {tool_name} used {tool_count}x in last {self.window_size} calls (limit {limit})"}

        return None

    @override
    async def awrap_model_call(self, request, handler):
        result = await handler(request)
        response = result if isinstance(result, ModelResponse) else result
        ai_msgs = response.result if hasattr(response, "result") else []
        new_msgs = []

        for msg in ai_msgs:
            if not isinstance(msg, AIMessage):
                new_msgs.append(msg)
                continue

            tool_calls = getattr(msg, "tool_calls", []) or []
            blocked_calls = []
            safe_calls = []

            for tc in tool_calls:
                loop = self._check_loop(tc.get("name", "?"), tc.get("args", {}))
                if loop and loop.get("blocked"):
                    blocked_calls.append(tc)
                    logger.warning("Blocked loop: %s - %s", tc.get("name"), loop.get("message"))
                else:
                    safe_calls.append(tc)

            if blocked_calls:
                content = msg.content or ""
                for bc in blocked_calls:
                    content += f"\n[Tool call BLOCKED: {bc.get('name')} - loop detection triggered]"
                new_msg = AIMessage(content=content, tool_calls=safe_calls,
                                    id=getattr(msg, "id", None))
                new_msgs.append(new_msg)
            else:
                new_msgs.append(msg)

        return ModelResponse(result=new_msgs, structured_response=getattr(response, "structured_response", None))

    @classmethod
    def from_config(cls, config: Any) -> "LoopDetectionMiddleware":
        return cls(
            warn_threshold=config.warn_threshold,
            hard_limit=config.hard_limit,
            window_size=config.window_size,
            tool_freq_warn=config.tool_freq_warn,
            tool_freq_hard_limit=config.tool_freq_hard_limit,
            tool_freq_overrides=getattr(config, "tool_freq_overrides", {}),
        )
