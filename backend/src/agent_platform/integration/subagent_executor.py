"""Sub-agent LLM execution engine for Forge.

Creates and runs independent LangChain agents as sub-agents,
with support for timeouts, cancellation, and dependency resolution.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from agent_platform.integration.config import get_integration_config
from agent_platform.integration.models import create_chat_model
from agent_platform.integration.tools import get_available_tools

logger = logging.getLogger(__name__)


class SubagentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class SubagentResult:
    task_id: str = ""
    status: SubagentStatus = SubagentStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    ai_messages: list[dict] = field(default_factory=list)
    agent_type: str = "general-purpose"


@dataclass
class SubagentConfig:
    """Configuration for a single sub-agent type."""
    name: str
    description: str = ""
    system_prompt: str = ""
    skills: Optional[list[str]] = None
    tools: Optional[list[str]] = None
    model: Optional[str] = None
    max_turns: int = 80
    timeout_seconds: int = 600

    @staticmethod
    def default_general_purpose() -> "SubagentConfig":
        return SubagentConfig(
            name="general-purpose",
            description="General-purpose sub-agent for complex multi-step tasks",
            system_prompt="You are a helpful sub-agent assistant. Complete the assigned task thoroughly.",
            max_turns=120,
            timeout_seconds=900,
        )

    @staticmethod
    def default_bash() -> "SubagentConfig":
        return SubagentConfig(
            name="bash",
            description="Bash command specialist",
            system_prompt="You are a bash specialist sub-agent. Execute shell commands efficiently.",
            tools=["bash", "read_file", "write_file", "ls"],
            max_turns=80,
            timeout_seconds=300,
        )


class SubagentRuntime:
    """Runs independent LLM agents as sub-agents.

    Each sub-agent gets its own LangChain agent instance with:
    - Independent model (inherits from parent or overrides)
    - Filtered tool set based on agent type
    - Custom system prompt
    - Independent middleware chain (minimal)
    - Timeout and cancellation support
    """

    def __init__(
        self,
        config: Optional[SubagentConfig] = None,
        parent_model_name: Optional[str] = None,
        parent_tools: Optional[list[BaseTool]] = None,
    ):
        self.config = config or SubagentConfig.default_general_purpose()
        self.parent_model_name = parent_model_name
        self.parent_tools = parent_tools

    async def execute(self, task: str, cancel_event: Optional[asyncio.Event] = None) -> SubagentResult:
        """Execute a task with the sub-agent.

        Args:
            task: The task description
            cancel_event: Optional event to signal cancellation

        Returns:
            SubagentResult with execution status and output
        """
        task_id = str(uuid.uuid4())[:8]
        result = SubagentResult(
            task_id=task_id,
            status=SubagentStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            agent_type=self.config.name,
        )

        try:
            cfg = get_integration_config()

            # Resolve model
            model_name = self.config.model or self.parent_model_name or cfg.default_model_name
            model_config = cfg.get_model_config(model_name)
            if not model_config and cfg.models:
                model_config = cfg.models[0]

            if not model_config:
                raise ValueError(f"No model configured for sub-agent '{self.config.name}'")

            model = create_chat_model(model_config=model_config, thinking_enabled=False)

            # Resolve tools - filter by allowed tool names
            tools = []
            all_tools = self.parent_tools or get_available_tools(app_config=cfg)
            if self.config.tools is not None:
                allowed = set(self.config.tools)
                tools = [t for t in all_tools if t.name in allowed]
            else:
                tools = list(all_tools)

            # Create the sub-agent
            agent = create_agent(
                model=model,
                tools=tools if tools else None,
                system_prompt=self.config.system_prompt or (
                    "You are a helpful sub-agent. Complete the assigned task efficiently."
                ),
            )

            # Build state
            state = {"messages": [HumanMessage(content=task)]}

            # Execute with timeout
            timeout = self.config.timeout_seconds
            task_obj = asyncio.create_task(self._run_agent(agent, state, result))
            try:
                await asyncio.wait_for(task_obj, timeout=timeout)
            except asyncio.TimeoutError:
                task_obj.cancel()
                result.status = SubagentStatus.TIMED_OUT
                result.error = f"Sub-agent timed out after {timeout}s"
                result.completed_at = datetime.now(timezone.utc).isoformat()
                logger.warning("Sub-agent %s timed out after %ds", task_id, timeout)

        except asyncio.CancelledError:
            result.status = SubagentStatus.CANCELLED
            result.error = "Sub-agent was cancelled"
            result.completed_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            result.status = SubagentStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now(timezone.utc).isoformat()
            logger.exception("Sub-agent %s failed: %s", task_id, e)

        return result

    async def _run_agent(self, agent, state: dict, result: SubagentResult) -> None:
        """Run the agent and collect results."""
        last_content = ""

        async for chunk in agent.astream(state, stream_mode="updates"):
            if isinstance(chunk, dict):
                for node, data in chunk.items():
                    if isinstance(data, dict):
                        msgs = data.get("messages", [])
                        for msg in msgs:
                            if isinstance(msg, AIMessage) and msg.content:
                                last_content = msg.content
                                result.ai_messages.append({"role": "assistant", "content": msg.content})
                            elif isinstance(msg, (HumanMessage,)):
                                pass  # Skip human messages in output

        result.result = last_content
        result.status = SubagentStatus.COMPLETED
        result.completed_at = datetime.now(timezone.utc).isoformat()


# ============================================================================
# Global registry for background tasks
# ============================================================================

_background_tasks: dict[str, tuple[SubagentRuntime, SubagentResult]] = {}


async def run_subagent(
    task: str,
    agent_type: str = "general-purpose",
    parent_model_name: Optional[str] = None,
    parent_tools: Optional[list[BaseTool]] = None,
    timeout: int = 600,
    background: bool = False,
) -> SubagentResult:
    """Run a sub-agent task.

    Args:
        task: Task description
        agent_type: Sub-agent type ('general-purpose', 'bash', or custom)
        parent_model_name: Model name to inherit from parent
        parent_tools: Tools to make available to the sub-agent
        timeout: Execution timeout in seconds
        background: If True, run in background and return immediately

    Returns:
        SubagentResult
    """
    # Resolve config
    if agent_type == "bash":
        config = SubagentConfig.default_bash()
    elif agent_type == "general-purpose":
        config = SubagentConfig.default_general_purpose()
    else:
        config = SubagentConfig(
            name=agent_type,
            system_prompt=f"You are a {agent_type} specialist sub-agent.",
            timeout_seconds=timeout,
        )

    runtime = SubagentRuntime(
        config=config,
        parent_model_name=parent_model_name,
        parent_tools=parent_tools,
    )

    if background:
        task_id = str(uuid.uuid4())[:8]
        result = SubagentResult(
            task_id=task_id,
            status=SubagentStatus.PENDING,
            agent_type=agent_type,
        )
        _background_tasks[task_id] = (runtime, result)

        async def _run_and_store():
            res = await runtime.execute(task)
            _background_tasks[task_id] = (runtime, res)

        asyncio.create_task(_run_and_store())
        return result
    else:
        return await runtime.execute(task)


async def get_background_result(task_id: str) -> Optional[SubagentResult]:
    """Get the result of a background sub-agent task."""
    entry = _background_tasks.get(task_id)
    if entry:
        return entry[1]
    return None


async def cancel_background_task(task_id: str) -> bool:
    """Cancel a background sub-agent task."""
    if task_id in _background_tasks:
        _, result = _background_tasks[task_id]
        if result.status in (SubagentStatus.PENDING, SubagentStatus.RUNNING):
            result.status = SubagentStatus.CANCELLED
            result.error = "Cancelled by user"
            result.completed_at = datetime.now(timezone.utc).isoformat()
            return True
    return False
