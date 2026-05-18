"""
Forge × DeerFlow Integration Layer

This package adapts DeerFlow's Super Agent Harness capabilities into
Forge's Enterprise Multi-User Agent Runtime Platform.

Key Integrations:
- Agent Factory: DeerFlow's create_deerflow_agent + Forge's HITL/Audit
- Middleware System: 14 DeerFlow middlewares with Forge platform extensions
- Multi-Provider Models: DeerFlow's model factory with Forge RBAC
- Sub-Agent Executor: DeerFlow's subagent system with Forge task tracking
- Skills System: SKILL.md: DeerFlow's SKILL.md skill system
- Memory/Summarization: DeerFlow's memory queue and summarization
- IM Channels: DeerFlow's multi-IM provider system
- MCP Integration: DeerFlow's MCP client management
- Tool Search: DeerFlow's deferred tool loading
- Loop Detection: DeerFlow's loop detection middleware

Architecture:
```
Forge Platform Layer (Multi-Tenant / HITL / Audit / Task Queue)
    ↕ Integration Layer
DeerFlow Harness Layer (Agent / Middleware / Skills / Memory / MCP)
    ↕ LangGraph Runtime
```

Each integrated component maintains Forge's enterprise security model
while adding DeerFlow's rich agent capabilities.
"""

from agent_platform.harness.config import ForgeDeerFlowConfig, get_integration_config
from agent_platform.harness.agents.factory import (
    create_forge_agent,
    get_available_models,
    resolve_model,
)

__all__ = [
    "ForgeDeerFlowConfig",
    "create_forge_agent",
    "get_available_models",
    "resolve_model",
    "get_integration_config",
]