"""Sub-agent system tests (20 tests)."""
import os, sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestSubagentConfigs:
    def test_01_default_general(self):
        from agent_platform.integration.subagent_executor import SubagentConfig
        c = SubagentConfig.default_general_purpose()
        assert c.name == "general-purpose" and c.max_turns == 120
    def test_02_default_bash(self):
        from agent_platform.integration.subagent_executor import SubagentConfig
        c = SubagentConfig.default_bash()
        assert c.name == "bash" and "bash" in c.tools
    def test_03_custom(self):
        from agent_platform.integration.subagent_executor import SubagentConfig
        c = SubagentConfig(name="custom", system_prompt="You are a helper.")
        assert c.max_turns == 80  # Default
    def test_04_full_config(self):
        from agent_platform.integration.subagent_executor import SubagentConfig
        c = SubagentConfig(name="full", description="A full config", system_prompt="Help",
                          skills=["python", "bash"], tools=["bash"], model="gpt-4", max_turns=50, timeout_seconds=300)
        assert c.name == "full" and c.max_turns == 50 and c.timeout_seconds == 300
    def test_05_default_timeout(self):
        from agent_platform.integration.subagent_executor import SubagentConfig
        from agent_platform.integration.subagent_executor import SubagentConfig
        c = SubagentConfig.default_general_purpose()
        assert c.timeout_seconds == 900

class TestSubagentRuntime:
    def test_01_default_runtime(self):
        from agent_platform.integration.subagent_executor import SubagentRuntime
        r = SubagentRuntime()
        assert r.config.name == "general-purpose"
    def test_02_custom_runtime(self):
        from agent_platform.integration.subagent_executor import SubagentRuntime, SubagentConfig
        c = SubagentConfig(name="test", system_prompt="test")
        r = SubagentRuntime(config=c)
        assert r.config.name == "test"
    def test_03_parent_model(self):
        from agent_platform.integration.subagent_executor import SubagentRuntime
        r = SubagentRuntime(parent_model_name="claude-sonnet-4-6")
        assert r.parent_model_name == "claude-sonnet-4-6"
    def test_04_parent_tools(self):
        from agent_platform.integration.subagent_executor import SubagentRuntime
        r = SubagentRuntime(parent_tools=[])
        assert r.parent_tools == []

class TestSubagentFunctions:
    def test_01_run_subagent_exists(self):
        from agent_platform.integration.subagent_executor import run_subagent
        assert callable(run_subagent)
    def test_02_cancel_exists(self):
        from agent_platform.integration.subagent_executor import cancel_background_task
        assert callable(cancel_background_task)
    def test_03_get_result_exists(self):
        from agent_platform.integration.subagent_executor import get_background_result
        assert callable(get_background_result)
    def test_04_status_enum(self):
        from agent_platform.integration.subagent_executor import SubagentStatus
        assert len(SubagentStatus) == 6
        assert SubagentStatus.PENDING.value == "pending"
        assert SubagentStatus.COMPLETED.value == "completed"
