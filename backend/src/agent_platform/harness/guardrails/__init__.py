"""Guardrails — Pre-tool-call authorization framework.

Provides a pluggable provider interface for tool authorization checks.
Compatible with DeerFlow's guardrails/ module pattern.

Architecture:
- GuardrailProvider: Abstract interface for authorization decisions
- BuiltinGuardrailProvider: Default provider using Forge's HITL rules
- GuardrailMiddleware: Middleware adapter for the agent pipeline
"""

from agent_platform.harness.guardrails.provider import (
    GuardrailDecision,
    GuardrailProvider,
)
from agent_platform.harness.guardrails.builtin import BuiltinGuardrailProvider
from agent_platform.harness.guardrails.middleware import GuardrailMiddleware

__all__ = [
    "GuardrailDecision",
    "GuardrailMiddleware",
    "GuardrailProvider",
    "BuiltinGuardrailProvider",
]
