"""Execution context for tool gateway operations.

This module provides the ExecutionContext dataclass that carries
user, session, and request information through tool execution.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

if TYPE_CHECKING:
    from agent_platform.models.session import Session
    from agent_platform.models.task import Task
    from agent_platform.models.user import User


@dataclass
class ExecutionContext:
    """Context for tool execution through the gateway.

    This dataclass carries all necessary context information for
    executing tools, including user, session, task, and request details.
    It is used for audit logging, permission checks, and HITL decisions.
    """

    # User and organization info
    user: "User"
    org_id: Optional[str] = None

    # Session and task context
    session: Optional["Session"] = None
    task: Optional["Task"] = None

    # Request tracking
    request_id: str = field(default_factory=lambda: str(uuid4()))

    # Client information
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Additional context
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Set org_id from user if not provided."""
        if self.org_id is None and hasattr(self.user, "org_id"):
            self.org_id = str(self.user.org_id)

    @property
    def user_id(self) -> str:
        """Get user ID as string."""
        return str(self.user.id)

    @property
    def session_id(self) -> Optional[str]:
        """Get session ID as string."""
        return str(self.session.id) if self.session else None

    @property
    def task_id(self) -> Optional[str]:
        """Get task ID as string."""
        return str(self.task.id) if self.task else None

    def to_dict(self) -> dict[str, Any]:
        """Convert execution context to dictionary (for serialization)."""
        return {
            "user_id": self.user_id,
            "org_id": self.org_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "metadata": self.metadata,
        }

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for audit logging."""
        return {
            "user_id": self.user_id,
            "org_id": self.org_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }


@dataclass
class GatewayConfig:
    """Configuration for Tool Gateway execution.

    This dataclass provides configuration options for controlling
    tool execution behavior through the gateway.
    """

    # HITL settings
    enable_hitl: bool = True
    custom_hitl_rules: Optional[list[dict]] = None

    # Execution settings
    timeout_seconds: Optional[int] = None
    max_retries: int = 0
    retry_delay_seconds: int = 1

    # Audit settings
    enable_audit: bool = True
    audit_level: str = "full"  # full, minimal, errors_only

    # Permission settings
    check_permissions: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enable_hitl": self.enable_hitl,
            "custom_hitl_rules": self.custom_hitl_rules,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "enable_audit": self.enable_audit,
            "audit_level": self.audit_level,
            "check_permissions": self.check_permissions,
        }
