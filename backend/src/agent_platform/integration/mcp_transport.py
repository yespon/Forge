"""MCP transport layer using the mcp library directly.

Provides stdio and SSE transport for connecting to MCP servers,
discovering tools, and calling them.

Architecture:
  MCPTransportManager
    ├── StdioTransport  (subprocess stdin/stdout)
    └── SSETransport    (HTTP SSE connection)
          ↓
    ServerSession (mcp.client.session.ClientSession)
          ↓
    list_tools() / call_tool()
          ↓
    LangChain BaseTool wrapper
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool, tool

logger = logging.getLogger(__name__)


# ============================================================================
# Data Types
# ============================================================================


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""
    name: str
    enabled: bool = True
    transport: str = "stdio"  # stdio or sse
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""  # For SSE
    headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 300.0


@dataclass
class MCPToolDef:
    """A tool discovered from an MCP server."""
    name: str
    description: str = ""
    input_schema: dict = field(default_factory=dict)
    server_name: str = ""


# ============================================================================
# Config Loader
# ============================================================================


class MCPConfigLoader:
    """Loads MCP server configurations from extensions_config.json."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config()

    def _find_config(self) -> str:
        candidates = [
            os.environ.get("EXTENSIONS_CONFIG_PATH", ""),
            "extensions_config.json",
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "extensions_config.json"),
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        return "extensions_config.json"

    def load(self) -> list[MCPServerConfig]:
        """Load all enabled MCP server configs."""
        path = Path(self.config_path)
        if not path.exists():
            logger.info("No MCP config at %s", self.config_path)
            return []

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load MCP config: %s", e)
            return []

        servers = []
        for name, cfg in data.get("mcpServers", {}).items():
            if not cfg.get("enabled", True):
                continue

            # Resolve $ENV_VAR in env values
            resolved_env = {}
            for k, v in cfg.get("env", {}).items():
                if isinstance(v, str) and v.startswith("$"):
                    resolved_env[k] = os.environ.get(v[1:], "")
                else:
                    resolved_env[k] = v

            server = MCPServerConfig(
                name=name,
                enabled=cfg.get("enabled", True),
                transport=cfg.get("type", "stdio"),
                command=cfg.get("command", ""),
                args=cfg.get("args", []),
                env=resolved_env,
                url=cfg.get("url", ""),
                headers=cfg.get("headers", {}),
                timeout=cfg.get("timeout", 300.0),
            )
            servers.append(server)

        logger.info("Loaded %d MCP server configs", len(servers))
        return servers


# ============================================================================
# Transport Implementations
# ============================================================================


class StdioTransport:
    """Manages an MCP server subprocess with stdio transport."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._session: Optional[Any] = None

    async def connect(self) -> Any:
        """Start the subprocess and create an MCP client session.

        Returns:
            ClientSession instance
        """
        import anyio
        from mcp.client.session import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters

        params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=self.config.env or None,
        )

        logger.info("Connecting to MCP server '%s' via stdio: %s %s",
                     self.config.name, self.config.command, " ".join(self.config.args))

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    logger.info("Connected to MCP server '%s'", self.config.name)
                    return session
        except Exception as e:
            logger.error("Failed to connect to MCP server '%s': %s", self.config.name, e)
            raise

    async def disconnect(self):
        """Disconnect from the server."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception as e:
                logger.warning("Error terminating MCP process %s: %e", self.config.name, e)
            self._process = None
        self._session = None

    @property
    def session(self) -> Optional[Any]:
        return self._session


