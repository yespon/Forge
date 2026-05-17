"""Agent factory integrating DeerFlow's agent harness with Forge's platform.

This module adapts DeerFlow's create_deerflow_agent + make_lead_agent into
Forge's enterprise context, adding:
- Multi-tenant RBAC checks
- HITL approval via Forge's ToolGateway
- Audit logging integration
- Session-based tool loading
"""

import logging
from typing import Any, Optional

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware

from agent_platform.integration.config import ForgeDeerFlowConfig, get_integration_config
from agent_platform.integration.middleware import build_forge_middleware_chain
from agent_platform.integration.models import create_chat_model
from agent_platform.integration.tools import get_available_tools
from agent_platform.integration.types import ModelConfig

logger = logging.getLogger(__name__)


class ForgeAgentState:
    """State schema for Forge agents, extending ThreadState with Forge-specific fields."""

    messages: list
    sandbox: dict
    thread_data: dict
    title: Optional[str] = None

    # Forge enterprise extensions
    org_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    hitl_enabled: bool = False
    audit_enabled: bool = True


def create_forge_agent(
    model_name: str,
    system_prompt: Optional[str] = None,
    tools: Optional[list] = None,
    *,
    thinking_enabled: bool = True,
    plan_mode: bool = False,
    subagent_enabled: bool = False,
    hitl_enabled: bool = False,
    audit_enabled: bool = True,
    session=None,
    user=None,
    db=None,
    app_config: Optional[ForgeDeerFlowConfig] = None,
    **kwargs,
) -> Any:
    """Create a Forge agent with full DeerFlow capabilities.

    Integrates DeerFlow's agent harness with Forge's enterprise features:
    - Multi-provider model selection (from config.yaml)
    - Full middleware chain (summarization, memory, titles, etc.)
    - HITL approval via ToolGateway integration
    - Audit logging
    - Skill-based tool loading

    Args:
        model_name: Name of the model to use (from integration config)
        system_prompt: Optional custom system prompt
        tools: Optional custom tools list (overrides automatic loading)
        thinking_enabled: Enable thinking/reasoning mode
        plan_mode: Enable task todo list tracking
        subagent_enabled: Enable sub-agent delegation
        hitl_enabled: Enable HITL approval checks
        audit_enabled: Enable audit logging
        session: Forge Session for tool loading
        user: Forge User for permission checks
        db: Database session
        app_config: Integration configuration

    Returns:
        Compiled LangGraph agent
    """
    cfg = app_config or get_integration_config()

    # Resolve model
    model_config = cfg.get_model_config(model_name)
    if not model_config:
        model_config = cfg.models[0] if cfg.models else None
    if not model_config:
        raise ValueError(f"No model '{model_name}' found and no default model configured")

    # Create chat model
    model = create_chat_model(
        model_config=model_config,
        thinking_enabled=thinking_enabled,
    )

    # Resolve tools
    if tools is None:
        tools = get_available_tools(
            model_name=model_name,
            subagent_enabled=subagent_enabled,
            app_config=cfg,
            session=session,
            user=user,
            db=db,
        )

    # Build middleware chain
    middleware = build_forge_middleware_chain(
        app_config=cfg,
        model_name=model_name,
        plan_mode=plan_mode,
        subagent_enabled=subagent_enabled,
        hitl_enabled=hitl_enabled,
        audit_enabled=audit_enabled,
        session=session,
        user=user,
        db=db,
    )

    # Build agent
    agent = create_agent(
        model=model,
        tools=tools,
        middleware=middleware,
        system_prompt=system_prompt,
    )

    return agent


def resolve_model(model_name: Optional[str] = None) -> ModelConfig:
    """Resolve a model name to its configuration."""
    cfg = get_integration_config()
    if model_name:
        m = cfg.get_model_config(model_name)
        if m:
            return m
    return cfg.models[0] if cfg.models else ModelConfig()


def get_available_models() -> list[dict]:
    """Get list of available models for API endpoints."""
    cfg = get_integration_config()
    return [
        {
            "name": m.name,
            "display_name": m.display_name,
            "supports_thinking": m.supports_thinking,
            "supports_vision": m.supports_vision,
        }
        for m in cfg.models
    ]