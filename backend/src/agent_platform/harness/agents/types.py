"""Model configuration types for Forge × DeerFlow integration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SummarizationTriggerType(str, Enum):
    TOKENS = "tokens"
    MESSAGES = "messages"
    FRACTION = "fraction"


class SummarizationKeepType(str, Enum):
    MESSAGES = "messages"
    TOKENS = "tokens"
    FRACTION = "fraction"


@dataclass
class ModelConfig:
    name: str = ""
    display_name: str = ""
    use: str = "langchain_openai:ChatOpenAI"
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 600.0
    max_retries: int = 2
    supports_thinking: bool = False
    supports_vision: bool = False
    supports_reasoning_effort: bool = False
    extra_config: dict = field(default_factory=dict)

    def get_resolved_api_key(self) -> Optional[str]:
        key = self.api_key
        if key.startswith("$"):
            import os
            return os.environ.get(key[1:])
        return key if key else None

    def get_resolved_base_url(self) -> Optional[str]:
        return self.base_url or self.api_base or None


@dataclass
class ToolConfig:
    name: str = ""
    group: str = "default"
    use: str = ""
    config: dict = field(default_factory=dict)


@dataclass
class SummarizationTrigger:
    type: SummarizationTriggerType = SummarizationTriggerType.TOKENS
    value: int = 15564
    def to_tuple(self):
        return (self.type.value, self.value)


@dataclass
class SummarizationKeep:
    type: SummarizationKeepType = SummarizationKeepType.MESSAGES
    value: int = 10
    def to_tuple(self):
        return (self.type.value, self.value)


@dataclass
class SummarizationConfig:
    enabled: bool = True
    model_name: Optional[str] = None
    trigger: Optional[list[SummarizationTrigger]] = None
    keep: SummarizationKeep = field(default_factory=SummarizationKeep)
    trim_tokens_to_summarize: int = 15564
    summary_prompt: Optional[str] = None
    preserve_recent_skill_count: int = 5
    preserve_recent_skill_tokens: int = 25000
    preserve_recent_skill_tokens_per_skill: int = 5000
    skill_file_read_tool_names: list = field(default_factory=lambda: ["read_file", "read", "view", "cat"])


@dataclass
class MemoryConfig:
    enabled: bool = True
    storage_path: str = ".deer-flow/memory.json"
    debounce_seconds: int = 30
    model_name: Optional[str] = None
    max_facts: int = 100
    fact_confidence_threshold: float = 0.7
    injection_enabled: bool = True
    max_injection_tokens: int = 2000


@dataclass
class LoopDetectionConfig:
    enabled: bool = True
    warn_threshold: int = 3
    hard_limit: int = 5
    window_size: int = 20
    max_tracked_threads: int = 100
    tool_freq_warn: int = 30
    tool_freq_hard_limit: int = 50
    tool_freq_overrides: dict = field(default_factory=dict)


@dataclass
class SubAgentConfig:
    timeout_seconds: int = 900
    max_turns: Optional[int] = None
    agents: dict = field(default_factory=dict)
    custom_agents: dict = field(default_factory=dict)


@dataclass
class ToolSearchConfig:
    enabled: bool = False


@dataclass
class TitleConfig:
    enabled: bool = True
    max_words: int = 6
    max_chars: int = 60
    model_name: Optional[str] = None


@dataclass
class TokenUsageConfig:
    enabled: bool = True


@dataclass
class GuardrailsConfig:
    enabled: bool = False
    provider: dict = field(default_factory=dict)


@dataclass
class RunEventsConfig:
    backend: str = "memory"
    max_trace_content: int = 10240
    track_token_usage: bool = True


@dataclass
class ChannelSessionConfig:
    assistant_id: str = "lead_agent"
    config: dict = field(default_factory=lambda: {"recursion_limit": 100})
    context: dict = field(default_factory=lambda: {
        "thinking_enabled": True, "is_plan_mode": False, "subagent_enabled": False,
    })


@dataclass
class ChannelConfig:
    enabled: bool = False
    langgraph_url: str = "http://localhost:8001/api"
    gateway_url: str = "http://localhost:8001"
    session: ChannelSessionConfig = field(default_factory=ChannelSessionConfig)
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_webhook: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
    telegram_bot: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    wechat_bot_token: Optional[str] = None
    wecom_bot_id: Optional[str] = None
    wecom_bot_secret: Optional[str] = None
    dingtalk_client_id: Optional[str] = None
    dingtalk_client_secret: Optional[str] = None
    discord_bot_token: Optional[str] = None
    allowed_users: list = field(default_factory=list)


@dataclass
class SkillConfig:
    path: str = "skills"
    container_path: str = "/mnt/skills"


@dataclass
class DatabaseConfig:
    backend: str = "postgres"
    postgres_url: str = ""
    sqlite_dir: str = ".deer-flow/data"


@dataclass
class AgentSkillConfig:
    name: str = ""
    description: str = ""
    system_prompt: str = ""
    skills: Optional[list[str]] = None
    tools: Optional[list[str]] = None
    model: Optional[str] = None
    max_turns: int = 80
    timeout_seconds: int = 600