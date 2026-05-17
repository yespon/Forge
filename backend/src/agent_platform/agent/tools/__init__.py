"""Agent tools package.

DEPRECATED: Tools have been moved to the skills package.
Use agent_platform.skills instead for new code.
"""

from agent_platform.agent.tools.hitl import (
    HITLInterrupt,
    HITLToolManager,
    HITLWrappedTool,
    wrap_tool_with_hitl,
)

# Re-export from skills for backward compatibility
from agent_platform.skills import (
    ToolResult,
    execute_bash,
    read_file,
    sanitize_path,
    write_file,
)

__all__ = [
    "execute_bash",
    "HITLInterrupt",
    "HITLToolManager",
    "HITLWrappedTool",
    "read_file",
    "sanitize_path",
    "ToolResult",
    "wrap_tool_with_hitl",
    "write_file",
]
