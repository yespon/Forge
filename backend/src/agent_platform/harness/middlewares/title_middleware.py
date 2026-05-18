"""TitleMiddleware - auto-generates conversation titles."""

import logging
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class TitleMiddleware(AgentMiddleware):
    """Generates descriptive titles for conversations based on first exchange."""

    def __init__(self, model: Optional[Any] = None, max_words: int = 6, max_chars: int = 60):
        super().__init__()
        self.model = model
        self.max_words = max_words
        self.max_chars = max_chars
        self._generated = False

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        if self._generated:
            return None

        msgs = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        if len(msgs) < 2:
            return None

        # Check if title already exists
        title = state.get("title") if isinstance(state, dict) else getattr(state, "title", None)
        if title:
            self._generated = True
            return None

        if self.model is None:
            return None

        first_exchange = msgs[:2]
        prompt = f"Generate a concise title (max {self.max_words} words, {self.max_chars} chars) for this conversation:\n"
        for m in first_exchange:
            role = getattr(m, "type", "unknown")
            content = getattr(m, "content", "")[:500]
            prompt += f"\n{role}: {content}"

        try:
            result = await self.model.ainvoke([SystemMessage(content="You generate concise conversation titles."),
                                               HumanMessage(content=prompt)])
            title = result.content.strip() if hasattr(result, "content") else str(result).strip()
            title = title[:self.max_chars]
            self._generated = True
            logger.info("Generated title: %s", title)
            return {"title": title}
        except Exception as e:
            logger.warning("Title generation failed: %s", e)
            return None
