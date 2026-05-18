"""SummarizationMiddleware - reduces context by summarizing old messages."""

import logging
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, RemoveMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class SummarizationMiddleware(AgentMiddleware):
    """Context reduction middleware with LLM-based summarization."""

    def __init__(
        self,
        model: Optional[Any] = None,
        trigger: tuple = ("tokens", 15564),
        keep: tuple = ("messages", 10),
        trim_tokens_to_summarize: int = 15564,
        summary_prompt: Optional[str] = None,
        skills_container_path: str = "/mnt/skills",
        skill_file_read_tool_names: Optional[list] = None,
        preserve_recent_skill_count: int = 5,
        preserve_recent_skill_tokens: int = 25000,
        preserve_recent_skill_tokens_per_skill: int = 5000,
    ):
        super().__init__()
        self.model = model
        self.trigger = trigger
        self.keep = keep
        self.trim_tokens_to_summarize = trim_tokens_to_summarize
        self.summary_prompt = summary_prompt

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _should_summarize(self, messages: list) -> bool:
        total = sum(self._estimate_tokens(str(getattr(m, "content", ""))) for m in messages)
        t_type, t_val = self.trigger
        if t_type == "tokens" and total >= t_val:
            return True
        if t_type == "messages" and len(messages) >= t_val:
            return True
        return False

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        msgs = state.get("messages", []) if isinstance(state, dict) else getattr(state, "messages", [])
        if not self._should_summarize(msgs):
            return None

        logger.info("Summarization triggered: %d msgs", len(msgs))

        if self.model is not None:
            summary = await self._generate_summary(msgs)
            if summary:
                return self._apply_summary(state, msgs, summary)
        return None

    async def _generate_summary(self, messages: list) -> Optional[str]:
        k_type, k_val = self.keep
        recent = messages[-k_val:] if k_type == "messages" else messages[-10:]

        prompt = self.summary_prompt or (
            "Summarize the conversation history below. Keep all important "
            "information: user goals, decisions, code changes, errors, pending tasks.\n"
        )
        to_summarize = messages[:-len(recent)] if len(messages) > len(recent) else messages[:-5]
        summary_msgs = [SystemMessage(content="You are a conversation summarizer."),
                        HumanMessage(content=prompt)] + list(to_summarize)
        try:
            result = await self.model.ainvoke(summary_msgs)
            summary = result.content if hasattr(result, "content") else str(result)
            logger.info("Summary generated (%d chars)", len(summary))
            return summary
        except Exception as e:
            logger.warning("Summarization failed: %s", e)
            return None

    def _apply_summary(self, state, messages, summary):
        k_type, k_val = self.keep
        preserved = messages[-k_val:] if k_type == "messages" else messages[-10:]
        remove_ids = []
        for m in messages[:-len(preserved)]:
            mid = getattr(m, "id", None)
            if mid:
                remove_ids.append(RemoveMessage(id=mid))
        summary_msg = HumanMessage(
            content=f"[Summary of {len(messages)-len(preserved)} previous messages]:\n{summary}"
        )
        new_msgs = [summary_msg] + list(preserved) + remove_ids
        return {"messages": new_msgs}
