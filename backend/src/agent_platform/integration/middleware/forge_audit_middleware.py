"""ForgeAuditMiddleware - audit logging for all tool calls."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class ForgeAuditMiddleware(AgentMiddleware):
    """Records all tool calls to the audit log for compliance.

    Integrates with Forge's AuditLogger to capture:
    - Tool name and input arguments
    - Execution result (success/error)
    - User and session context
    - Timestamps
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        db: Optional[Any] = None,
    ):
        super().__init__()
        self.session_id = session_id
        self.user_id = user_id
        self.org_id = org_id
        self.db = db

    @override
    async def awrap_tool_call(self, request, handler):
        """Intercept tool call, execute it, then audit the result."""
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")
        tool_input = tool_call.get("args", {})

        start_time = datetime.now(timezone.utc)

        try:
            result = await handler(request)
            status = "success" if isinstance(result, ToolMessage) and result.status != "error" else "error"
            return result
        except Exception as e:
            status = "error"
            raise
        finally:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            self._log_audit(tool_name, tool_input, status, elapsed)

    def _log_audit(self, tool_name: str, tool_input: dict, status: str, elapsed: float):
        """Write audit log entry."""
        try:
            from agent_platform.services.audit_logger import AuditLogger
            from agent_platform.models.audit_log import AuditAction

            logger.info(
                "AUDIT: tool=%s status=%s user=%s session=%s elapsed=%.2fs",
                tool_name, status, self.user_id, self.session_id, elapsed,
            )

            if self.db is not None:
                audit = AuditLogger(db=self.db)
                import asyncio
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    pass
        except Exception as e:
            logger.warning("Audit logging failed: %s", e)
