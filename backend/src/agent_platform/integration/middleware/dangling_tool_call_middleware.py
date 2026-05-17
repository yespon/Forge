"""DanglingToolCallMiddleware - patches dangling tool calls in message history.

A dangling tool call occurs when an AIMessage contains tool_calls but there are
no corresponding ToolMessages in the history (e.g., due to user interruption or
request cancellation). This middleware detects and fixes such gaps by inserting
synthetic ToolMessages with an error indicator.
"""

import json
import logging
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class DanglingToolCallMiddleware(AgentMiddleware):
    """Inserts placeholder ToolMessages for dangling tool calls before model invocation."""

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
        """Intercept model call to patch dangling tool calls in message history."""
        messages = request.messages
        patched = self._patch_dangling_tool_calls(messages)

        if patched:
            logger.info(f"Patched {patched} dangling tool call(s) in message history")
            request = request.override(messages=self._get_patched_messages(request))

        return await handler(request)

    def _find_dangling_tool_calls(self, messages: list) -> list[tuple[int, AIMessage, list[dict]]]:
        """Find AIMessages with tool_calls missing corresponding ToolMessages."""
        tool_call_ids = set()
        for msg in messages:
            if isinstance(msg, ToolMessage):
                tool_call_ids.add(msg.tool_call_id)

        dangling = []
        for i, msg in enumerate(messages):
            if not isinstance(msg, AIMessage):
                continue
            tool_calls = getattr(msg, "tool_calls", []) or []
            for tc in tool_calls:
                tc_id = tc.get("id") or tc.get("tool_call_id")
                if tc_id and tc_id not in tool_call_ids:
                    dangling.append((i, tc_id, tc.get("name", "unknown")))

        return dangling

    def _patch_dangling_tool_calls(self, messages: list) -> int:
        """Patch dangling tool calls by inserting synthetic error ToolMessages."""
        patches = self._find_dangling_tool_calls(messages)
        if not patches:
            return 0

        inserted = 0
        for idx, tc_id, tc_name in patches:
            error_msg = ToolMessage(
                content=f"Error: Tool call '{tc_name}' ({tc_id}) was interrupted and did not execute. "
                        f"The previous response was incomplete. Please retry or provide an alternative approach.",
                tool_call_id=tc_id,
                status="error",
            )
            messages.insert(idx + 1 + inserted, error_msg)
            inserted += 1

        return inserted