"""Guardrail provider interface.

Defines the abstract protocol for tool authorization decisions.
Custom providers can be registered via configuration to extend
or replace the built-in HITL rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol


class GuardrailAction(str, Enum):
    """Action to take on a tool call."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    WARN = "warn"


@dataclass
class GuardrailDecision:
    """Result of a guardrail check."""

    action: GuardrailAction
    reason: Optional[str] = None
    risk_level: str = "low"  # low, medium, high, critical
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.action in (GuardrailAction.ALLOW, GuardrailAction.WARN)

    @property
    def requires_approval(self) -> bool:
        return self.action == GuardrailAction.REQUIRE_APPROVAL


class GuardrailProvider(Protocol):
    """Protocol for guardrail providers.

    Implement this to create custom authorization logic for tool calls.
    Multiple providers can be composed; the most restrictive decision wins.
    """

    name: str

    async def check(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: dict[str, Any],
    ) -> GuardrailDecision:
        """Check whether a tool call should be allowed.

        Args:
            tool_name: Name of the tool being called.
            tool_input: Arguments passed to the tool.
            context: Execution context (user_id, session_id, etc.)

        Returns:
            GuardrailDecision with action and explanation.
        """
        ...

    async def on_tool_result(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_output: Any,
        context: dict[str, Any],
    ) -> None:
        """Optional hook called after tool execution.

        Useful for logging, metrics, or post-execution validation.
        """
        ...
