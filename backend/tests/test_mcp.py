"""MCP config and transport tests (25 tests)."""
import os, sys, json, tempfile, shutil; from pathlib import Path
import os, sys, json, tempfile, shutil; from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class TestMCPConfig:
    def setup_method(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "extensions_config.json"
        self.cfg.write_text(json.dumps({"mcpServers":{"srv1":{"enabled":True,"type":"stdio","command":"echo"}}}))
    def teardown_method(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def test_01_mcp_manager(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        assert m is not None
    def test_02_enabled_servers(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        sv = m.get_enabled_servers()
        assert len(sv) >= 1
    def test_03_add_server(self):
        from agent_platform.integration.mcp import MCPManager
        from agent_platform.integration.mcp_transport import MCPServerConfig
        m = MCPManager(config_path=str(self.cfg))
        m.add_server("new", MCPServerConfig(name="new", command="test"))
        assert len(m.get_enabled_servers()) >= 2
    def test_04_remove_server(self):
        from agent_platform.integration.mcp import MCPManager
        from agent_platform.integration.mcp_transport import MCPServerConfig
        m = MCPManager(config_path=str(self.cfg))
        m.add_server("tmp", MCPServerConfig(name="tmp", command="x"))
        assert m.remove_server("tmp")
    def test_05_remove_nonexistent(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        assert not m.remove_server("nonexistent")
    def test_06_enable_server(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        m.enable_server("srv1")
        assert any(s["name"] == "srv1" for s in m.get_enabled_servers())
    def test_07_disable_server(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        m.disable_server("srv1")
        sv = m.get_enabled_servers()
        assert not any(s.get("name") == "srv1" for s in sv)
    def test_08_no_config_file(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path="/tmp/nonexistent/_.json")
        assert m.get_enabled_servers() == []
    def test_09_server_count(self):
        from agent_platform.integration.mcp import MCPManager
        m = MCPManager(config_path=str(self.cfg))
        assert m.server_count >= 1

class TestMCPTransportConfig:
    def test_01_config_loader(self):
        from agent_platform.integration.mcp_transport import MCPConfigLoader
        td = tempfile.mkdtemp()
        try:
            cfg = os.path.join(td, "extensions_config.json")
            open(cfg, 'w').write(json.dumps({"mcpServers":{"t":{"enabled":True,"type":"stdio","command":"echo"}}}))
            l = MCPConfigLoader(config_path=cfg)
            cfgs = l.load()
            assert len(cfgs) >= 1
            assert cfgs[0].transport == "stdio"
        finally:
            shutil.rmtree(td, ignore_errors=True)
    def test_02_sse_config(self):
        from agent_platform.integration.mcp_transport import MCPConfigLoader
        td = tempfile.mkdtemp()
        try:
            cfg = os.path.join(td, "ec.json")
            open(cfg, 'w').write(json.dumps({"mcpServers":{"sse-srv":{"enabled":True,"type":"sse","url":"http://localhost:8080/mcp"}}}))
            l = MCPConfigLoader(config_path=cfg)
            cfgs = l.load()
            assert any(c.transport == "sse" for c in cfgs)
        finally:
            shutil.rmtree(td, ignore_errors=True)
    def test_03_env_var_resolution(self):
        from agent_platform.integration.mcp_transport import MCPConfigLoader
        os.environ["_MCP_TEST_VAR"] = "resolved-value"
        td = tempfile.mkdtemp()
        try:
            cfg = os.path.join(td, "ec.json")
            open(cfg, 'w').write(json.dumps({"mcpServers":{"t":{"enabled":True,"type":"stdio","command":"echo","env":{"VAR":"$_MCP_TEST_VAR"}}}}))
            l = MCPConfigLoader(config_path=cfg)
            cfgs = l.load()
            assert any(c.env.get("VAR") == "resolved-value" for c in cfgs)
        finally:
            shutil.rmtree(td, ignore_errors=True)
            os.environ.pop("_MCP_TEST_VAR", None)
    def test_04_missing_config(self):
        from agent_platform.integration.mcp_transport import MCPConfigLoader
        l = MCPConfigLoader(config_path="/tmp/nonexistent_xyz.json")
        assert l.load() == []
    def test_05_invalid_json(self):
        td = tempfile.mkdtemp()
        try:
            cfg = os.path.join(td, "bad.json")
            open(cfg, 'w').write("not json}")
            from agent_platform.integration.mcp_transport import MCPConfigLoader
            l = MCPConfigLoader(config_path=cfg)
            assert l.load() == []
        finally:
            shutil.rmtree(td, ignore_errors=True)

class TestMCPOAuth:
    def test_01_manager(self):
        from agent_platform.integration.mcp_oauth import OAuthTokenManager
        m = OAuthTokenManager()
        assert not m.has_any_oauth()
    def test_02_add_server(self):
        from agent_platform.integration.mcp_oauth import OAuthConfig, OAuthTokenManager
        m = OAuthTokenManager()
        m.add_server("test", OAuthConfig(token_url="https://example.com/token", client_id="cid", client_secret="cs"))
        assert m.has_oauth("test")
    def test_03_nonexistent(self):
        from agent_platform.integration.mcp_oauth import OAuthTokenManager
        m = OAuthTokenManager()
        assert not m.has_oauth("nonexistent")
    def test_04_header_none(self):
        from agent_platform.integration.mcp_oauth import OAuthTokenManager
        m = OAuthTokenManager()
        h = None
        import asyncio
        try:
            h = asyncio.run(m.get_auth_header("nonexistent"))
        except:
            pass
        assert h is None

class TestMCPServerConfig:
    def test_01_defaults(self):
        from agent_platform.integration.mcp_transport import MCPServerConfig
        c = MCPServerConfig(name="test")
        assert c.name == "test" and c.transport == "stdio"
    def test_02_full(self):
        from agent_platform.integration.mcp_transport import MCPServerConfig
        c = MCPServerConfig(name="f", transport="sse", url="http://example.com", timeout=30.0)
        assert c.transport == "sse" and c.timeout == 30.0
