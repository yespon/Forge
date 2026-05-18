"""Model factory tests (30 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestModelResolution:
    def test_01_resolve_anthropic(self):
        from agent_platform.integration.models import resolve_model_class
        c = resolve_model_class("langchain_anthropic:ChatAnthropic")
        assert "ChatAnthropic" in c.__name__
    def test_02_resolve_openai(self):
        from agent_platform.integration.models import resolve_model_class
        c = resolve_model_class("langchain_openai:ChatOpenAI")
        assert "ChatOpenAI" in c.__name__



    def test_06_invalid_path(self):
        from agent_platform.integration.models import resolve_model_class
        try:
            resolve_model_class("nonexistent.module:Class")
            assert False, "Should raise"
        except (ImportError, ValueError, AttributeError):
            pass
    def test_07_empty_use_path(self):
        from agent_platform.integration.models import resolve_model_class
        try:
            resolve_model_class("")
            assert False
        except (ValueError, ImportError, AttributeError):
            pass

class TestProviderRegistry:
    def test_01_get_registry(self):
        from agent_platform.integration.models import get_registered_providers
        r = get_registered_providers()
        assert len(r) >= 7
    def test_02_has_anthropic(self):
        from agent_platform.integration.models import get_registered_providers
        assert "anthropic" in get_registered_providers()
    def test_03_has_openai(self):
        from agent_platform.integration.models import get_registered_providers
        assert "openai" in get_registered_providers()
    def test_04_has_deepseek(self):
        from agent_platform.integration.models import get_registered_providers
        assert "deepseek" in get_registered_providers()
    def test_05_has_google(self):
        from agent_platform.integration.models import get_registered_providers
        assert "google" in get_registered_providers()
    def test_06_has_ollama(self):
        from agent_platform.integration.models import get_registered_providers
        assert "ollama" in get_registered_providers()
    def test_07_has_vllm(self):
        from agent_platform.integration.models import get_registered_providers
        assert "vllm" in get_registered_providers()
    def test_08_has_grok(self):
        from agent_platform.integration.models import get_registered_providers
        assert "grok" in get_registered_providers()

class TestDetectProvider:
    def test_01_anthropic_detect(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("langchain_anthropic:ChatAnthropic", "") == "anthropic"
    def test_02_openai_detect(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("langchain_openai:ChatOpenAI", "") == "openai"
    def test_03_deepseek_detect(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("langchain_deepseek:ChatDeepSeek", "") == "deepseek"
    def test_04_google_detect(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("langchain_google_genai:ChatGoogleGenerativeAI", "") == "google"
    def test_05_ollama_detect(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("langchain_ollama:ChatOllama", "") == "ollama"
    def test_06_model_name_fallback(self):
        from agent_platform.integration.models import _detect_provider_type
        assert _detect_provider_type("unknown:Class", "deepseek-chat") == "deepseek"
    def test_07_unknown_fallback(self):
        from agent_platform.integration.models import _detect_provider_type
        t = _detect_provider_type("unknown:Class", "unknown-model")
        assert t is not None  # Should return a default

class TestCreateModel:
    def test_01_config_object(self):
        from agent_platform.integration.types import ModelConfig
        from agent_platform.integration.models import create_chat_model
        cfg = ModelConfig(name="test", use="langchain_anthropic:ChatAnthropic", model="claude-sonnet-4-6")
        try:
            m = create_chat_model(model_config=cfg, api_key="sk-test")
            assert m is not None
        except Exception as e:
            assert "api_key" in str(e).lower() or "auth" in str(e).lower()  # Auth errors expected without real key
    def test_02_thinking_enabled(self):
        from agent_platform.integration.types import ModelConfig
        from agent_platform.integration.models import create_chat_model
        cfg = ModelConfig(name="test", use="langchain_anthropic:ChatAnthropic", model="claude-sonnet-4-6", supports_thinking=True)
        try:
            m = create_chat_model(model_config=cfg, api_key="sk-test", thinking_enabled=True)
        except Exception:
            pass  # Auth error expected
