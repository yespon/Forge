"""setup_agent + update_agent — let users create custom agents via SOUL.md."""

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

import yaml
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_agents_base() -> str:
    return os.environ.get("FORGE_AGENTS_PATH", ".deer-flow/users/anonymous/agents")


def _validate_agent_name(name: str) -> str:
    name = name.strip().lower().replace(" ", "-")
    if not name or len(name) > 64:
        raise ValueError(f"Invalid agent name: {name!r}")
    if not re.match(r"^[a-z0-9_-]+$", name):
        raise ValueError(f"Agent name must match ^[a-z0-9_-]+$, got {name!r}")
    return name


@tool(parse_docstring=True)
def setup_agent(
    soul: str,
    description: str,
    name: Optional[str] = None,
    skills: Optional[list[str]] = None,
) -> str:
    """Create or reconfigure a custom DeerFlow agent.

    Persists a SOUL.md + config.yaml so the agent definition survives restarts.

    Args:
        soul: Full SOUL.md markdown content defining the agent personality.
        description: One-line description of what this agent does.
        name: Unique agent name (auto-generated if omitted).
        skills: Skill names this agent may use. None = all, [] = none.

    Returns:
        Confirmation with the agent directory path.
    """
    if name is None:
        name = f"agent-{uuid.uuid4().hex[:6]}"
    name = _validate_agent_name(name)

    base = Path(_get_agents_base())
    agent_dir = base / name
    agent_dir.mkdir(parents=True, exist_ok=True)

    (agent_dir / "SOUL.md").write_text(soul)
    cfg = {"name": name, "description": description, "skills": skills}
    (agent_dir / "config.yaml").write_text(yaml.dump(cfg, default_flow_style=False))

    logger.info("Custom agent %r created at %s", name, agent_dir)
    return f"Agent {name!r} created: {agent_dir}/SOUL.md"


@tool(parse_docstring=True)
def update_agent(
    name: str,
    soul: Optional[str] = None,
    description: Optional[str] = None,
    skills: Optional[list[str]] = None,
) -> str:
    """Persist updates to an existing custom agent's SOUL.md or config.

    Args:
        name: Existing agent name.
        soul: Full replacement SOUL.md content (optional).
        description: New description (optional).
        skills: New skill allow-list (optional).

    Returns:
        Confirmation.
    """
    name = _validate_agent_name(name)
    agent_dir = Path(_get_agents_base()) / name
    if not agent_dir.exists():
        return f"Error: agent {name!r} does not exist"

    if soul is not None:
        (agent_dir / "SOUL.md").write_text(soul)

    if description is not None or skills is not None:
        cfg_path = agent_dir / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        if description is not None:
            cfg["description"] = description
        if skills is not None:
            cfg["skills"] = skills
        cfg_path.write_text(yaml.dump(cfg, default_flow_style=False))

    return f"Agent {name!r} updated"


def load_custom_agent(name: str) -> Optional[dict]:
    """Load a custom agent's config and SOUL.md content.

    Returns dict with 'name', 'description', 'soul', 'skills' or None.
    """
    name = _validate_agent_name(name)
    agent_dir = Path(_get_agents_base()) / name
    if not agent_dir.exists():
        return None

    cfg = {}
    cfg_path = agent_dir / "config.yaml"
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text()) or {}

    soul = ""
    soul_path = agent_dir / "SOUL.md"
    if soul_path.exists():
        soul = soul_path.read_text()

    return {
        "name": name,
        "description": cfg.get("description", ""),
        "soul": soul,
        "skills": cfg.get("skills"),
    }


def list_custom_agents() -> list[str]:
    """List all custom agent names."""
    base = Path(_get_agents_base())
    if not base.exists():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and (d / "config.yaml").exists() and (d / "SOUL.md").exists()
    )
