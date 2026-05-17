"""Capability planner service.

This module provides the CapabilityPlanner class that creates
execution plans based on required skills and user capabilities.
"""

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.skill import Skill
from agent_platform.services.skill_resolver import SkillDefinition, get_skill_resolver


@dataclass
class CapabilityPlan:
    """Execution plan for a task.

    Contains the skills, tools, and configuration needed
    to execute a task.
    """

    # Skills to enable for this task
    skills: list[str] = field(default_factory=list)

    # Tools to make available to the agent
    tools: list[str] = field(default_factory=list)

    # Whether HITL should be enabled
    enable_hitl: bool = False

    # HITL rules to apply (if HITL is enabled)
    hitl_rules: list[dict] = field(default_factory=list)

    # Model to use (can be overridden per task)
    model: str = "claude-sonnet-4-6"

    # Additional configuration
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert plan to dictionary."""
        return {
            "skills": self.skills,
            "tools": self.tools,
            "enable_hitl": self.enable_hitl,
            "hitl_rules": self.hitl_rules,
            "model": self.model,
            "config": self.config,
        }


class CapabilityPlanner:
    """Capability planner for creating task execution plans.

    The CapabilityPlanner analyzes required skills and user context
to create an execution plan that specifies:
    - Which skills to enable
    - Which tools to make available
    - Whether HITL is needed
    - Any custom configuration
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        """Initialize capability planner.

        Args:
            db: Optional database session for skill lookups
        """
        self.db = db
        self.skill_resolver = get_skill_resolver()

    async def plan(
        self,
        skills: list[str],
        user_id: str,
        enable_hitl: bool = False,
        custom_rules: Optional[list[dict]] = None,
    ) -> CapabilityPlan:
        """Create an execution plan for the given skills.

        Args:
            skills: List of skill names required for the task
            user_id: ID of the user requesting the task
            enable_hitl: Whether to enable HITL for this task
            custom_rules: Optional custom HITL rules

        Returns:
            CapabilityPlan with execution configuration

        Examples:
            >>> planner = CapabilityPlanner()
            >>> plan = await planner.plan(
            ...     skills=["file_ops", "data_analysis"],
            ...     user_id="user-123",
            ...     enable_hitl=True,
            ... )
            >>> plan.tools
            ['read_file', 'write_file', 'execute_bash']
        """
        plan = CapabilityPlan(
            skills=skills,
            enable_hitl=enable_hitl,
            hitl_rules=custom_rules or [],
        )

        # Collect tools from all skills
        tools_set: set[str] = set()
        for skill_name in skills:
            skill_def = self.skill_resolver.get_skill(skill_name)
            if skill_def:
                tools_set.update(skill_def.tools)

        plan.tools = list(tools_set)

        # Check skill availability if database is available
        if self.db:
            await self._check_skill_availability(skills, user_id, plan)

        # Add default tools if no specific skills matched
        if not plan.tools:
            plan.tools = ["execute_bash", "read_file", "write_file"]

        return plan

    async def plan_from_prompt(
        self,
        prompt: str,
        user_id: str,
        enable_hitl: bool = False,
    ) -> CapabilityPlan:
        """Create an execution plan from a user prompt.

        This is a convenience method that resolves skills from
        the prompt and then creates a plan.

        Args:
            prompt: User prompt to analyze
            user_id: ID of the user requesting the task
            enable_hitl: Whether to enable HITL for this task

        Returns:
            CapabilityPlan with execution configuration
        """
        # Resolve skills from prompt
        skills = self.skill_resolver.resolve(prompt)

        # Create plan
        return await self.plan(
            skills=skills,
            user_id=user_id,
            enable_hitl=enable_hitl,
        )

    async def _check_skill_availability(
        self,
        skill_names: list[str],
        user_id: str,
        plan: CapabilityPlan,
    ) -> None:
        """Check if skills are available to the user.

        MVP: This is a placeholder that doesn't actually check permissions.
        In production, this would:
        1. Check if user has grants for restricted skills
        2. Verify skill availability in the org
        3. Apply any org-level restrictions

        Args:
            skill_names: List of skill names to check
            user_id: ID of the user
            plan: Plan to update with availability info
        """
        # MVP: All builtin skills are available
        # In production, this would query the database
        pass

    def get_available_skills(self) -> list[SkillDefinition]:
        """Get list of all available skills.

        Returns:
            List of skill definitions
        """
        return self.skill_resolver.get_all_skills()


# Global planner instance
_default_planner: Optional[CapabilityPlanner] = None


def get_capability_planner(db: Optional[AsyncSession] = None) -> CapabilityPlanner:
    """Get the default capability planner instance.

    Args:
        db: Optional database session

    Returns:
        CapabilityPlanner instance
    """
    global _default_planner
    if _default_planner is None:
        _default_planner = CapabilityPlanner(db=db)
    elif db is not None:
        _default_planner.db = db
    return _default_planner
