"""Skill Registry for managing and loading skills."""

import importlib.util
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import yaml
from langchain_core.tools import StructuredTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.skill import Skill, SkillGrant
from agent_platform.models.user import User, UserRole

if TYPE_CHECKING:
    from agent_platform.models.session import Session as SessionModel


class SkillLoadError(Exception):
    """Error loading a skill."""

    pass


class SkillPermissionError(Exception):
    """Error accessing a skill due to permission."""

    pass


class SkillRegistry:
    """Registry for managing skills and their tools."""

    # Migration date for backward compatibility
    # Sessions created before this date get automatic skill grants
    MIGRATION_DATE: datetime = datetime(2026, 5, 5, 0, 0, 0)

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize the skill registry.

        Args:
            db: Optional database session for persistence
        """
        self.db = db
        self._builtin_skills: dict[str, Skill] = {}
        self._tool_cache: dict[str, StructuredTool] = {}

        # Load builtin skills on initialization
        self._load_builtin_skills()

    def _get_builtin_skills_dir(self) -> Path:
        """Get the builtin skills directory path."""
        # Look for skills directory relative to package root
        current_file = Path(__file__).resolve()
        # Go up to src/agent_platform, then to skills/builtin
        skills_dir = current_file.parent.parent / "skills" / "builtin"
        return skills_dir

    def _load_builtin_skills(self) -> None:
        """Load all builtin skills from the skills/builtin directory."""
        skills_dir = self._get_builtin_skills_dir()

        if not skills_dir.exists():
            # No builtin skills directory yet
            return

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_yaml = skill_dir / "skill.yaml"
            if not skill_yaml.exists():
                continue

            try:
                skill = self._load_skill_from_yaml(skill_yaml, skill_dir)
                self._builtin_skills[skill.name] = skill
            except Exception as e:
                # Log error but continue loading other skills
                print(f"Failed to load builtin skill from {skill_dir}: {e}")

    def _load_skill_from_yaml(self, yaml_path: Path, skill_dir: Path) -> Skill:
        """Load a skill definition from a YAML file.

        Args:
            yaml_path: Path to the skill.yaml file
            skill_dir: Directory containing the skill

        Returns:
            Skill instance
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            manifest = yaml.safe_load(f)

        name = manifest.get("name")
        if not name:
            raise SkillLoadError("Skill manifest missing 'name' field")

        version = manifest.get("version", "0.1.0")

        # Parse restrictions
        restrictions = manifest.get("restrictions", {})
        is_restricted = bool(restrictions)

        return Skill(
            name=name,
            version=version,
            description=manifest.get("description", ""),
            visibility="builtin",
            manifest=manifest,
            source_path=str(skill_dir.relative_to(Path(__file__).parent.parent)),
            is_builtin=True,
            is_restricted=is_restricted,
            restrictions=restrictions,
            is_active=True,
        )

    def get_builtin_skill(self, name: str) -> Optional[Skill]:
        """Get a builtin skill by name.

        Args:
            name: Skill name

        Returns:
            Skill instance or None if not found
        """
        return self._builtin_skills.get(name)

    def list_builtin_skills(self) -> list[Skill]:
        """List all available builtin skills.

        Returns:
            List of builtin skills
        """
        return list(self._builtin_skills.values())

    def _load_tool_function(self, skill: Skill, tool_def: dict) -> callable:
        """Load a tool function from a skill.

        Args:
            skill: Skill instance
            tool_def: Tool definition from manifest

        Returns:
            Callable tool function
        """
        entrypoint = tool_def.get("entrypoint")
        if not entrypoint:
            raise SkillLoadError(f"Tool {tool_def.get('name')} missing entrypoint")

        # Parse entrypoint (e.g., "tools.read_file" or "file_ops.tools:read_file")
        if "." in entrypoint:
            module_path, func_name = entrypoint.rsplit(".", 1)
        elif ":" in entrypoint:
            module_path, func_name = entrypoint.split(":", 1)
        else:
            raise SkillLoadError(f"Invalid entrypoint format: {entrypoint}")

        # Resolve module path relative to skill directory
        if skill.source_path:
            base_dir = Path(__file__).parent.parent / skill.source_path
            module_file = base_dir / f"{module_path}.py"

            if module_file.exists():
                spec = importlib.util.spec_from_file_location(
                    f"skill_{skill.name}_{module_path}", module_file
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return getattr(module, func_name)

        # Fallback: try to import as absolute module
        full_module = f"agent_platform.{skill.source_path}.{module_path}".replace("/", ".")
        module = importlib.import_module(full_module)
        return getattr(module, func_name)

    def get_skill_tools(
        self,
        skill_name: str,
        user: Optional[User] = None,
        auto_grant: bool = False,
    ) -> list[StructuredTool]:
        """Get tools for a skill if the user has permission.

        Args:
            skill_name: Name of the skill
            user: User requesting the tools
            auto_grant: Whether to auto-grant restricted skills

        Returns:
            List of structured tools

        Raises:
            SkillPermissionError: If user doesn't have permission
            SkillLoadError: If skill not found or failed to load
        """
        skill = self._builtin_skills.get(skill_name)
        if not skill:
            raise SkillLoadError(f"Skill not found: {skill_name}")

        # Check permissions
        if skill.is_restricted and not auto_grant:
            if user is None or not skill.can_be_used_by(user):
                raise SkillPermissionError(
                    f"User does not have permission to use skill: {skill_name}"
                )

        # Get tools from manifest
        manifest = skill.manifest
        tools_def = manifest.get("tools", [])

        tools = []
        for tool_def in tools_def:
            tool_name = tool_def.get("name")
            if not tool_name:
                continue

            # Check cache first
            cache_key = f"{skill_name}:{tool_name}"
            if cache_key in self._tool_cache:
                tools.append(self._tool_cache[cache_key])
                continue

            # Load tool function
            func = self._load_tool_function(skill, tool_def)

            # Create structured tool
            description = tool_def.get("description", func.__doc__ or "")
            tool = StructuredTool.from_function(
                func=func,
                name=tool_name,
                description=description,
            )

            self._tool_cache[cache_key] = tool
            tools.append(tool)

        return tools

    async def check_skill_grant(
        self,
        skill_name: str,
        session: "SessionModel",
    ) -> bool:
        """Check if a skill is granted for a session.

        Args:
            skill_name: Name of the skill
            session: Session to check

        Returns:
            True if skill is granted
        """
        if not self.db:
            return False

        # Get skill
        skill = self._builtin_skills.get(skill_name)
        if not skill:
            return False

        # Not restricted - anyone can use
        if not skill.is_restricted:
            return True

        # Check for explicit grant
        query = select(SkillGrant).where(
            SkillGrant.skill_id == skill.id,
            SkillGrant.session_id == session.id,
        )
        result = await self.db.execute(query)
        grant = result.scalar_one_or_none()

        if grant and not grant.is_expired:
            return True

        # Check for user-level grant
        if session.user_id:
            query = select(SkillGrant).where(
                SkillGrant.skill_id == skill.id,
                SkillGrant.user_id == session.user_id,
            )
            result = await self.db.execute(query)
            grant = result.scalar_one_or_none()

            if grant and not grant.is_expired:
                return True

        return False

    async def get_tools_for_session(
        self,
        session: "SessionModel",
        user: Optional[User] = None,
    ) -> list[StructuredTool]:
        """Get all tools available for a session.

        This method implements backward compatibility:
        - Sessions created before MIGRATION_DATE get file_ops auto-granted
        - New sessions start with no tools (secure by default)

        Args:
            session: Session to get tools for
            user: User associated with the session

        Returns:
            List of structured tools
        """
        tools = []

        # Get enabled skills from session settings
        enabled_skills = session.settings.get("enabled_skills", [])

        for skill_name in enabled_skills:
            skill = self._builtin_skills.get(skill_name)
            if not skill:
                continue

            # Check if skill is restricted and needs grant
            if skill.is_restricted:
                # Check explicit grant
                has_grant = await self.check_skill_grant(skill_name, session)

                # Backward compatibility: auto-grant for old sessions
                if not has_grant and session.created_at < self.MIGRATION_DATE:
                    has_grant = True

                if not has_grant:
                    continue

            try:
                skill_tools = self.get_skill_tools(skill_name, user, auto_grant=False)
                tools.extend(skill_tools)
            except (SkillPermissionError, SkillLoadError):
                # Skip skills that can't be loaded or user doesn't have permission for
                continue

        # Backward compatibility: Old sessions without enabled_skills get file_ops
        if not enabled_skills and session.created_at < self.MIGRATION_DATE:
            if "file_ops" in self._builtin_skills:
                try:
                    file_ops_tools = self.get_skill_tools(
                        "file_ops", user, auto_grant=True
                    )
                    tools.extend(file_ops_tools)
                except SkillLoadError:
                    pass

        return tools

    async def grant_skill_to_session(
        self,
        skill_name: str,
        session: "SessionModel",
        granted_by: Optional[User] = None,
    ) -> SkillGrant:
        """Grant a skill to a session.

        Args:
            skill_name: Name of the skill to grant
            session: Session to grant the skill to
            granted_by: User granting the skill

        Returns:
            SkillGrant instance

        Raises:
            SkillLoadError: If skill not found
        """
        if not self.db:
            raise RuntimeError("Database session required for granting skills")

        skill = self._builtin_skills.get(skill_name)
        if not skill:
            raise SkillLoadError(f"Skill not found: {skill_name}")

        # Create or get skill in database
        from sqlalchemy import select

        db_skill = await self.db.execute(
            select(Skill).where(Skill.name == skill_name, Skill.is_builtin == True)
        )
        db_skill = db_skill.scalar_one_or_none()

        if not db_skill:
            # Create database record for builtin skill
            db_skill = Skill(
                name=skill.name,
                version=skill.version,
                description=skill.description,
                visibility=skill.visibility,
                manifest=skill.manifest,
                source_path=skill.source_path,
                is_builtin=True,
                is_restricted=skill.is_restricted,
                restrictions=skill.restrictions,
                is_active=True,
            )
            self.db.add(db_skill)
            await self.db.flush()

        # Create grant
        grant = SkillGrant(
            skill_id=db_skill.id,
            session_id=session.id,
            granted_by=granted_by.id if granted_by else None,
        )
        self.db.add(grant)
        await self.db.commit()

        return grant

    def get_available_skills_for_user(self, user: User) -> list[dict]:
        """Get list of skills available to a user.

        Args:
            user: User to check

        Returns:
            List of skill info dictionaries
        """
        available = []

        for skill in self._builtin_skills.values():
            can_use = skill.can_be_used_by(user)
            available.append({
                "name": skill.name,
                "version": skill.version,
                "description": skill.description,
                "is_restricted": skill.is_restricted,
                "can_use": can_use,
                "tools": [t.get("name") for t in skill.manifest.get("tools", [])],
            })

        return available


# Global registry instance (lazy initialization)
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry(db: Optional[AsyncSession] = None) -> SkillRegistry:
    """Get or create the global skill registry.

    Args:
        db: Optional database session

    Returns:
        SkillRegistry instance
    """
    global _skill_registry

    if _skill_registry is None:
        _skill_registry = SkillRegistry(db=db)
    elif db is not None:
        _skill_registry.db = db

    return _skill_registry
