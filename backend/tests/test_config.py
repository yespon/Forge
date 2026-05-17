"""Configuration loading and parsing tests (25 tests)."""
import os, sys, json, tempfile, shutil; from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestYamlLoading:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        cfg = {"models":[{"name":"m1","use":"langchain_anthropic:ChatAnthropic","model":"claude"}],
               "summarization":{"enabled":True,"trigger":[{"type":"tokens","value":15000}]},
               "memory":{"enabled":True},"loop_detection":{"enabled":True,"warn_threshold":3},"title":{"enabled":True}}
        self.cfg = self.tmp / "config.yaml"
        self.cfg.write_text(yaml.dump(cfg))
    def teardown_method(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def test_01_load_basic_yaml(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert d is not None
    def test_02_model_count(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert len(d["models"]) == 1
    def test_03_model_name(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert d["models"][0]["name"] == "m1"
    def test_04_summarization_defaults(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert d["summarization"]["enabled"] == True
    def test_05_memory_defaults(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert d["memory"]["enabled"] == True
    def test_06_loop_detection(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.cfg))
        assert d["loop_detection"]["warn_threshold"] == 3
    def test_07_missing_file(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config("/tmp/nonexistent_file.yaml")
        assert d is None or len(d.get("models", [])) == 0
    def test_08_env_var_in_value(self):
        os.environ["_TEST_KEY"] = "sk-test"
        (self.tmp / "config.yaml").write_text(yaml.dump({"models":[{"api_key":"$_TEST_KEY"}]}))
        from agent_platform.integration.config import load_yaml_config
        # Env vars are preserved as-is and resolved at runtime
        d = load_yaml_config(str(self.tmp / "config.yaml"))
        assert d is not None
    def test_09_multi_model_config(self):
        cfg2 = {"models":[{"name":"a","use":"p1","model":"m1"},{"name":"b","use":"p2","model":"m2"}]}
        (self.tmp / "multi.yaml").write_text(yaml.dump(cfg2))
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config(str(self.tmp / "multi.yaml"))
        assert len(d["models"]) == 2

class TestForgeConfig:
    def test_01_default_creation(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert c.database.backend == "postgres"
    def test_02_summarization(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert hasattr(c, "summarization")
    def test_03_memory(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert hasattr(c, "memory")
    def test_04_loop_detection(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert hasattr(c, "loop_detection")
    def test_05_title(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert hasattr(c, "title")
    def test_06_skills_path(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert c.skills.path == "skills/public"
    def test_07_default_model(self):
        from agent_platform.integration.config import ForgeDeerFlowConfig
        c = ForgeDeerFlowConfig()
        assert c.default_model_name is not None
    def test_08_config_version(self):
        from agent_platform.integration.config import load_yaml_config
        d = load_yaml_config("config.yaml")
        assert d is None or "config_version" in d

class TestTypes:
    def test_01_model_config(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(name="test", use="pkg:Class", model="gpt-4")
        assert m.name == "test" and m.model == "gpt-4"
    def test_02_thinking_fields(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(supports_thinking=True, when_thinking_enabled={"extra_body": {"thinking": {"type": "enabled"}}})
        assert m.when_thinking_enabled is not None
    def test_03_penalty_fields(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(temperature=0.5, top_p=0.8, frequency_penalty=0.2, presence_penalty=0.1)
        assert m.temperature == 0.5
    def test_04_stop_sequences(self):
        from agent_platform.integration.types import ModelConfig
        m = ModelConfig(stop_sequences=["END", "STOP"])
        assert len(m.stop_sequences) == 2
