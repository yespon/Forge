"""ACP agent tests (15 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestACPManager:
    def test_01_get_manager(self):
        from agent_platform.integration.acp_agent import ACPAgentManager, get_acp_manager
        m = get_acp_manager()
        assert isinstance(m, ACPAgentManager)
    def test_02_register(self):
        from agent_platform.integration.acp_agent import ACPAgentManager, ACPAgentConfig
        m = ACPAgentManager()
        m.register(ACPAgentConfig(name="test-a", command="echo"))
        assert m.get("test-a") is not None
    def test_03_list(self):
        from agent_platform.integration.acp_agent import ACPAgentManager
        m = ACPAgentManager()
        assert isinstance(m.list_agents(), list)
    def test_04_get_nonexistent(self):
        from agent_platform.integration.acp_agent import ACPAgentManager
        m = ACPAgentManager()
        assert m.get("nonexistent") is None
    def test_05_multiple_registrations(self):
        from agent_platform.integration.acp_agent import ACPAgentManager, ACPAgentConfig
        m = ACPAgentManager()
        m.register(ACPAgentConfig(name="a", command="c1"))
        m.register(ACPAgentConfig(name="b", command="c2"))
        assert len(m.list_agents()) == 2
    def test_06_config_defaults(self):
        from agent_platform.integration.acp_agent import ACPAgentConfig
        c = ACPAgentConfig(name="test")
        assert c.timeout == 600 and c.name == "test"
    def test_07_full_config(self):
        from agent_platform.integration.acp_agent import ACPAgentConfig
        c = ACPAgentConfig(name="f", command="npx", args=["--acp"], timeout=300, api_url="http://localhost")
        assert c.command == "npx" and c.timeout == 300

class TestACPInvoke:
    def test_01_tool_importable(self):
        from agent_platform.integration.acp_agent import invoke_acp_agent_tool
        assert hasattr(invoke_acp_agent_tool, 'invoke')
    def test_02_tool_func(self):
        from agent_platform.integration.acp_agent import invoke_acp_agent_tool
        assert hasattr(invoke_acp_agent_tool, 'func')
    def test_03_tool_name(self):
        from agent_platform.integration.acp_agent import invoke_acp_agent_tool
        assert hasattr(invoke_acp_agent_tool, 'name')
    def test_04_tool_description(self):
        from agent_platform.integration.acp_agent import invoke_acp_agent_tool
        assert hasattr(invoke_acp_agent_tool, 'description')
