"""Multi-provider model factory adapted from DeerFlow for Forge.

Supports OpenAI, Anthropic, DeepSeek, Google, Ollama, and custom providers.
Handles thinking mode toggling and API key resolution.
"""

import importlib
import logging
import os
import re
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel

from agent_platform.harness.agents.types import ModelConfig

logger = logging.getLogger(__name__)


def resolve_env_value(value: str) -> str:
    """Resolve $VAR or ${VAR} environment variable references in a string."""
    if not isinstance(value, str):
        return value

    def _replace(match):
        var_name = match.group(1) or match.group(2)
        return os.environ.get(var_name, "")

    return re.sub(r'\$(\w+)|(?<!\\)\$\{(\w+)\}', _replace, value)


def resolve_model_class(use_path: str) -> type:
    """Resolve a dotted class path like 'langchain_openai:ChatOpenAI' to the class.

    Supports both:
    - module:ClassName format
    - module.sub:ClassName format
    """
    if ":" in use_path:
        module_path, class_name = use_path.split(":", 1)
    elif "." in use_path:
        parts = use_path.rsplit(".", 1)
        module_path, class_name = parts[0], parts[1]
    else:
        raise ValueError(f"Invalid use path: {use_path}")

    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Failed to resolve '{use_path}': {e}")


def create_chat_model(
    model_config: ModelConfig,
    thinking_enabled: bool = True,
    reasoning_effort: Optional[str] = None,
    app_config: Optional[Any] = None,
) -> BaseChatModel:
    """Create a LangChain chat model from a ModelConfig.

    Supports multiple providers with provider-specific parameter handling.

    Args:
        model_config: Model configuration
        thinking_enabled: Enable thinking/reasoning mode
        reasoning_effort: Reasoning effort level (for supported models)
        app_config: Application configuration

    Returns:
        Configured BaseChatModel instance
    """
    use_path = model_config.use
    model_name = model_config.model or model_config.name
    api_key = resolve_env_value(model_config.api_key) if model_config.api_key else None
    base_url = resolve_env_value(model_config.base_url or model_config.api_base) if (model_config.base_url or model_config.api_base) else None

    # Build kwargs
    kwargs: dict[str, Any] = {
        "model": model_name,
    }

    # API key
    if api_key:
        kwargs["api_key"] = api_key

    # Base URL (provider-dependent parameter name)
    if base_url:
        kwargs["base_url"] = base_url

    # Common params
    if model_config.max_tokens:
        kwargs["max_tokens"] = model_config.max_tokens
    if model_config.temperature is not None:
        kwargs["temperature"] = model_config.temperature
    if model_config.timeout:
        # Different providers use different timeout param names
        kwargs["timeout"] = model_config.timeout
        kwargs["request_timeout"] = model_config.timeout
        kwargs["default_request_timeout"] = model_config.timeout

    if model_config.max_retries:
        kwargs["max_retries"] = model_config.max_retries

    # Provider-specific handling
    provider_type = _detect_provider_type(use_path, model_name)

    if provider_type == "anthropic":
        if thinking_enabled and model_config.supports_thinking:
            kwargs["thinking"] = {"type": "enabled"}
        else:
            kwargs["thinking"] = {"type": "disabled"}

    elif provider_type == "openai":
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

        # Apply extra_body for thinking toggle
        if thinking_enabled and model_config.supports_thinking:
            extra = model_config.extra_config.get("when_thinking_enabled", {}).get("extra_body", {})
            if extra:
                kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **extra}
        else:
            extra = model_config.extra_config.get("when_thinking_disabled", {}).get("extra_body", {})
            if extra:
                kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **extra}

    elif provider_type == "deepseek":
        if thinking_enabled and model_config.supports_thinking:
            extra = model_config.extra_config.get("when_thinking_enabled", {}).get("extra_body", {})
            if extra:
                kwargs["extra_body"] = {**kwargs.get("extra_body", {}), **extra}

    elif provider_type == "google":
        # Google uses gemini_api_key instead of api_key
        if api_key:
            kwargs["gemini_api_key"] = api_key
            kwargs.pop("api_key", None)

    elif provider_type == "ollama":
        # Ollama uses num_predict instead of max_tokens
        if "max_tokens" in kwargs:
            kwargs["num_predict"] = kwargs.pop("max_tokens")

    # Resolve the class
    try:
        model_class = resolve_model_class(use_path)
        instance = model_class(**kwargs)
        logger.info(f"Created model '{model_name}' via {use_path} (thinking={thinking_enabled})")
        return instance
    except Exception as e:
        logger.error(f"Failed to create model '{model_name}' via {use_path}: {e}")
        raise


