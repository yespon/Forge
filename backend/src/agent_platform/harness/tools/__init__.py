"""Tools package for Forge × DeerFlow integration.

Provides tool loading, registration, and the core sandbox/web tools
adapted from DeerFlow's tool system.
"""

import logging
from typing import Any, Optional

from langchain_core.tools import BaseTool, tool

from agent_platform.harness.config import ForgeDeerFlowConfig

logger = logging.getLogger(__name__)


def get_available_tools(
    model_name: Optional[str] = None,
    subagent_enabled: bool = False,
    app_config: Optional[ForgeDeerFlowConfig] = None,
    session: Optional[Any] = None,
    user: Optional[Any] = None,
    db: Optional[Any] = None,
) -> list[BaseTool]:
    """Get all available tools for an agent session.

    Loads tools from:
    1. Sandbox file operations (read_file, write_file, ls)
    2. Web tools (web_search, web_fetch)
    3. Built-in tools (ask_clarification)
    4. Subagent tools (if subagent_enabled)
    5. MCP tools (if configured)

    Args:
        model_name: Current model name
        subagent_enabled: Whether to include subagent delegation tools
        app_config: Integration configuration
        session: Forge Session for skill-based tool loading
        user: Forge User for permission checks
        db: Database session

    Returns:
        List of structured tools
    """
    tools: list[BaseTool] = []

    # 1. File operations
    from agent_platform.harness.tools.file_ops import ls_tool, read_file_tool, write_file_tool
    tools.extend([ls_tool, read_file_tool, write_file_tool])

    # 2. Web tools
    try:
        from agent_platform.harness.tools.web_search import web_search_tool
        tools.append(web_search_tool)
    except Exception as e:
        logger.warning(f"Failed to load web_search tool: {e}")

    try:
        from agent_platform.harness.tools.web_fetch import web_fetch_tool
        tools.append(web_fetch_tool)
    except Exception as e:
        logger.warning(f"Failed to load web_fetch tool: {e}")

    # 3. Built-in tools
    from agent_platform.harness.tools.builtins import ask_clarification_tool
    tools.append(ask_clarification_tool)

    # 4. Subagent tool (if enabled)
    if subagent_enabled:
        try:
            from agent_platform.harness.tools.builtins import task_tool
            tools.append(task_tool)
        except Exception as e:
            logger.warning(f"Failed to load task_tool: {e}")

    # 5. Bash (if sandbox allows)
    try:
        from agent_platform.harness.tools.bash import bash_tool
        tools.append(bash_tool)
    except Exception as e:
        logger.warning(f"Failed to load bash tool: {e}")

    # 6. MCP tools (if configured)
    # TODO: Load MCP tools from extensions_config

    logger.info(f"Loaded {len(tools)} tools for agent session")
    return tools