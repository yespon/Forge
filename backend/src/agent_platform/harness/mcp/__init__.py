"""MCP (Model Context Protocol) integration for Forge.

Provides both the configuration management API (CRUD) and
the runtime transport layer (stdio/SSE connections, tool discovery).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from agent_platform.harness.mcp.transport import (
    MCPServerConfig,
    get_mcp_tools,
    shutdown_mcp,
)

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server configurations and tool lifecycle.

    Two modes:
    1. Config CRUD: add/remove/enable/disable servers
    2. Runtime: initialize connections, discover tools, manage lifecycle
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_path()
        self._transient_tools: list = []

    def _find_config_path(self) -> str:
        candidates = [
            os.environ.get("EXTENSIONS_CONFIG_PATH", ""),
            "extensions_config.json",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "extensions_config.json"

    # ---- Config CRUD ----

    def _load_raw(self) -> dict:
        path = Path(self.config_path)
        if not path.exists():
            return {"mcpServers": {}}
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"mcpServers": {}}

    def _save_raw(self, data: dict) -> None:
        Path(self.config_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info("Saved MCP config to %s", self.config_path)

    def get_enabled_servers(self) -> list[dict]:
        """Get all enabled MCP server configurations."""
        data = self._load_raw()
        servers = []
        for name, cfg in data.get("mcpServers", {}).items():
            if cfg.get("enabled", True):
                servers.append({"name": name, **cfg})
        return servers

    def add_server(self, name: str, config: MCPServerConfig) -> None:
        data = self._load_raw()
        data.setdefault("mcpServers", {})[name] = {
            "enabled": config.enabled,
            "type": config.transport,
            "command": config.command,
            "args": config.args,
            "env": config.env,
            "url": config.url,
            "headers": config.headers,
        }
        self._save_raw(data)

    def remove_server(self, name: str) -> bool:
        data = self._load_raw()
        if name in data.get("mcpServers", {}):
            del data["mcpServers"][name]
            self._save_raw(data)
            return True
        return False

    def enable_server(self, name: str) -> None:
        data = self._load_raw()
        if name in data.get("mcpServers", {}):
            data["mcpServers"][name]["enabled"] = True
            self._save_raw(data)

    def disable_server(self, name: str) -> None:
        data = self._load_raw()
        if name in data.get("mcpServers", {}):
            data["mcpServers"][name]["enabled"] = False
            self._save_raw(data)

    # ---- Runtime ----

    async def get_runtime_tools(self) -> list:
        """Get tools from all configured MCP servers via runtime connections."""
        tools = await get_mcp_tools(self.config_path)
        return self._transient_tools + tools

    async def initialize_runtime(self) -> None:
        """Initialize all MCP server connections."""
        await get_mcp_tools(self.config_path)
        logger.info("MCP runtime initialized")

    async def shutdown(self) -> None:
        """Shutdown all MCP connections."""
        await shutdown_mcp()
        logger.info("MCP runtime shutdown")

    @property
    def server_count(self) -> int:
        return len(self.get_enabled_servers())


# Global singleton
_manager: Optional[MCPManager] = None


def get_mcp_manager(config_path: Optional[str] = None) -> MCPManager:
    global _manager
    if _manager is None:
        _manager = MCPManager(config_path=config_path)
    return _manager