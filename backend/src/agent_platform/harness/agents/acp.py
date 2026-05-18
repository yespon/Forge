"""ACP (Agent Communication Protocol) integration for external agents.

Supports invoking Claude Code, Codex, and other ACP-compatible agents.
Each agent runs as a subprocess with an isolated workspace.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@dataclass
class ACPAgentConfig:
    """Configuration for an ACP-compatible external agent."""
    name: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 600
    api_url: str = ""  # For HTTP-based ACP agents
    api_key: str = ""


class ACPAgentManager:
    """Manages external ACP-compatible agents (Claude Code, Codex, etc.)."""

    def __init__(self):
        self._configs: dict[str, ACPAgentConfig] = {}
        self._load_defaults()

    def _load_defaults(self):
        """Load default agent configurations from environment."""
        # Claude Code
        claude_code_cmd = os.environ.get("CLAUDE_CODE_CMD", "")
        if claude_code_cmd or os.environ.get("CLAUDE_CODE_API_KEY"):
            self._configs["claude-code"] = ACPAgentConfig(
                name="claude-code",
                command=claude_code_cmd or "npx",
                args=["@anthropic-ai/claude-code", "--acp"] if not claude_code_cmd else ["--acp"],
                api_url=os.environ.get("CLAUDE_CODE_API_URL", "http://localhost:8080"),
                api_key=os.environ.get("CLAUDE_CODE_API_KEY", ""),
                timeout=900,
            )

    def register(self, config: ACPAgentConfig) -> None:
        self._configs[config.name] = config
        logger.info("Registered ACP agent: %s", config.name)

    def get(self, name: str) -> Optional[ACPAgentConfig]:
        return self._configs.get(name)

    def list_agents(self) -> list[str]:
        return list(self._configs.keys())


_manager: Optional[ACPAgentManager] = None


def get_acp_manager() -> ACPAgentManager:
    global _manager
    if _manager is None:
        _manager = ACPAgentManager()
    return _manager


async def invoke_acp_agent(
    agent_name: str,
    prompt: str,
    work_dir: Optional[str] = None,
    timeout: Optional[int] = None,
) -> str:
    """Invoke an ACP-compatible external agent.

    Args:
        agent_name: Name of the ACP agent (e.g., "claude-code", "codex")
        prompt: Task description to send to the agent
        work_dir: Working directory for the agent
        timeout: Maximum execution time in seconds

    Returns:
        Agent's response text
    """
    mgr = get_acp_manager()
    config = mgr.get(agent_name)
    if not config:
        raise ValueError(f"Unknown ACP agent: {agent_name}")

    timeout = timeout or config.timeout
    work_dir = work_dir or tempfile.mkdtemp(prefix=f"acp-{agent_name}-")
    os.makedirs(work_dir, exist_ok=True)

    logger.info("Invoking ACP agent '%s' with timeout=%ds in %s", agent_name, timeout, work_dir)

    try:
        if config.api_url:
            return await _invoke_acp_http(config, prompt, work_dir, timeout)
        else:
            return await _invoke_acp_subprocess(config, prompt, work_dir, timeout)
    except asyncio.TimeoutError:
        return f"ACP agent '{agent_name}' timed out after {timeout}s"
    except Exception as e:
        logger.exception("ACP agent '%s' failed")
        return f"ACP agent '{agent_name}' failed: {e}"


async def _invoke_acp_http(config: ACPAgentConfig, prompt: str, work_dir: str, timeout: int) -> str:
    """Invoke an HTTP-based ACP agent."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        payload = {
            "prompt": prompt,
            "work_dir": work_dir,
        }
        resp = await client.post(config.api_url + "/run", json=payload, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return result.get("result") or result.get("output") or str(result)


async def _invoke_acp_subprocess(config: ACPAgentConfig, prompt: str, work_dir: str, timeout: int) -> str:
    """Invoke a subprocess-based ACP agent."""
    env = os.environ.copy()
    env.update(config.env)
    env["WORK_DIR"] = work_dir

    # Write prompt to temp file
    prompt_file = Path(work_dir) / "_acp_prompt.txt"
    prompt_file.write_text(prompt)

    full_args = config.args + [str(prompt_file)]

    process = await asyncio.create_subprocess_exec(
        config.command, *full_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=work_dir,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        if process.returncode != 0 and process.returncode is not None:
            return f"ACP agent exited with code {process.returncode}:\n{stderr_str[:2000]}\n{stdout_str[:2000]}"

        # Try to read output from work dir
        result_file = Path(work_dir) / "_acp_result.txt"
        if result_file.exists():
            return result_file.read_text()

        return stdout_str[-10000:] if len(stdout_str) > 10000 else stdout_str

    except asyncio.TimeoutError:
        process.kill()
        raise


@tool(parse_docstring=True)
def invoke_acp_agent_tool(
    agent: str,
    prompt: str,
    timeout: Optional[int] = 600,
) -> str:
    """Invoke an external ACP-compatible agent (Claude Code, Codex, etc.).

    Use this for tasks better suited for specialized external agents.

    Args:
        agent: Name of the ACP agent to invoke
        prompt: The task description to send to the agent
        timeout: Maximum execution time in seconds

    Returns:
        Agent's response
    """
    return asyncio.run(invoke_acp_agent(agent, prompt, timeout=timeout))
