"""Skills system adapted from DeerFlow's SKILL.md format for Forge.

Supports loading skills from SKILL.md files and injecting them
into the system prompt, with Forge's permission controls.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from agent_platform.integration.config import ForgeDeerFlowConfig, get_integration_config

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A skill loaded from SKILL.md."""
    name: str
    description: str = ""
    instructions: str = ""
    license: str = ""
    allowed_tools: Optional[list[str]] = None
    source_path: str = ""
    is_active: bool = True


class SkillLoader:
    """Loads skills from SKILL.md files.

    Skills are Markdown files with YAML front matter that define
    agent capabilities. The content is injected into the system prompt.
    """

    def __init__(self, skills_path: str = "skills"):
        self.skills_path = Path(skills_path)
        self._skills: dict[str, Skill] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        """Load all skills from the skills directory."""
        if not self.skills_path.exists():
            logger.info(f"Skills directory not found: {self.skills_path}")
            return

        for skill_dir in sorted(self.skills_path.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                skill = self._parse_skill(skill_file, skill_dir)
                self._skills[skill.name] = skill
                logger.info(f"Loaded skill: '{skill.name}' from {skill_dir.name}")
            except Exception as e:
                logger.warning(f"Failed to load skill from {skill_dir}: {e}")

    def _parse_skill(self, skill_file: Path, skill_dir: Path) -> Skill:
        """Parse a SKILL.md file with YAML front matter."""
        content = skill_file.read_text(encoding="utf-8")

        # Extract YAML front matter
        front_matter = {}
        instructions = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    front_matter = yaml.safe_load(parts[1]) or {}
                    instructions = parts[2].strip()
                except yaml.YAMLError as e:
                    logger.warning(f"YAML parse error in {skill_file}: {e}")

        name = front_matter.get("name", skill_dir.name)
        description = front_matter.get("description", "")

        return Skill(
            name=name,
            description=description,
            instructions=instructions,
            license=front_matter.get("license", ""),
            allowed_tools=front_matter.get("allowed-tools"),
            source_path=str(skill_dir.relative_to(self.skills_path.parent) if self.skills_path.parent else skill_dir),
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_enabled_skills(self, enabled_names: Optional[set[str]] = None) -> list[Skill]:
        """Get skills filtered by enabled names."""
        if enabled_names is None:
            return list(self._skills.values())
        return [s for s in self._skills.values() if s.name in enabled_names]

    def get_skill_instructions(self, enabled_names: Optional[set[str]] = None) -> str:
        """Get combined instructions for enabled skills.

        Returns formatted instructions suitable for system prompt injection.
        """
        skills = self.get_enabled_skills(enabled_names)
        if not skills:
            return ""

        parts = ["<skills>"]
        for skill in skills:
            parts.append(f"<skill name=\"{skill.name}\">")
            parts.append(skill.instructions)
            parts.append("</skill>")
        parts.append("</skills>")

        return "\n\n".join(parts)

    def get_all_skill_names(self) -> list[str]:
        """Get names of all loaded skills."""
        return list(self._skills.keys())

    def reload(self) -> None:
        """Reload all skills from disk."""
        self._skills.clear()
        self._load_skills()


class SkillManager:
    """Manages skill enablement and injection."""

    def __init__(self, skills_path: str = "skills"):
        self.loader = SkillLoader(skills_path)
        self._enabled: set[str] = set()

    def enable_skill(self, name: str) -> bool:
        """Enable a skill by name."""
        if name in self.loader.get_all_skill_names():
            self._enabled.add(name)
            return True
        return False

    def disable_skill(self, name: str) -> None:
        """Disable a skill."""
        self._enabled.discard(name)

    def set_enabled_skills(self, names: list[str]) -> None:
        """Set the enabled skills list."""
        available = set(self.loader.get_all_skill_names())
        self._enabled = set(names) & available

    def get_system_prompt_instructions(self) -> str:
        """Get skill instructions for system prompt injection."""
        return self.loader.get_skill_instructions(self._enabled if self._enabled else None)

    @property
    def enabled_skills(self) -> list[Skill]:
        """Get currently enabled skills."""
        return self.loader.get_enabled_skills(self._enabled if self._enabled else None)

    @property
    def all_skills(self) -> list[Skill]:
        return self.loader.get_enabled_skills()


# Global skill manager
_skill_manager: Optional[SkillManager] = None


def get_skill_manager(skills_path: Optional[str] = None) -> SkillManager:
    """Get or create the global skill manager."""
    global _skill_manager
    if _skill_manager is None:
        cfg = get_integration_config()
        path = skills_path or cfg.skills.path
        _skill_manager = SkillManager(skills_path=path)
    return _skill_manager