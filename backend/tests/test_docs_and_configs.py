"""Documentation, model config, and provider recommendation tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

ROOT = Path(__file__).parent.parent.parent  # project root (Forge/)

class TestDocsSite:
    def test_001_website_exists(self): assert (ROOT / "website").exists()
    def test_002_package_json_exists(self): assert (ROOT / "website/package.json").exists()
    def test_003_config_exists(self): assert (ROOT / "website/docusaurus.config.ts").exists()
    def test_004_sidebars_exists(self): assert (ROOT / "website/sidebars.ts").exists()
    def test_005_homepage_exists(self): assert (ROOT / "website/src/pages/index.tsx").exists()
    def test_006_docs_index_exists(self): assert (ROOT / "website/docs/index.md").exists()
    def test_007_architecture_doc_imported(self): assert (ROOT / "website/docs/architecture.md").exists()
    def test_008_roadmap_doc_imported(self): assert (ROOT / "website/docs/roadmap.md").exists()
    def test_009_model_configs_doc_imported(self): assert (ROOT / "website/docs/model-configs.md").exists()
    def test_010_docs_readme_exists(self): assert (ROOT / "website/README.md").exists()
    def test_011_api_overview_exists(self): assert (ROOT / "website/docs/api/overview.md").exists()
    def test_012_api_models_exists(self): assert (ROOT / "website/docs/api/models.md").exists()
    def test_013_api_approvals_exists(self): assert (ROOT / "website/docs/api/approvals.md").exists()
    def test_014_api_tasks_exists(self): assert (ROOT / "website/docs/api/tasks.md").exists()
    def test_015_deployment_doc_exists(self): assert (ROOT / "website/docs/deployment/docker.md").exists()
    def test_016_custom_css_exists(self): assert (ROOT / "website/src/css/custom.css").exists()
    def test_017_static_img_dir_exists(self): assert (ROOT / "website/static/img").exists()
    def test_018_favicon_exists(self): assert (ROOT / "website/static/img/favicon.ico").exists()

class TestModelRecommendations:
    def test_019_recommendations_import(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert callable(get_provider_recommendations)
    def test_020_registry_import(self):
        from agent_platform.integration.models import get_registered_providers
        assert callable(get_registered_providers)
    def test_021_recommendations_not_empty(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert len(get_provider_recommendations()) >= 5
    def test_022_registry_not_empty(self):
        from agent_platform.integration.models import get_registered_providers
        assert len(get_registered_providers()) >= 7
    def test_023_anthropic_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "anthropic" in get_provider_recommendations()
    def test_024_openai_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "openai" in get_provider_recommendations()
    def test_025_deepseek_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "deepseek" in get_provider_recommendations()
    def test_026_google_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "google" in get_provider_recommendations()
    def test_027_ollama_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "ollama" in get_provider_recommendations()
    def test_028_vllm_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "vllm" in get_provider_recommendations()
    def test_029_grok_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "grok" in get_provider_recommendations()
    def test_030_minimax_recommendation(self):
        from agent_platform.integration.models import get_provider_recommendations
        assert "minimax" in get_provider_recommendations()

class TestModelConfigDoc:
    def test_031_model_configs_exists(self): assert Path("MODEL_CONFIGS.md").exists()
    def test_032_model_configs_has_matrix(self): assert "Provider Capability Matrix" in Path("MODEL_CONFIGS.md").read_text()
    def test_033_model_configs_has_guidance(self): assert "Tuning Guidance" in Path("MODEL_CONFIGS.md").read_text()
    def test_034_model_configs_mentions_anthropic(self): assert "Anthropic" in Path("MODEL_CONFIGS.md").read_text()
    def test_035_model_configs_mentions_openai(self): assert "OpenAI" in Path("MODEL_CONFIGS.md").read_text()
    def test_036_model_configs_mentions_deepseek(self): assert "DeepSeek" in Path("MODEL_CONFIGS.md").read_text()
    def test_037_model_configs_mentions_google(self): assert "Google" in Path("MODEL_CONFIGS.md").read_text()
    def test_038_model_configs_mentions_ollama(self): assert "Ollama" in Path("MODEL_CONFIGS.md").read_text()
    def test_039_model_configs_mentions_vllm(self): assert "vLLM" in Path("MODEL_CONFIGS.md").read_text()
    def test_040_model_configs_mentions_grok(self): assert "Grok" in Path("MODEL_CONFIGS.md").read_text()
    def test_041_model_configs_mentions_minimax(self): assert ("MiniMax" in Path("MODEL_CONFIGS.md").read_text()) or ("minimax" in Path("MODEL_CONFIGS.md").read_text())

class TestTypeFields:
    def test_042_model_config_has_when_thinking_enabled(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(when_thinking_enabled={"x": 1})
        assert m.when_thinking_enabled == {"x": 1}
    def test_043_model_config_has_when_thinking_disabled(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(when_thinking_disabled={"y": 2})
        assert m.when_thinking_disabled == {"y": 2}
    def test_044_model_config_has_budget(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(thinking_budget_tokens=1234)
        assert m.thinking_budget_tokens == 1234
    def test_045_model_config_has_temperature(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(temperature=0.25)
        assert m.temperature == 0.25
    def test_046_model_config_has_top_p(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(top_p=0.8)
        assert m.top_p == 0.8
    def test_047_model_config_has_frequency_penalty(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(frequency_penalty=0.1)
        assert m.frequency_penalty == 0.1
    def test_048_model_config_has_presence_penalty(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(presence_penalty=0.2)
        assert m.presence_penalty == 0.2
    def test_049_model_config_has_stop_sequences(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(stop_sequences=["END"])
        assert m.stop_sequences == ["END"]
    def test_050_model_config_defaults_still_work(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig()
        assert m.max_tokens == 4096
