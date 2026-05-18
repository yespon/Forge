"""Unified runtime abstraction layer."""

from agent_platform.runtime.context import RuntimeContext, RuntimeRun, RuntimeSnapshot
from agent_platform.runtime.events import RuntimeEvent
from agent_platform.runtime.interrupts import ApprovalInterrupt
from agent_platform.runtime.registry import RuntimeRegistry, get_runtime_registry

__all__ = [
    "RuntimeContext",
    "RuntimeRun",
    "RuntimeSnapshot",
    "RuntimeEvent",
    "ApprovalInterrupt",
    "RuntimeRegistry",
    "get_runtime_registry",
]

# Lazy imports for heavy submodules
def get_checkpointer():
    """Get the configured LangGraph checkpointer."""
    from agent_platform.runtime.checkpointer import get_checkpointer as _get
    return _get()

def get_store():
    """Get the global key-value store."""
    from agent_platform.runtime.store import get_store as _get
    return _get()
