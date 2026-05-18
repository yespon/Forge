"""Forge Agent Harness — core agent engine library.

This package mirrors DeerFlow's `packages/harness/deerflow/` structure,
providing the agent runtime components that Forge wraps with enterprise features.

Subpackages:
    agents/      — Agent factory & type definitions
    middlewares/ — 14 middleware chain components
    memory/      — Memory extraction & storage
    mcp/         — MCP protocol integration (stdio/SSE/OAuth)
    models/      — LLM model resolution & provider config
    skills/      — Skill discovery & loading
    subagents/   — Sub-agent delegation & execution
    tools/       — Built-in tool implementations
    tracing/     — Observability (LangFuse/LangSmith)
"""
from .config import ForgeDeerFlowConfig, get_integration_config

__all__ = ["ForgeDeerFlowConfig", "get_integration_config"]
