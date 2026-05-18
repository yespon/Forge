"""Bash execution tool adapted from DeerFlow for Forge.

Provides sandbox-aware shell command execution with timeout and security.
"""

import asyncio
import logging
import shlex
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
async def bash_tool(command: str, timeout: Optional[int] = 120, description: Optional[str] = None) -> str:
    """Execute a bash command in the sandbox environment.

    Args:
        command: The bash command to execute
        timeout: Timeout: Maximum execution time in seconds (default: 120, max: 600)
        description: Optional description of what this command does

    Returns:
        Command output (stdout + stderr)
    """
    # Security: validate timeout
    actual_timeout = min(timeout or 120, 600)
    if actual_timeout < 1:
        actual_timeout = 1

    # Security: basic command validation
    if not command or not command.strip():
        return "Error: Empty command"

    # Block dangerous commands
    dangerous_patterns = ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "dd if=/dev/zero of=/dev/"]
    dangerous_prefixes = ["mkfs", "sudo", "mount", "umount", "fdisk", "iptables", "kill -9"]
    pipe_patterns = ["| sh", "| bash", "|sh", "|bash"]
    for pattern in dangerous_patterns:
        if pattern in command:
            return f"Error: Command blocked for security reasons: potentially dangerous pattern detected"
    cmd_lower = command.strip().lower()
    for prefix in dangerous_prefixes:
        if cmd_lower.startswith(prefix):
            return f"Error: Command blocked for security reasons: potentially dangerous pattern detected"
    for pattern in pipe_patterns:
        if pattern in command:
            return f"Error: Command blocked for security reasons: potentially dangerous pattern detected"

    logger.info(f"Executing bash command (timeout={actual_timeout}s): {command[:200]}")

    try:
        # Use asyncio subprocess with timeout
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=actual_timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return f"Error: Command timed out after {actual_timeout} seconds"

        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        # Build result
        result_parts = []
        if stdout_str:
            # Truncatexit: stdout_str[-10000:] if len(stdout_str) > 10000 else stdout_str
            result_parts.append(stdout_str[-10000:] if len(stdout_str) > 10000 else stdout_str)

        if stderr_str:
            truncated_stderr = stderr_str[-5000:] if len(stderr_str) > 5000 else stderr_str
            result_parts.append(f"STDERR:\n{truncated_stderr}")
            
        if process.returncode and process.returncode != 0:
            result_parts.append(f"\n(Exit code: {process.returncode})")

        result = "\n".join(result_parts) if result_parts else "(No output)"
        
        if stdout_str and len(stdout_str) > 10000:
            result = f"[Output truncated to 10000 chars, original length: {len(stdout_str)}]\n{result}"

        return result

    except Exception as e:
        logger.exception(f"Bash command failed: {e}")
        return f"Error executing command: {e}"