"""
Unified configuration for Forge + DeerFlow integration.

Merges Forge's Pydantic Settings (from .env) with DeerFlow's YAML config format.
Forge settings take precedence for overlapping values.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from agent_platform.config import get_settings as get_forge_settings
from agent_platform.integration.types import (
    ChannelConfig,
    ChannelSessionConfig,
    DatabaseConfig,
    GuardrailsConfig,
    LoopDetectionConfig,
    MemoryConfig,
    ModelConfig,
    RunEventsConfig,
    SkillConfig,
    SubAgentConfig,
    SummarizationConfig,
    SummarizationKeep,
    SummarizationKeepType,
    SummarizationTrigger,
    SummarizationTriggerType,
    TitleConfig,
    TokenUsageConfig,
    ToolConfig,
    ToolSearchConfig,
)


class ForgeDeerFlowConfig:
    """Unified Forge + DeerFlow configuration."""

    def __init__(self, forge_settings: Any = None):
        self.forge = forge_settings

        # LLM Models
        self.models: list[ModelConfig] = []

        # Tool configuration
        self.tool_groups: list[dict] = [
            {"name": "web"},
            {"name": "file:read"},
            {"name": "file:write"},
            {"name": "bash"},
        ]
        self.tools: list[ToolConfig] = [
            ToolConfig(name="web_search", group="web", use="agent_platform.integration.tools.web_search:web_search_tool"),
            ToolConfig(name="read_file", group="file:read", use="agent_platform.integration.tools.file_ops:read_file_tool"),
            ToolConfig(name="write_file", group="file:write", use="agent_platform.integration.tools.file_ops:write_file_tool"),
            ToolConfig(name="bash", group="bash", use="agent_platform.integration.tools.bash:bash_tool"),
        ]

        # Skills
        self.skills = SkillConfig()

        # Database (always Postgres for Forge)
        db_url = str(forge_settings.DATABASE_URL) if forge_settings else ""
        self.database = DatabaseConfig(backend="postgres", postgres_url=db_url)

        # Features with defaults
        self.tool_search = ToolSearchConfig()
        self.loop_detection = LoopDetectionConfig()
        self.subagents = SubAgentConfig()
        self.summarization = SummarizationConfig()
        self.memory = MemoryConfig()
        self.title = TitleConfig()
        self.token_usage = TokenUsageConfig()
        self.guardrails = GuardrailsConfig()
        self.run_events = RunEventsConfig()
        self.channels = ChannelConfig()

    def get_model_config(self, name: str) -> Optional[ModelConfig]:
        for m in self.models:
            if m.name == name:
                return m
        return None

    @property
    def default_model_name(self) -> str:
        if self.models:
            return self.models[0].name
        return ""

    @property
    def log_level(self) -> str:
        return self.forge.LOG_LEVEL if self.forge else "info"


def load_yaml_config(path: str) -> Optional[dict]:
    """Load and resolve environment variables in a YAML config."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        raw = f.read()
    # Resolve $VAR patterns
    import re
    def _resolve_env(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    resolved = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', _resolve_env, raw)
    return yaml.safe_load(resolved)


def _load_models(config: ForgeDeerFlowConfig, data: dict) -> None:
    for item in data.get("models", []):
        config.models.append(ModelConfig(
            name=item["name"],
            display_name=item.get("display_name", item["name"]),
            use=item.get("use", "langchain_openai:ChatOpenAI"),
            model=item.get("model", item["name"]),
            api_key=item.get("api_key", ""),
            api_base=item.get("api_base", ""),
            base_url=item.get("base_url", ""),
            max_tokens=item.get("max_tokens", 4096),
            temperature=item.get("temperature", 0.7),
            timeout=item.get("timeout", 600.0),
            max_retries=item.get("max_retries", 2),
            supports_thinking=item.get("supports_thinking", False),
            supports_vision=item.get("supports_vision", False),
        ))


def _load_tools(config: ForgeDeerFlowConfig, data: dict) -> None:
    existing_names = {t.name for t in config.tools}
    for item in data.get("tools", []):
        name = item["name"]
        if name not in existing_names:
            config.tools.append(ToolConfig(
                name=name,
                group=item.get("group", "default"),
                use=item["use"],
            ))


def _load_features(config: ForgeDeerFlowConfig, data: dict) -> None:
    # Summarization
    if "summarization" in data:
        s = data["summarization"]
        cfg = config.summarization
        cfg.enabled = s.get("enabled", True)
        cfg.model_name = s.get("model_name")
        cfg.trim_tokens_to_summarize = s.get("trim_tokens_to_summarize", 15564)

        trigger_raw = s.get("trigger")
        if trigger_raw:
            if not isinstance(trigger_raw, list):
                trigger_raw = [trigger_raw]
            triggers = []
            for t in trigger_raw:
                triggers.append(SummarizationTrigger(
                    type=SummarizationTriggerType(t.get("type", "tokens")),
                    value=t.get("value", 15564),
                ))
            cfg.trigger = triggers

        keep_raw = s.get("keep", {})
        cfg.keep = SummarizationKeep(
            type=SummarizationKeepType(keep_raw.get("type", "messages")),
            value=keep_raw.get("value", 10),
        )

    # Memory
    if "memory" in data:
        m = data["memory"]
        cfg = config.memory
        cfg.enabled = m.get("enabled", True)
        cfg.debounce_seconds = m.get("debounce_seconds", 30)
        cfg.max_facts = m.get("max_facts", 100)
        cfg.injection_enabled = m.get("injection_enabled", True)

    # Loop detection
    if "loop_detection" in data:
        ld = data["loop_detection"]
        cfg = config.loop_detection
        cfg.enabled = ld.get("enabled", True)
        cfg.warn_threshold = ld.get("warn_threshold", 3)
        cfg.hard_limit = ld.get("hard_limit", 5)

    # Tool search
    if "tool_search" in data:
        config.tool_search.enabled = data["tool_search"].get("enabled", False)

    # Title
    if "title" in data:
        cfg = config.title
        cfg.enabled = data["title"].get("enabled", True)

    # Tool groups
    if "tool_groups" in data:
        config.tool_groups = data["tool_groups"]

    # Skills path
    if "skills" in data:
        skills_data = data["skills"]
        config.skills.path = skills_data.get("path", "skills")
        config.skills.container_path = skills_data.get("container_path", "/mnt/skills")


def get_config_forge() -> ForgeDeerFlowConfig:
    """Build the unified Forge + DeerFlow configuration."""
    forge_settings = get_forge_settings()
    config = ForgeDeerFlowConfig(forge_settings=forge_settings)

    # Scan for DeerFlow config files
    config_paths = [
        os.environ.get("DEER_FLOW_CONFIG_PATH", ""),
        "config.yaml",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "config.yaml"),
    ]

    loaded = False
    for path in config_paths:
        if path and os.path.exists(path):
            data = load_yaml_config(path)
            if data:
                _load_models(config, data)
                _load_tools(config, data)
                _load_features(config, data)
                loaded = True
                break

    # Default model if none loaded
    if not config.models:
        config.models.append(ModelConfig(
            name="claude-sonnet-4-6",
            display_name="Claude Sonnet 4.6",
            use="langchain_anthropic:ChatAnthropic",
            model="claude-sonnet-4-6",
            api_key="$ANTHROPIC_API_KEY",
            supports_thinking=True,
            supports_vision=True,
        ))

    return config


@lru_cache(maxsize=1)
def get_integration_config() -> ForgeDeerFlowConfig:
    """Get cached integration configuration."""
    return get_config_forge()