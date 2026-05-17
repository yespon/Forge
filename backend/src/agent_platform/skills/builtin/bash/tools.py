"""Bash execution tools for the bash skill."""

import subprocess
from pathlib import Path
from typing import Annotated

from agent_platform.skills.builtin.file_ops.tools import ToolResult, sanitize_path


def execute_bash(
    command: Annotated[str, "Bash command to execute"],
    working_dir: Annotated[str | None, "Working directory"] = None,
    timeout: Annotated[int, "Timeout in seconds"] = 30,
) -> ToolResult:
    """Execute a bash command.

    Args:
        command: Bash command to execute
        working_dir: Working directory (must be within /workspace)
        timeout: Timeout in seconds

    Returns:
        ToolResult with output or error
    """
    # Sanitize working directory
    if working_dir:
        try:
            working_dir = str(sanitize_path("/workspace", working_dir))
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))
    else:
        working_dir = "/workspace"

    # Block dangerous commands
    dangerous_patterns = [
        "rm -rf /",
        "> /dev/sda",
        "dd if=/dev/zero",
        "mkfs",
        ":(){ :|:& };:",  # Fork bomb
    ]

    for pattern in dangerous_patterns:
        if pattern in command:
            return ToolResult(
                success=False,
                output="",
                error=f"Dangerous command blocked: {pattern}",
            )

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        return ToolResult(
            success=result.returncode == 0,
            output=output,
            error=result.stderr if result.returncode != 0 else None,
        )

    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False,
            output="",
            error=f"Command timed out after {timeout} seconds",
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))
