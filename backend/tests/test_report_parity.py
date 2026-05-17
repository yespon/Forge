"""Final parity / capability report sanity tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestParity:
    def test_001_architecture_exists(self): assert Path('ARCHITECTURE.md').exists()
    def test_002_roadmap_exists(self): assert Path('ROADMAP.md').exists()
    def test_003_model_configs_exists(self): assert Path('MODEL_CONFIGS.md').exists()
    def test_004_docs_site_exists(self): assert Path('website').exists()
    def test_005_i18n_exists(self): assert Path('frontend/src/i18n/index.ts').exists()
    def test_006_skills_count(self): assert len(list(Path('skills/public').glob('*/SKILL.md'))) >= 21
    def test_007_test_file_count(self): assert len(list(Path('backend/tests').glob('*.py'))) >= 15
    def test_008_provider_count(self):
        from agent_platform.integration.models import get_registered_providers
        assert len(get_registered_providers()) >= 8
    def test_009_channels_type_count(self):
        from agent_platform.integration.channels import ChannelType
        assert len(ChannelType) >= 7
    def test_010_middleware_builder_exists(self):
        from agent_platform.integration.middleware_module import build_forge_middleware_chain
        assert callable(build_forge_middleware_chain)
    def test_011_custom_agent_loader_exists(self):
        from agent_platform.integration.tools.setup_agent_tool import load_custom_agent
        assert callable(load_custom_agent)
    def test_012_oauth_manager_exists(self):
        from agent_platform.integration.mcp_oauth import OAuthTokenManager
        assert OAuthTokenManager is not None
    def test_013_acp_manager_exists(self):
        from agent_platform.integration.acp_agent import ACPAgentManager
        assert ACPAgentManager is not None
    def test_014_memory_manager_exists(self):
        from agent_platform.integration.memory import MemoryManager
        assert MemoryManager is not None
    def test_015_doc_site_package(self):
        assert 'docusaurus' in Path('website/package.json').read_text().lower()
