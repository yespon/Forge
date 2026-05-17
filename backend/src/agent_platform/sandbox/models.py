"""Sandbox data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SandboxStatus(str, Enum):
    """Sandbox status."""

    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DESTROYED = "destroyed"


@dataclass
class SandboxConfig:
    """Sandbox configuration."""

    # Container configuration
    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_limit: float = 0.5
    timeout: int = 30

    # Environment
    env_vars: dict[str, str] = field(default_factory=dict)
    working_dir: str = "/workspace"

    # Network (default: no network for security)
    network_mode: str = "none"
    allow_internet: bool = False

    # Volumes
    volume_size: str = "1GB"
    mount_paths: list[str] = field(default_factory=list)

    # Security
    read_only: bool = False
    no_new_privileges: bool = True
    seccomp_profile: str | None = None


@dataclass
class ExecutionResult:
    """Command execution result."""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


@dataclass
class SandboxInfo:
    """Sandbox runtime information."""

    id: str
    session_id: str
    status: SandboxStatus
    container_id: str | None
    created_at: datetime
    started_at: datetime | None
    last_activity_at: datetime
    config: SandboxConfig

    # Resource usage
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "status": self.status.value,
            "container_id": self.container_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_activity_at": self.last_activity_at.isoformat(),
            "config": {
                "image": self.config.image,
                "memory_limit": self.config.memory_limit,
                "cpu_limit": self.config.cpu_limit,
                "working_dir": self.config.working_dir,
                "network_mode": self.config.network_mode,
            },
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
        }
