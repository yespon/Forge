"""Built-in guardrail provider using Forge's HITL rules engine.

Wraps the existing hitl_rules.py service as a GuardrailProvider,
providing backward compatibility while enabling the pluggable interface.
"""

from __future__ import annotations

from typing import Any, Optional

from agent_platform.harness.guardrails.provider import (
    GuardrailAction,
    GuardrailDecision,
)


class BuiltinGuardrailProvider:
    """Default guardrail provider backed by Forge HITL rules.

    Delegates to services/hitl_rules.py for pattern matching,
    translating rule matches into GuardrailDecision objects.
    """

    name = "builtin"

    def __init__(self, rules_service: Optional[Any] = None):
        self._rules_service = rules_service

    def _get_rules_service(self):
        if self._rules_service is None:
            from agent_platform.services.hitl_rules import HITLRulesEngine

            self._rules_service = HITLRulesEngine()
        return self._rules_service

    async def check(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> GuardrailDecision:
        """Check tool call against built-in HITL rules."""
        engine = self._get_rules_service()
        result = engine.check_rules(tool_name, tool_input, context)

        if result is None:
            return GuardrailDecision(action=GuardrailAction.ALLOW)

        # Map HITL risk levels to guardrail actions
        risk_level = result.get("risk_level", "medium")
        if risk_level == "critical":
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                reason=result.get("reason", "Blocked by security policy"),
                risk_level=risk_level,
                metadata=result,
            )
        elif risk_level in ("high", "medium"):
            return GuardrailDecision(
                action=GuardrailAction.REQUIRE_APPROVAL,
                reason=result.get("reason", "Requires human approval"),
                risk_level=risk_level,
                metadata=result,
            )
        else:
            return GuardrailDecision(
                action=GuardrailAction.WARN,
                reason=result.get("reason"),
                risk_level=risk_level,
                metadata=result,
            )

    async def on_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        context: dict[str, Any],
    ) -> None:
        """No-op for builtin provider."""
        pass
