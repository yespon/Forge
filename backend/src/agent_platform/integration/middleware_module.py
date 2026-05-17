"""Middleware chain builder for Forge x DeerFlow integration.

Builds the middleware pipeline that processes agent execution,
combining DeerFlow's harness middlewares with Forge's enterprise
middlewares (HITL approval, audit logging, multi-tenant RBAC).
"""

import logging
from typing import Any, Optional

from langchain.agents.middleware import AgentMiddleware

from agent_platform.integration.middleware import (
    ClarificationMiddleware,
    DanglingToolCallMiddleware,
    DynamicContextMiddleware,
    ForgeAuditMiddleware,
    ForgeHITLMiddleware,
    LoopDetectionMiddleware,
    MemoryMiddleware,
    SandboxMiddleware,
    SubagentLimitMiddleware,
    SummarizationMiddleware,
    TitleMiddleware,
    TodoMiddleware,
    ToolErrorHandlingMiddleware,
)
from agent_platform.integration.config import ForgeDeerFlowConfig

logger = logging.getLogger(__name__)


def build_forge_middleware_chain(
    app_config: Optional[ForgeDeerFlowConfig] = None,
    model_name: Optional[str] = None,
    plan_mode: bool = False,
    subagent_enabled: bool = False,
    hitl_enabled: bool = False,
    audit_enabled: bool = True,
    session: Optional[Any] = None,
    user: Optional[Any] = None,
    db: Optional[Any] = None,
) -> list[AgentMiddleware]:
    """Build the complete middleware chain for a Forge agent.

    Order (by execution priority):
      1. SandboxMiddleware         - Environment setup
      2. DanglingToolCallMiddleware - Patch missing tool results
      3. ToolErrorHandlingMiddleware- Handle tool execution errors
      4. SummarizationMiddleware     - Context reduction (if enabled)
      5. TodoMiddleware              - Task tracking (if plan_mode)
      6. TitleMiddleware             - Auto-title (if enabled)
      7. MemoryMiddleware            - Memory recall (if enabled)
      8. ForgeHITLMiddleware         - HITL approval (if enabled)
      9. ForgeAuditMiddleware        - Audit logging (if enabled)
      10. SubagentLimitMiddleware    - Subagent concurrency (if enabled)
      11. LoopDetectionMiddleware    - Loop detection (if enabled)
      12. ClarificationMiddleware    - Clarification handling (always last)

    Args:
        app_config: Integration configuration
        model_name: Current model name
        plan_mode: Enable plan mode with todo list
        subagent_enabled: Enable sub-agent delegation
        hitl_enabled: Enable HITL approval
        audit_enabled: Enable audit logging
        session: Forge Session
        user: Forge User
        db: Database session

    Returns:
        Ordered list of middleware instances
    """
    cfg = app_config
    chain: list[AgentMiddleware] = []

    # Common context
    session_id = str(session.id) if session else None
    user_id = str(user.id) if user else None
    org_id = str(user.org_id) if user and hasattr(user, "org_id") else None

    # 1. Sandbox (always)
    chain.append(SandboxMiddleware(lazy_init=True))

    # 2. Dangling tool calls (always)
    chain.append(DanglingToolCallMiddleware())

    # 3. Tool error handling (always)
    chain.append(ToolErrorHandlingMiddleware())

    # 4. Summarization (if enabled)
    if cfg and cfg.summarization.enabled:
        chain.append(SummarizationMiddleware(
            trigger=cfg.summarization.trigger,
            keep=cfg.summarization.keep,
            trim_tokens_to_summarize=cfg.summarization.trim_tokens_to_summarize,
            skills_container_path=cfg.skills.container_path,
            preserve_recent_skill_count=cfg.summarization.preserve_recent_skill_count,
        ))

    # 5. Todo list (if plan mode)
    if plan_mode:
        chain.append(TodoMiddleware())

    # 6. Title generation (if enabled)
    if cfg and cfg.title.enabled:
        chain.append(TitleMiddleware(
            max_words=cfg.title.max_words,
            max_chars=cfg.title.max_chars,
        ))

    # 7. Memory (if enabled)
    if cfg and cfg.memory.enabled:
        chain.append(MemoryMiddleware(
            agent_name="lead_agent",
            memory_config=cfg.memory,
        ))

    # 8. Forge HITL (if enabled)
    if hitl_enabled:
        chain.append(ForgeHITLMiddleware(
            session_id=session_id, org_id=org_id, user_id=user_id, db=db,
        ))

    # 9. Forge Audit (if enabled)
    if audit_enabled:
        chain.append(ForgeAuditMiddleware(
            session_id=session_id, user_id=user_id, org_id=org_id, db=db,
        ))

    # 10. Subagent limit (if enabled)
    if subagent_enabled:
        chain.append(SubagentLimitMiddleware(max_concurrent=3))

    # 11. Loop detection (if enabled)
    if cfg and cfg.loop_detection.enabled:
        chain.append(LoopDetectionMiddleware.from_config(cfg.loop_detection))

    # 12. Clarification (always last)
    chain.append(ClarificationMiddleware())

    logger.info(
        "Built middleware chain: %d middlewares (plan=%s subagent=%s hitl=%s audit=%s)",
        len(chain), plan_mode, subagent_enabled, hitl_enabled, audit_enabled,
    )

    return chain
