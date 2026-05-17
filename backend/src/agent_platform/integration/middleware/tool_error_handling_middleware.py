"""ToolErrorHandlingMiddleware - converts tool exceptions to ToolMessages."""

import logging
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class ToolErrorHandlingMiddleware(AgentMiddleware):
    """Catches tool exceptions and converts them to proper ToolMessage responses."""

    @override
    async def awrap_tool_call(self, request, handler):
        try:
            result = await handler(request)
            return result
        except Exception as e:
            logger.warning(f"Tool {request.tool_call.get('name', '?')} failed: {e}")
            return ToolMessage(
                content=f"Tool execution error: {e}",
                tool_call_id=request.tool_call["id"],
                status="error",
            )