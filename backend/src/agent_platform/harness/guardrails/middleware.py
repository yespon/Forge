"""Guardrail middleware for the agent pipeline.

Intercepts tool calls in the LangGraph execution and runs them through
registered GuardrailProvider instances before execution.
"""

from __future__ import annotations

from typing import Any, Optional

import structlog

from agent_platform.harness.guardrails.provider import (
    GuardrailAction,
    GuardrailDecision,
    GuardrailProvider,
)

logger = structlog.get_logger(__name__)


class GuardrailMiddleware:
    """Middleware that enforces guardrail checks on tool calls.

    Composes multiple providers; the most restrictive decision wins.

    Usage in agent factory:
        guardrail_mw = GuardrailMiddleware(providers=[builtin, custom])
        # Insert into middleware chain before tool execution
    """

    def __init__(self, providers: Optional[list[GuardrailProvider]] = None):
        self._providers: list[GuardrailProvider] = providers or []

    def add_provider(self, provider: GuardrailProvider) -> None:
        """Register an additional guardrail provider."""
        self._providers.append(provider)

    async def check_tool_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> GuardrailDecision:
        """Run all providers and return the most restrictive decision.

        Priority: DENY > REQUIRE_APPROVAL > WARN > ALLOW
        """
        if not self._providers:
            return GuardrailDecision(action=GuardrailAction.ALLOW)

        decisions: list[GuardrailDecision] = []
        for provider in self._providers:
            try:
                decision = await provider.check(tool_name, tool_input, context)
                decisions.append(decision)
            except Exception as e:
                logger.warning(
                    "guardrail_provider_error",
                    provider=getattr(provider, "name", "unknown"),
                    error=str(e),
                )
                # Fail-open: provider errors don't block execution
                continue

        if not decisions:
            return GuardrailDecision(action=GuardrailAction.ALLOW)

        # Most restrictive wins
        priority = {
            GuardrailAction.DENY: 4,
            GuardrailAction.REQUIRE_APPROVAL: 3,
            GuardrailAction.WARN: 2,
            GuardrailAction.ALLOW: 1,
        }
        most_restrictive = max(decisions, key=lambda d: priority.get(d.action, 0))

        if most_restrictive.action != GuardrailAction.ALLOW:
            logger.info(
                "guardrail_triggered",
                tool_name=tool_name,
                action=most_restrictive.action.value,
                reason=most_restrictive.reason,
                risk_level=most_restrictive.risk_level,
            )

        return most_restrictive

    async def on_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        context: dict[str, Any],
    ) -> None:
        """Notify all providers of tool results (for logging/metrics)."""
        for provider in self._providers:
            try:
                await provider.on_tool_result(tool_name, tool_input, tool_output, context)
            except Exception:
                pass
