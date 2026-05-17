"""ClarificationMiddleware - handles agent clarification requests."""

import json
import logging
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class ClarificationMiddleware(AgentMiddleware):
    """Handles clarification requests from the agent.

    When the agent calls ask_clarification, this middleware:
    1. Intercepts the tool call
    2. Stores the clarification question in state
    3. Returns a signal that execution should pause
    """

    _CLARIFICATION_TOOL = "ask_clarification"

    @override
    async def awrap_tool_call(self, request, handler):
        tool_name = request.tool_call.get("name", "")
        if tool_name != self._CLARIFICATION_TOOL:
            return await handler(request)

        args = request.tool_call.get("args", {})
        question = args.get("question", "No question provided")

        logger.info(f"Agent requests clarification: {question[:100]}")

        # Store clarification in state for the UI to display
        state = request.state
        if isinstance(state, dict):
            state["_clarification"] = {
                "question": question,
                "tool_call_id": request.tool_call["id"],
                "status": "pending",
            }

        # Return a special ToolMessage that pauses execution
        return ToolMessage(
            content=f"CLARIFICATION_REQUIRED: {question}",
            tool_call_id=request.tool_call["id"],
            status="requires_input",
            additional_kwargs={"clarification": True, "question": question},
        )