"""SandboxMiddleware - manages sandbox environment for each thread."""

import logging
import os
from pathlib import Path
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class SandboxMiddleware(AgentMiddleware):
    """Manages thread-level sandbox acquisition and release.

    On each agent step, ensures the thread has an isolated workspace
    directory available. Creates paths on demand.
    """

    def __init__(self, lazy_init: bool = True, base_path: Optional[str] = None):
        super().__init__()
        self.lazy_init = lazy_init
        self.base_path = base_path or os.environ.get("FORGE_SANDBOX_PATH", ".deer-flow/threads")

    def _resolve_thread_id(self, runtime: Runtime) -> Optional[str]:
        """Extract thread_id from runtime context."""
        ctx = runtime.context or {}
        thread_id = ctx.get("thread_id")
        if thread_id is None:
            try:
                from langgraph.config import get_config
                cfg = get_config()
                thread_id = cfg.get("configurable", {}).get("thread_id")
            except Exception:
                pass
        return thread_id

    def _ensure_workspace(self, thread_id: str) -> dict:
        """Create thread workspace directories and return paths."""
        base = Path(self.base_path) / thread_id / "user-data"
        dirs = {
            "workspace": base / "workspace",
            "uploads": base / "uploads",
            "outputs": base / "outputs",
        }
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)

        return {
            "workspace": str(dirs["workspace"]),
            "uploads": str(dirs["uploads"]),
            "outputs": str(dirs["outputs"]),
        }

    @override
    async def abefore_agent(self, state: AgentState, runtime: Runtime) -> Optional[dict]:
        """Set up sandbox before agent execution."""
        thread_id = self._resolve_thread_id(runtime)
        if not thread_id:
            return None

        paths = self._ensure_workspace(thread_id)
        logger.debug("Sandbox ready for thread %s: workspace=%s", thread_id, paths["workspace"])

        return {
            "sandbox": {
                "thread_id": thread_id,
                "paths": paths,
                "ready": True,
            },
        }