# Provider registry for extensible model creation
_PROVIDER_REGISTRY = {
    "openai": "langchain_openai:ChatOpenAI",
    "anthropic": "langchain_anthropic:ChatAnthropic",
    "deepseek": "langchain_deepseek:ChatDeepSeek",
    "google": "langchain_google_genai:ChatGoogleGenerativeAI",
    "ollama": "langchain_ollama:ChatOllama",
    "vllm": "langchain_openai:ChatOpenAI",  # OpenAI-compatible
    "grok": "langchain_openai:ChatOpenAI",   # xAI API
    "minimax": "langchain_openai:ChatOpenAI",  # OpenAI-compatible
}


def get_registered_providers() -> dict:
    """Get all registered providers."""
    return dict(_PROVIDER_REGISTRY)


def _detect_provider_type(use_path: str, model_name: str) -> str:
    """Detect LLM provider type from use path or model name."""
    use_lower = use_path.lower()
    name_lower = model_name.lower()

    if "anthropic" in use_lower:
        return "anthropic"
    if "openai" in use_lower and "google" not in use_lower:
        return "openai"
    if "deepseek" in use_lower or "deepseek" in name_lower:
        return "deepseek"
    if "google" in use_lower:
        return "google"
    if "ollama" in use_lower:
        return "ollama"

    # Fall back based on model name patterns
    if any(x in name_lower for x in ["claude"]):
        return "anthropic"
    if any(x in name_lower for x in ["gpt", "o1", "o3"]):
        return "openai"
    if any(x in name_lower for x in ["gemini"]):
        return "google"
    if any(x in name_lower for x in ["deepseek"]):
        return "deepseek"

    return "openai"


def build_provider_kwargs(model_config, provider_type: str, thinking_enabled: bool = False) -> dict:
    """Normalize provider-specific kwargs from ModelConfig."""
    kwargs = {
        "model": model_config.model,
        "max_tokens": model_config.max_tokens or 4096,
        "timeout": model_config.timeout or 600.0,
        "max_retries": model_config.max_retries or 2,
        "temperature": model_config.temperature,
        "top_p": model_config.top_p,
    }

    if getattr(model_config, 'stop_sequences', None):
        kwargs["stop"] = model_config.stop_sequences

    if provider_type not in {"google", "ollama"}:
        if getattr(model_config, 'frequency_penalty', 0.0):
            kwargs["frequency_penalty"] = model_config.frequency_penalty
        if getattr(model_config, 'presence_penalty', 0.0):
            kwargs["presence_penalty"] = model_config.presence_penalty

    if getattr(model_config, 'api_key', None):
        kwargs["api_key"] = model_config.api_key

    if provider_type == "google" and "api_key" in kwargs:
        kwargs["gemini_api_key"] = kwargs.pop("api_key")
    if provider_type == "ollama":
        if "max_tokens" in kwargs:
            kwargs["num_predict"] = kwargs.pop("max_tokens")
        if getattr(model_config, 'api_base', None):
            kwargs["base_url"] = model_config.api_base
    if provider_type in {"openai", "vllm", "grok", "minimax"} and getattr(model_config, 'api_base', None):
        kwargs["base_url"] = model_config.api_base

    if getattr(model_config, 'supports_reasoning_effort', False) and provider_type in {"openai", "grok", "minimax"}:
        kwargs.setdefault("reasoning_effort", "medium")

    if getattr(model_config, 'supports_thinking', False) and thinking_enabled:
        kwargs["thinking"] = {"type": "enabled"}
        if getattr(model_config, 'thinking_budget_tokens', None):
            kwargs["thinking"]["budget_tokens"] = model_config.thinking_budget_tokens
        if getattr(model_config, 'when_thinking_enabled', None):
            for k, v in model_config.when_thinking_enabled.items():
                kwargs.setdefault(k, v)
    elif getattr(model_config, 'when_thinking_disabled', None):
        for k, v in model_config.when_thinking_disabled.items():
            kwargs.setdefault(k, v)

    return kwargs


def get_provider_recommendations() -> dict:
    """Return opinionated provider presets for UI / docs / config generation."""
    return {
        "anthropic": {"best_for": ["general", "coding", "reasoning"], "recommended_model": "claude-sonnet-4-6"},
        "openai": {"best_for": ["vision", "structured_output", "reasoning"], "recommended_model": "gpt-4o"},
        "deepseek": {"best_for": ["chinese", "cost_effective"], "recommended_model": "deepseek-chat"},
        "google": {"best_for": ["multimodal", "speed"], "recommended_model": "gemini-2.0-flash-exp"},
        "ollama": {"best_for": ["local", "privacy"], "recommended_model": "llama3"},
        "vllm": {"best_for": ["self_hosted", "scale"], "recommended_model": "meta-llama/Meta-Llama-3-8B-Instruct"},
        "grok": {"best_for": ["reasoning", "openai_compatible"], "recommended_model": "grok-2"},
        "minimax": {"best_for": ["multilingual", "openai_compatible"], "recommended_model": "abab6.5-chat"},
    }
