"""TodoMiddleware - task tracking for plan mode."""

import logging
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class TodoMiddleware(AgentMiddleware):
    """Task tracking middleware for complex multi-step tasks.

    Injects todo management system prompt and tool description
    to enable the agent to track and manage task progress.
    """

    def __init__(self, system_prompt: str = "", tool_description: str = ""):
        super().__init__()
        self.system_prompt = system_prompt or (
            "<todo_list_system>\n"
            "You have access to the `write_todos` tool to help manage complex multi-step objectives.\n"
            "- Mark todos as completed IMMEDIATELY after finishing each step.\n"
            "- Keep EXACTLY ONE task as `in_progress` at any time.\n"
            "- Update the todo list in REAL-TIME.\n"
            "- Only use for complex tasks (3+ steps).\n"
            "</todo_list_system>"
        )
        self.tool_description = tool_description or (
            "Create and manage a structured task list for complex work sessions. "
            "Only use for complex tasks requiring 3+ steps."
        )

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        """Inject todo system prompt into context before model call."""
        return {"_todo_prompt": self.system_prompt}