class SSETransport:
    """Manages an MCP server connection via SSE transport."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._session: Optional[Any] = None

    async def connect(self) -> Any:
        """Connect to an SSE MCP server.

        Returns:
            ClientSession instance
        """
        import anyio
        from mcp.client.session import ClientSession
        from mcp.client.sse import sse_client

        logger.info("Connecting to MCP server '%s' via SSE: %s",
                     self.config.name, self.config.url)

        try:
            headers = self.config.headers or {}
            async with sse_client(self.config.url, headers=headers,
                                  timeout=self.config.timeout) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    logger.info("Connected to MCP server '%s' via SSE", self.config.name)
                    return session
        except Exception as e:
            logger.error("Failed to connect to MCP server '%s' via SSE: %s",
                         self.config.name, e)
            raise

    async def disconnect(self):
        self._session = None

    @property
    def session(self) -> Optional[Any]:
        return self._session


# ============================================================================
# Tool Discovery & Wrapping
# ============================================================================


async def discover_tools(session: Any, server_name: str) -> list[MCPToolDef]:
    """Discover tools from an MCP server session.

    Args:
        session: MCP ClientSession instance
        server_name: Server name for tool naming

    Returns:
        List of discovered tool definitions
    """
    try:
        result = await session.list_tools()
        tools = []
        for t in result.tools:
            tool_def = MCPToolDef(
                name=f"{server_name}_{t.name}",
                description=t.description or "",
                input_schema=t.inputSchema if hasattr(t, "inputSchema") else {},
                server_name=server_name,
            )
            tools.append(tool_def)
        logger.info("Discovered %d tools from server '%s'", len(tools), server_name)
        return tools
    except Exception as e:
        logger.warning("Failed to discover tools from '%s': %s", server_name, e)
        return []


def wrap_mcp_tool(tool_def: MCPToolDef, session: Any) -> BaseTool:
    """Wrap an MCP tool definition as a LangChain StructuredTool.

    Args:
        tool_def: Tool definition from MCP server
        session: MCP ClientSession to call the tool through

    Returns:
        LangChain StructuredTool
    """
    async def _call_tool(**kwargs) -> str:
        """Call the MCP tool and return results."""
        try:
            result = await session.call_tool(tool_def.name.split("_", 1)[1], arguments=kwargs)
            # Format the result
            parts = []
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    parts.append(content_item.text)
                elif hasattr(content_item, "data"):
                    parts.append(f"[Binary data: {len(content_item.data)} bytes]")
                elif hasattr(content_item, "type"):
                    parts.append(f"[Content type: {content_item.type}]")
            return "\n".join(parts)
        except Exception as e:
            return f"MCP tool error: {e}"

    return StructuredTool.from_function(
        func=_call_tool,
        name=tool_def.name,
        description=tool_def.description,
        args_schema=None,  # LangChain will infer from the signature
    )


# ============================================================================
# Manager
# ============================================================================


class MCPTransportManager:
    """Manages all MCP server connections and tool discovery."""

    def __init__(self, config_path: Optional[str] = None):
        self.config_loader = MCPConfigLoader(config_path)
        self._servers: dict[str, Any] = {}  # name -> transport
        self._sessions: dict[str, Any] = {}  # name -> session
        self._tools: list[MCPToolDef] = []
        self._langchain_tools: list[BaseTool] = []
        self._config_mtime: Optional[float] = None
        self._initialized = False

    async def initialize(self) -> list[BaseTool]:
        """Initialize all MCP server connections and discover tools.

        Returns:
            List of LangChain tools from all servers
        """
        configs = self.config_loader.load()
        if not configs:
            self._initialized = True
            return []

        self._record_config_mtime()

        for config in configs:
            try:
                if config.transport == "stdio":
                    transport = StdioTransport(config)
                elif config.transport == "sse":
                    transport = SSETransport(config)
                else:
                    logger.warning("Unsupported MCP transport '%s' for server '%s'",
                                   config.transport, config.name)
                    continue

                session = await transport.connect()
                self._servers[config.name] = transport
                # We can't store sessions directly since they close with the context manager
                # So we discover tools immediately
                tools = await discover_tools(session, config.name)
                self._tools.extend(tools)

                for td in tools:
                    lt = wrap_mcp_tool(td, session)
                    self._langchain_tools.append(lt)

                logger.info("Initialized MCP server '%s': %d tools",
                            config.name, len(tools))

            except Exception as e:
                logger.error("Failed to initialize MCP server '%s': %s", config.name, e)

        self._initialized = True
        logger.info("MCP initialized: %d tools from %d servers",
                     len(self._langchain_tools), len(configs))
        return self._langchain_tools

    def _record_config_mtime(self):
        path = Path(self.config_loader.config_path)
        if path.exists():
            self._config_mtime = os.path.getmtime(path)

    def _is_stale(self) -> bool:
        path = Path(self.config_loader.config_path)
        if path.exists() and self._config_mtime is not None:
            return os.path.getmtime(path) > self._config_mtime
        return False

    async def get_tools(self) -> list[BaseTool]:
        """Get cached MCP tools, re-initializing if config changed."""
        if not self._initialized:
            return await self.initialize()
        if self._is_stale():
            logger.info("MCP config changed, re-initializing...")
            await self.shutdown()
            return await self.initialize()
        return list(self._langchain_tools)

    async def shutdown(self):
        """Disconnect all servers."""
        for name, transport in self._servers.items():
            try:
                await transport.disconnect()
                logger.info("Disconnected MCP server '%s'", name)
            except Exception as e:
                logger.warning("Error disconnecting MCP server '%s': %s", name, e)
        self._servers.clear()
        self._sessions.clear()
        self._tools.clear()
        self._langchain_tools.clear()
        self._initialized = False

    @property
    def tool_count(self) -> int:
        return len(self._langchain_tools)

    @property
    def server_count(self) -> int:
        return len(self._servers)


# Global manager
_manager: Optional[MCPTransportManager] = None


async def get_mcp_tools(config_path: Optional[str] = None) -> list[BaseTool]:
    """Get all MCP tools (cached singleton)."""
    global _manager
    if _manager is None:
        _manager = MCPTransportManager(config_path=config_path)
    return await _manager.get_tools()


async def shutdown_mcp():
    """Shutdown all MCP connections."""
    global _manager
    if _manager:
        await _manager.shutdown()
        _manager = None
