"""Agent tools for file operations and command execution."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated


def sanitize_path(base_path: str, user_path: str) -> Path:
    """Sanitize and resolve user-provided path within base directory.

    Args:
        base_path: Base directory path
        user_path: User-provided path (may include ..)

    Returns:
        Resolved path within base directory

    Raises:
        ValueError: If path escapes base directory
    """
    base = Path(base_path).resolve()
    target = (base / user_path).resolve()

    # Ensure target is within base directory
    if not str(target).startswith(str(base)):
        raise ValueError(f"Path '{user_path}' escapes base directory")

    return target


@dataclass
class ToolResult:
    """Tool execution result."""

    success: bool
    output: str
    error: str | None = None


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


def read_file(
    path: Annotated[str, "File path to read (relative to /workspace)"],
    offset: Annotated[int, "Line offset (0-indexed)"] = 0,
    limit: Annotated[int, "Max lines to read"] = 100,
) -> ToolResult:
    """Read file contents.

    Args:
        path: File path (relative to /workspace)
        offset: Starting line number (0-indexed)
        limit: Maximum number of lines to read

    Returns:
        ToolResult with file content
    """
    try:
        file_path = sanitize_path("/workspace", path)

        if not file_path.exists():
            return ToolResult(
                success=False,
                output="",
                error=f"File not found: {path}",
            )

        if not file_path.is_file():
            return ToolResult(
                success=False,
                output="",
                error=f"Path is not a file: {path}",
            )

        # Read file
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Apply offset and limit
        lines = lines[offset : offset + limit]

        # Add line numbers
        numbered_lines = []
        for i, line in enumerate(lines, start=offset + 1):
            numbered_lines.append(f"{i:4d} | {line.rstrip()}")

        content = "\n".join(numbered_lines)

        if offset + limit < len(lines):
            content += f"\n\n... ({len(lines) - offset - limit} more lines)"

        return ToolResult(success=True, output=content)

    except ValueError as e:
        return ToolResult(success=False, output="", error=str(e))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


def write_file(
    path: Annotated[str, "File path to write (relative to /workspace)"],
    content: Annotated[str, "Content to write"],
    append: Annotated[bool, "Append to file instead of overwrite"] = False,
) -> ToolResult:
    """Write content to file.

    Args:
        path: File path (relative to /workspace)
        content: Content to write
        append: Whether to append or overwrite

    Returns:
        ToolResult with status
    """
    try:
        file_path = sanitize_path("/workspace", path)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        mode = "a" if append else "w"
        with open(file_path, mode, encoding="utf-8") as f:
            f.write(content)

        action = "appended to" if append else "wrote"
        return ToolResult(
            success=True,
            output=f"Successfully {action} {path}",
        )

    except ValueError as e:
        return ToolResult(success=False, output="", error=str(e))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))
