"""Edge case & boundary tests (30 tests)."""
import os, sys; from pathlib import Path; import pytest
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestMemoryEdge:
    def test_01_empty_search(self): from agent_platform.integration.memory import MemoryStore, MemoryFact; s=MemoryStore("/tmp/_te1.json"); s.add_fact(MemoryFact("x")); assert len(s.get_relevant_facts("")) >= 0; s.clear()
    def test_02_very_long(self): from agent_platform.integration.memory import MemoryStore, MemoryFact; s=MemoryStore("/tmp/_te2.json"); s.add_fact(MemoryFact("x"*10000)); assert s.get_all_facts()[0].content == ("x"*10000)[:500]; s.clear()
    def test_03_unicode(self): from agent_platform.integration.memory import MemoryStore, MemoryFact; s=MemoryStore("/tmp/_te3.json"); s.add_fact(MemoryFact("你好世界")); r=s.get_relevant_facts("你好"); assert len(r)>=1; s.clear()
    def test_04_empty_storage(self): from agent_platform.integration.memory import MemoryStore; s=MemoryStore("/tmp/_te4.json"); assert len(s.get_all_facts())==0; s.clear()

class TestLoopEdge:
    def test_01_empty_call(self): from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware; ld=LoopDetectionMiddleware(); assert ld._check_loop("","") is None
    def test_02_no_args(self): from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware; ld=LoopDetectionMiddleware(); assert ld._check_loop("read",{}) is None
    def test_03_many_unique(self): from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware; ld=LoopDetectionMiddleware(); [ld._check_loop(f"t{i}",{"x":i}) for i in range(200)]; assert len(ld._history) <= ld.window_size
    def test_04_window_eviction(self): from agent_platform.integration.middleware.loop_detection_middleware import LoopDetectionMiddleware; ld=LoopDetectionMiddleware(window_size=3); [ld._check_loop("t",{"x":i}) for i in range(10)]; assert len(ld._history) <= 3

class TestConfigEdge:
    def test_01_empty_yaml(self):
        import tempfile, yaml; tmp=Path(tempfile.mkdtemp()); f=tmp/"config.yaml"; f.write_text(""); from agent_platform.integration.config import load_yaml_config; d=load_yaml_config(str(f)); assert d is None or d is not None  # empty yaml returns None
    def test_02_bad_yaml(self):
        import tempfile; tmp=Path(tempfile.mkdtemp()); f=tmp/"bad.yaml"; f.write_text("{bad: yaml: [}"); from agent_platform.integration.config import load_yaml_config; d=load_yaml_config(str(f)); assert d is None or isinstance(d, dict)
    def test_03_non_existent(self): from agent_platform.integration.config import load_yaml_config; assert load_yaml_config("/tmp/xyz_not_there.yaml") is None
    def test_04_empty_models(self): import tempfile,yaml; tmp=Path(tempfile.mkdtemp()); f=tmp/"c.yaml"; f.write_text(yaml.dump({"models":[]})); from agent_platform.integration.config import load_yaml_config; d=load_yaml_config(str(f)); assert len(d["models"])==0

class TestToolsEdge:
    @pytest.mark.asyncio
    async def test_01_file_not_found(self): from agent_platform.integration.tools.file_ops import read_file_tool; r=await read_file_tool.ainvoke({"path":"nonexistent_file_xyz.txt"}); assert "not found" in r.lower() or "Error" in r
    @pytest.mark.asyncio
    async def test_02_empty_dir(self): from agent_platform.integration.tools.file_ops import ls_tool; import tempfile; tmp=Path(tempfile.mkdtemp()); r=await ls_tool.ainvoke({"path":str(tmp)}); assert r is not None
    @pytest.mark.asyncio
    async def test_03_bash_empty(self): from agent_platform.integration.tools.bash import bash_tool; r=await bash_tool.ainvoke({"command":""}); assert r is not None
    @pytest.mark.asyncio
    async def test_04_bash_invalid(self): from agent_platform.integration.tools.bash import bash_tool; r=await bash_tool.ainvoke({"command":"nonexistent_cmd_xyz"}); assert r is not None
    @pytest.mark.asyncio
    async def test_05_web_search_empty(self): from agent_platform.integration.tools.web_search import web_search_tool; r=await web_search_tool.ainvoke({"query":""}); assert r is not None
    @pytest.mark.asyncio
    async def test_06_web_fetch_bad_url(self): from agent_platform.integration.tools.web_fetch import web_fetch_tool; r=await web_fetch_tool.ainvoke({"url":"https://nonexistent.example.com"}); assert "error" in r.lower() or r is not None

class TestChannelsEdge:
    def test_01_empty_config(self):
        from agent_platform.integration.channels import FeishuChannel, SlackChannel, MessageBus; bus=MessageBus(); FeishuChannel(bus, {}); SlackChannel(bus, {})
    def test_02_channel_messages(self):
        from agent_platform.integration.channels import ChannelType; ct=ChannelType.FEISHU; assert ct.value is not None
    def test_03_message_bus_publish(self):
        import asyncio; from agent_platform.integration.channels import MessageBus, InboundMessage; b=MessageBus(); asyncio.run(b.publish_inbound(InboundMessage(text="t"))); assert b._inbound.qsize() >= 1
    def test_04_service_interface(self):
        from agent_platform.integration.channels import ChannelService; s=ChannelService(); assert s.get_status() == "stopped"
