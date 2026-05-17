"""Provider kwargs normalization tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class DummyConfig:
    def __init__(self, **kwargs):
        self.name = kwargs.get('name', 'dummy')
        self.model = kwargs.get('model', 'dummy-model')
        self.max_tokens = kwargs.get('max_tokens', 4096)
        self.timeout = kwargs.get('timeout', 600.0)
        self.max_retries = kwargs.get('max_retries', 2)
        self.temperature = kwargs.get('temperature', 0.7)
        self.top_p = kwargs.get('top_p', 0.9)
        self.frequency_penalty = kwargs.get('frequency_penalty', 0.0)
        self.presence_penalty = kwargs.get('presence_penalty', 0.0)
        self.stop_sequences = kwargs.get('stop_sequences', None)
        self.api_key = kwargs.get('api_key', 'sk-test')
        self.api_base = kwargs.get('api_base', '')
        self.supports_reasoning_effort = kwargs.get('supports_reasoning_effort', False)
        self.supports_thinking = kwargs.get('supports_thinking', False)
        self.thinking_budget_tokens = kwargs.get('thinking_budget_tokens', None)
        self.when_thinking_enabled = kwargs.get('when_thinking_enabled', None)
        self.when_thinking_disabled = kwargs.get('when_thinking_disabled', None)

class TestProviderKwargs:
    def test_001_basic_openai(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(), 'openai', False)
        assert k['model'] == 'dummy-model'
    def test_002_basic_anthropic(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(), 'anthropic', False)
        assert k['max_tokens'] == 4096
    def test_003_google_api_key_renamed(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_key='gkey'), 'google', False)
        assert 'gemini_api_key' in k and 'api_key' not in k
    def test_004_ollama_num_predict(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(max_tokens=111), 'ollama', False)
        assert 'num_predict' in k and 'max_tokens' not in k
    def test_005_api_base_openai(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://x'), 'openai', False)
        assert k['base_url'] == 'http://x'
    def test_006_api_base_vllm(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://vllm'), 'vllm', False)
        assert k['base_url'] == 'http://vllm'
    def test_007_reasoning_effort(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(supports_reasoning_effort=True), 'openai', False)
        assert k.get('reasoning_effort') == 'medium'
    def test_008_no_reasoning_effort_for_google(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(supports_reasoning_effort=True), 'google', False)
        assert 'reasoning_effort' not in k
    def test_009_thinking_enabled(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(supports_thinking=True), 'anthropic', True)
        assert 'thinking' in k
    def test_010_thinking_budget(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(supports_thinking=True, thinking_budget_tokens=999), 'anthropic', True)
        assert k['thinking']['budget_tokens'] == 999
    def test_011_when_enabled(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(supports_thinking=True, when_thinking_enabled={'x': 1}), 'anthropic', True)
        assert k['x'] == 1
    def test_012_when_disabled(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(when_thinking_disabled={'y': 2}), 'openai', False)
        assert k['y'] == 2
    def test_013_stop_sequences(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(stop_sequences=['END']), 'openai', False)
        assert k['stop'] == ['END']
    def test_014_frequency_penalty(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(frequency_penalty=0.5), 'openai', False)
        assert k['frequency_penalty'] == 0.5
    def test_015_presence_penalty(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(presence_penalty=0.6), 'openai', False)
        assert k['presence_penalty'] == 0.6
    def test_016_no_penalty_google(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(frequency_penalty=0.5, presence_penalty=0.6), 'google', False)
        assert 'frequency_penalty' not in k and 'presence_penalty' not in k
    def test_017_temperature(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(temperature=0.11), 'openai', False)
        assert k['temperature'] == 0.11
    def test_018_top_p(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(top_p=0.55), 'openai', False)
        assert k['top_p'] == 0.55
    def test_019_max_retries(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(max_retries=7), 'openai', False)
        assert k['max_retries'] == 7
    def test_020_timeout(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(timeout=12.5), 'openai', False)
        assert k['timeout'] == 12.5
    def test_021_max_tokens(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(max_tokens=222), 'anthropic', False)
        assert k['max_tokens'] == 222
    def test_022_api_key_passed(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_key='secret'), 'anthropic', False)
        assert k['api_key'] == 'secret'
    def test_023_provider_recommendations_shape(self):
        from agent_platform.integration.models import get_provider_recommendations
        r = get_provider_recommendations()
        assert 'best_for' in r['anthropic']
    def test_024_provider_recommendations_model(self):
        from agent_platform.integration.models import get_provider_recommendations
        r = get_provider_recommendations()
        assert 'recommended_model' in r['openai']
    def test_025_provider_recommendations_count(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert len(get_provider_recommendations()) >= 8
    def test_026_minimax_base(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://minimax'), 'minimax', False)
        assert k['base_url'] == 'http://minimax'
    def test_027_grok_base(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://xai'), 'grok', False)
        assert k['base_url'] == 'http://xai'
    def test_028_ollama_base(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://ollama'), 'ollama', False)
        assert k['base_url'] == 'http://ollama'
    def test_029_google_keeps_model(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(model='gemini-2.0'), 'google', False)
        assert k['model'] == 'gemini-2.0'
    def test_030_anthropic_no_base_url(self):
        from agent_platform.integration.models import build_provider_kwargs
        k = build_provider_kwargs(DummyConfig(api_base='http://x'), 'anthropic', False)
        assert 'base_url' not in k
