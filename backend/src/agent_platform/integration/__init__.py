"""Forge × DeerFlow Integration Layer.

DEPRECATED: This package is a backward-compatibility shim.
All modules have been relocated to agent_platform.harness.* and agent_platform.channels.

Import mapping:
    integration.config          → harness.config
    integration.agent_factory   → harness.agents.factory
    integration.types           → harness.agents.types
    integration.models          → harness.models
    integration.memory          → harness.memory
    integration.mcp             → harness.mcp
    integration.mcp_oauth       → harness.mcp.oauth
    integration.mcp_transport   → harness.mcp.transport
    integration.skills          → harness.skills
    integration.subagents       → harness.subagents
    integration.subagent_executor → harness.subagents.executor
    integration.channels        → channels
    integration.middleware.*    → harness.middlewares.*
    integration.middleware_module → harness.middlewares.registry
    integration.tools.*         → harness.tools.*
    integration.acp_agent       → harness.agents.acp
"""
# Re-export for backward compatibility
from agent_platform.harness.config import ForgeDeerFlowConfig, get_integration_config
from agent_platform.harness.agents.factory import create_forge_agent, get_available_models, resolve_model
from agent_platform.harness.memory import get_memory_manager
from agent_platform.harness.mcp import get_mcp_manager
from agent_platform.harness.skills import get_skill_manager

__all__ = [
    "ForgeDeerFlowConfig", "create_forge_agent", "get_available_models", "resolve_model",
    "get_integration_config", "get_memory_manager", "get_mcp_manager", "get_skill_manager",
]
