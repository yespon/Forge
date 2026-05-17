"""MemoryMiddleware - conversation memory with fact injection and extraction."""

import logging
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class MemoryMiddleware(AgentMiddleware):
    """Conversation memory middleware.

    Before model: injects relevant memory facts into context.
    After model: extracts new facts from conversation and stores them.
    """

    def __init__(self, agent_name: Optional[str] = None, memory_config: Optional[Any] = None):
        super().__init__()
        self.agent_name = agent_name
        self.memory_config = memory_config
        self._initialized = False
        self._mm = None

    def _ensure_memory(self):
        if not self._initialized:
            from agent_platform.integration.memory import get_memory_manager
            self._mm = get_memory_manager()
            self._initialized = True

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        """Inject memory facts before model processes messages."""
        self._ensure_memory()
        if not self._mm or not self._mm.injection_enabled:
            return None

        msgs = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        last_content = ""
        for msg in reversed(msgs):
            content = getattr(msg, "content", "")
            if content:
                last_content = content[:500]
                break

        memory_ctx = self._mm.get_memory_context(query=last_content)
        if memory_ctx:
            return {"_memory_context": memory_ctx}
        return None

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        """Extract memory facts after model response."""
        self._ensure_memory()
        if not self._mm:
            return None

        msgs = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        count = self.extract_and_store_facts(msgs)
        if count > 0:
            logger.info("Stored %d new memory facts", count)
        return None

    def extract_and_store_facts(self, messages: list) -> int:
        """Extract potential memory facts from recent user messages."""
        self._ensure_memory()
        if not self._mm:
            return 0

        count = 0
        for msg in messages[-6:]:
            content = getattr(msg, "content", "")
            if not isinstance(content, str) or len(content) < 30:
                continue

            role = getattr(msg, "type", "")
            if role == "human":
                self._mm.store_fact(content=content[:300], category="user_context", confidence=0.4)
                count += 1
        return count
