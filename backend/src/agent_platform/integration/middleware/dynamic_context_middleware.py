"""DynamicContextMiddleware - injects date/time and memory context."""

import logging
from datetime import datetime
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class DynamicContextMiddleware(AgentMiddleware):
    """Injects dynamic context (date, memory) into the conversation."""

    def __init__(self, agent_name: Optional[str] = None, app_config: Optional[Any] = None):
        super().__init__()
        self.agent_name = agent_name
        self.app_config = app_config

    def _get_date_context(self) -> str:
        now = datetime.now()
        return (
            f"<system_reminder>\n"
            f"  Current date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})\n"
            f"  Current time: {now.strftime('%H:%M')}\n"
            f"</system_reminder>"
        )

    def _get_memory_context(self) -> str:
        try:
            from agent_platform.integration.memory import get_memory_manager
            mm = get_memory_manager()
            return mm.get_memory_context()
        except Exception:
            return ""

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        """Inject context before model processes messages."""
        msgs = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        if not msgs:
            return None

        # Only inject on first turn or when there's new user input
        first_human = None
        for i, msg in enumerate(reversed(msgs)):
            if isinstance(msg, (HumanMessage,)) or getattr(msg, "type", "") == "human":
                first_human = i
                break

        if first_human is None:
            return None

        context_parts = [self._get_date_context()]
        memory_ctx = self._get_memory_context()
        if memory_ctx:
            context_parts.append(memory_ctx)

        context_block = "\n".join(context_parts)

        # Append context to the state for prompt injection
        # The context will be added to the system prompt by the agent builder
        return {"_dynamic_context": context_block}
