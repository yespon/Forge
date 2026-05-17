"""File operations tools adapted from DeerFlow for Forge.

Provides sandbox-aware file read, write, and listing operations.
"""

import os
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool


def _get_thread_workspace(thread_id: Optional[str] = None) -> Path:
    """Get the thread workspace directory."""
    base = Path(os.environ.get("FORGE_SANDBOX_PATH", ".deer-flow/threads"))
    if thread_id:
        return base / thread_id / "user-data" / "workspace"
    return base / "default" / "user-data" / "workspace"


@tool
async def read_file_tool(path: str, thread_id: Optional[str] = None) -> str:
    """Read the contents of a file.

    Args:
        path: Path to the file to read (relative to workspace or absolute)
        thread_id: Optional thread ID for scoping

    Returns:
        File contents as a string
    """
    workspace = _get_thread_workspace(thread_id)

    # Handle relative vs absolute paths
    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = workspace / filepath

    # Security: prevent path traversal
    try:
        filepath = filepath.resolve()
        workspace = workspace.resolve()
        if not str(filepath).startswith(str(workspace)):
            return f"Error: Access denied - path traversal detected: {path}"
    except (ValueError, OSError):
        return f"Error: Invalid path: {path}"

    if not filepath.exists():
        return f"Error: File not found: {path}"
    if not filepath.is_file():
        return f"Error: Not a file: {path}"

    try:
        content = filepath.read_text(encoding="utf-8")
        return content
    except UnicodeDecodeError:
        return f"Error: Cannot read binary file: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


@tool
async def write_file_tool(path: str, content: str, thread_id: Optional[str] = None) -> str:
    """Write content to a file.

    Creates parent directories if they don't exist.

    Args:
        path: Path to the file to write (relative to workspace or absolute)
        content: Content to write to the file
        thread_id: Optional thread ID for scoping

    Returns:
        Confirmation message
    """
    workspace = _get_thread_workspace(thread_id)

    filepath = Path(path)
    if not filepath.is_absolute():
        filepath = workspace / filepath

    try:
        filepath = filepath.resolve()
        workspace = workspace.resolve()
        if not str(filepath).startswith(str(workspace)):
            return f"Error: Access denied - path traversal detected: {path}"
    except (ValueError, OSError):
        return f"Error: Invalid path: {path}"

    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
async def ls_tool(path: str = ".", thread_id: Optional[str] = None) -> str:
    """List directory contents.

    Args:
        path: Directory path to list (default: current workspace)
        thread_id: Optional thread ID for scoping

    Returns:
        Directory listing as formatted string
    """
    workspace = _get_thread_workspace(thread_id)

    dirpath = Path(path)
    if not dirpath.is_absolute():
        dirpath = workspace / dirpath

    try:
        dirpath = dirpath.resolve()
    except (ValueError, OSError):
        return f"Error: Invalid path: {path}"

    if not dirpath.exists():
        return f"Error: Directory not found: {path}"
    if not dirpath.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = []
        for entry in sorted(dirpath.iterdir()):
            suffix = "/" if entry.is_dir() else ""
            size = entry.stat().st_size if entry.is_file() else 0
            entries.append(f"{entry.name}{suffix}  ({size} bytes)")

        if not entries:
            return f"Directory '{path}' is empty"

        return f"Contents of '{path}':\n" + "\n".join(entries)
    except PermissionError:
        return f"Error: Permission denied: {path}"
    except Exception as e:
        return f"Error listing directory: {e}"