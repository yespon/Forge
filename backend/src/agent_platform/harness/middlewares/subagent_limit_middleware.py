"""SubagentLimitMiddleware - controls concurrent sub-agent execution."""

import logging
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelResponse
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class SubagentLimitMiddleware(AgentMiddleware):
    """Limits concurrent sub-agent invocations to prevent resource exhaustion."""

    def __init__(self, max_concurrent: int = 3):
        super().__init__()
        self.max_concurrent = max_concurrent

    @override
    async def awrap_model_call(self, request, handler):
        """Intercept model output to limit parallel task tool calls."""
        result = await handler(request)
        response = result if hasattr(result, "result") else result
        ai_msgs = response.result if hasattr(response, "result") else []

        new_msgs = []
        for msg in ai_msgs:
            if not isinstance(msg, AIMessage):
                new_msgs.append(msg)
                continue

            tool_calls = getattr(msg, "tool_calls", []) or []
            task_calls = [tc for tc in tool_calls if tc.get("name") == "task_tool"]

            if len(task_calls) > self.max_concurrent:
                extra = task_calls[self.max_concurrent:]
                kept = [tc for tc in tool_calls if tc not in extra]
                names = [tc.get("args", {}).get("description", "?")[:50] for tc in extra]
                warning = f"\n[Sub-agent limit: {self.max_concurrent} concurrent max. {len(extra)} task(s) deferred: {', '.join(names)}]"
                content = (msg.content or "") + warning
                new_msgs.append(AIMessage(content=content, tool_calls=kept,
                                          id=getattr(msg, "id", None)))
                logger.warning("Deferred %d sub-agent tasks (limit %d)", len(extra), self.max_concurrent)
            else:
                new_msgs.append(msg)

        return ModelResponse(result=new_msgs, structured_response=getattr(response, "structured_response", None))
