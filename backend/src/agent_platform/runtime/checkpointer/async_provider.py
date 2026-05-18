"""Async checkpointer provider — entry point for langgraph.json.

This module provides the canonical `make_checkpointer` factory that langgraph.json
references for state persistence. It returns an async-compatible checkpointer.
"""

from agent_platform.runtime.checkpointer.provider import make_checkpointer

__all__ = ["make_checkpointer"]
