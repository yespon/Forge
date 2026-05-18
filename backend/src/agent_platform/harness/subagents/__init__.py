"""Sub-agent system - delegates tasks to independent LLM agents.

Deprecates old SubAgentExecutor with actual SubagentRuntime.
"""

from agent_platform.harness.subagents.executor import (
    SubagentConfig,
    SubagentResult,
    SubagentRuntime,
    SubagentStatus,
    get_background_result,
    cancel_background_task,
    run_subagent,
)

__all__ = [
    "SubagentConfig",
    "SubagentResult",
    "SubagentRuntime",
    "SubagentStatus",
    "get_background_result",
    "cancel_background_task",
    "run_subagent",
]
