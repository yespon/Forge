"""Skill resolver service.

This module provides the SkillResolver class that maps user prompts
to required skills based on keyword matching and intent detection.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class SkillDefinition:
    """Skill definition with metadata."""

    name: str
    description: str
    keywords: list[str]
    tools: list[str]
    priority: int = 0  # Higher = more specific, checked first


# Built-in skill definitions for MVP
# These would ideally be loaded from a database or configuration
BUILTIN_SKILLS: list[SkillDefinition] = [
    SkillDefinition(
        name="file_ops",
        description="File operations: read, write, list files",
        keywords=[
            "file", "read", "write", "create", "delete",
            "folder", "directory", "path", "save", "open",
            "内容", "文件", "读取", "写入", "创建", "删除",
        ],
        tools=["read_file", "write_file", "execute_bash"],
        priority=10,
    ),
    SkillDefinition(
        name="data_analysis",
        description="Data analysis and processing",
        keywords=[
            "analyze", "data", "csv", "json", "parse",
            "statistics", "chart", "graph", "visualization",
            "计算", "分析", "数据", "统计", "图表",
        ],
        tools=["read_file", "execute_bash"],
        priority=10,
    ),
    SkillDefinition(
        name="code_execution",
        description="Execute code and scripts",
        keywords=[
            "run", "execute", "python", "script", "code",
            "bash", "shell", "command", "terminal",
            "运行", "执行", "代码", "脚本", "命令",
        ],
        tools=["execute_bash"],
        priority=10,
    ),
    SkillDefinition(
        name="web_search",
        description="Search the web for information",
        keywords=[
            "search", "find", "google", "look up", "web",
            "internet", "online", "latest", "news",
            "搜索", "查找", "查询", "网上", "最新",
        ],
        tools=["web_search"],
        priority=5,
    ),
    SkillDefinition(
        name="git_ops",
        description="Git operations",
        keywords=[
            "git", "commit", "branch", "merge", "push", "pull",
            "repository", "repo", "version control",
            "git", "提交", "分支", "合并", "仓库",
        ],
        tools=["execute_bash"],
        priority=10,
    ),
    SkillDefinition(
        name="docker_ops",
        description="Docker operations",
        keywords=[
            "docker", "container", "image", "compose",
            "dockerfile", "build", "deploy",
            "docker", "容器", "镜像", "构建",
        ],
        tools=["execute_bash"],
        priority=10,
    ),
]


class SkillResolver:
    """Skill resolver for mapping prompts to skills.

    The SkillResolver analyzes user prompts and determines which
    skills are needed to fulfill the request. This is an MVP
    implementation using keyword matching.
    """

    def __init__(self, custom_skills: Optional[list[SkillDefinition]] = None):
        """Initialize skill resolver.

        Args:
            custom_skills: Optional list of custom skill definitions
        """
        self.skills = BUILTIN_SKILLS.copy()
        if custom_skills:
            self.skills.extend(custom_skills)

        # Sort by priority (higher first)
        self.skills.sort(key=lambda s: s.priority, reverse=True)

    def resolve(self, prompt: str) -> list[str]:
        """Resolve prompt to list of required skill names.

        Args:
            prompt: User prompt to analyze

        Returns:
            List of skill names needed for the task

        Examples:
            >>> resolver = SkillResolver()
            >>> resolver.resolve("Analyze the sales data in report.csv")
            ['data_analysis', 'file_ops']
            >>> resolver.resolve("Read the config file and run the script")
            ['file_ops', 'code_execution']
        """
        prompt_lower = prompt.lower()
        matched_skills: list[tuple[str, int]] = []  # (skill_name, match_count)

        for skill in self.skills:
            match_count = self._count_matches(prompt_lower, skill.keywords)
            if match_count > 0:
                matched_skills.append((skill.name, match_count))

        # Sort by match count (descending) and return skill names
        matched_skills.sort(key=lambda x: x[1], reverse=True)

        # Return unique skill names (preserve order)
        seen = set()
        result = []
        for skill_name, _ in matched_skills:
            if skill_name not in seen:
                seen.add(skill_name)
                result.append(skill_name)

        return result

    def resolve_with_details(self, prompt: str) -> list[SkillDefinition]:
        """Resolve prompt to list of skill definitions with details.

        Args:
            prompt: User prompt to analyze

        Returns:
            List of skill definitions needed for the task
        """
        skill_names = self.resolve(prompt)
        return [s for s in self.skills if s.name in skill_names]

    def _count_matches(self, text: str, keywords: list[str]) -> int:
        """Count how many keywords match in the text.

        Args:
            text: Text to search in (lowercase)
            keywords: List of keywords to match

        Returns:
            Number of matching keywords
        """
        count = 0
        for keyword in keywords:
            # Use word boundary matching for English keywords
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text):
                count += 1
            # For Chinese/short keywords, use simple containment
            elif len(keyword) <= 4 and keyword.lower() in text:
                count += 1
        return count

    def add_skill(self, skill: SkillDefinition) -> None:
        """Add a custom skill definition.

        Args:
            skill: Skill definition to add
        """
        # Remove existing skill with same name if present
        self.skills = [s for s in self.skills if s.name != skill.name]
        self.skills.append(skill)
        # Re-sort by priority
        self.skills.sort(key=lambda s: s.priority, reverse=True)

    def get_skill(self, name: str) -> Optional[SkillDefinition]:
        """Get a skill definition by name.

        Args:
            name: Skill name

        Returns:
            Skill definition or None if not found
        """
        for skill in self.skills:
            if skill.name == name:
                return skill
        return None

    def get_all_skills(self) -> list[SkillDefinition]:
        """Get all registered skill definitions.

        Returns:
            List of all skill definitions
        """
        return self.skills.copy()


# Global resolver instance
_default_resolver: Optional[SkillResolver] = None


def get_skill_resolver() -> SkillResolver:
    """Get the default skill resolver instance.

    Returns:
        SkillResolver instance
    """
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = SkillResolver()
    return _default_resolver
