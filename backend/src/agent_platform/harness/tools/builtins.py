"""Built-in tools for Forge × DeerFlow integration.

Provides core tools that are always available to agents:
- ask_clarification: Request user clarification
- task_tool: Delegate tasks to sub-agents (if enabled)
"""

import logging
from typing import Any, Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def ask_clarification_tool(question: str) -> str:
    """Ask the user a clarifying question when you need more information.

    Use this tool when:
    - The user's request is ambiguous
    - You need additional details to complete a task
    - There are multiple possible interpretations
    - You need to confirm a decision before proceeding

    Args:
        question: The clarification question to ask the user

    Returns:
        The user's response
    """
    return f"CLARIFICATION_NEEDED: {question}"


@tool
async def task_tool(
    description: str,
    agent_type: str = "general-purpose",
    priority: int = 1,
    depends_on: Optional[list[str]] = None,
) -> str:
    """Delegate a task to a sub-agent for parallel execution.

    Use this tool to run complex tasks in the background while you continue
    working on other things. The sub-agent will work independently.

    Args:
        description: Detailed description of the task to execute
        agent_type: Type of agent to use (general-purpose, bash, or custom name)
        priority: Task priority (0=urgent, 1=normal, 2=background)
        depends_on: List of task IDs this task depends on

    Returns:
        Task result from the sub-agent
    """
    logger.info(f"Task delegated: type={agent_type}, priority={priority}, desc={description[:100]}")

    # TODO: Integrate with Forge's TaskRuntime for actual sub-agent execution
    # For now, return a stub result
    return (
        f"Task submitted to {agent_type} agent.\n"
        f"Task ID: pending-{id(description)}\n"
        f"Status: queued\n\n"
        f"Note: Sub-agent execution will be available when integrated with "
        f"Forge's TaskRuntime."
    )