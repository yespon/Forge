"""ForgeHITLMiddleware - HITL approval via Forge's ToolGateway."""

import logging
from typing import Any, Optional, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

logger = logging.getLogger(__name__)


class ForgeHITLMiddleware(AgentMiddleware):
    """HITL approval middleware using Forge's HITLRulesEngine.

    Intercepts tool calls that match security rules and creates
    approval requests before allowing execution.
    """

    def __init__(self, session_id: Optional[str] = None, task_id: Optional[str] = None,
                 org_id: Optional[str] = None, user_id: Optional[str] = None,
                 db: Optional[Any] = None):
        super().__init__()
        self.session_id = session_id
        self.task_id = task_id
        self.org_id = org_id
        self.user_id = user_id
        self.db = db
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from agent_platform.services.hitl_rules import HITLRulesEngine
            self._engine = HITLRulesEngine(org_id=self.org_id)
        return self._engine

    @override
    async def awrap_tool_call(self, request, handler):
        """Intercept tool calls to check HITL requirements."""
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "")
        tool_input = tool_call.get("args", {})

        engine = self._get_engine()
        result = engine.check_rules(tool_name=tool_name, tool_input=tool_input)

        if not result.get("requires_approval"):
            return await handler(request)

        risk = result.get("risk_level", "medium")
        rule = result.get("matched_rule", "Unknown rule")
        desc = result.get("description", "No description")

        logger.warning(
            "HITL required: tool=%s risk=%s rule=%s session=%s",
            tool_name, risk, rule, self.session_id,
        )

        # Create approval request via ToolGateway
        try:
            from agent_platform.services.tool_gateway import ToolGateway
            gateway = ToolGateway(db=self.db)
            approval = await gateway.create_approval_request(
                tool_name=tool_name,
                tool_input=tool_input,
                risk_level=risk,
                matched_rule=rule,
                description=desc,
                session_id=self.session_id,
                task_id=self.task_id,
                user_id=self.user_id,
            )
            return Command(
                goto="human",
                update={"approval_request": approval},
            )
        except Exception as e:
            logger.error("HITL approval creation failed: %s", e)
            return ToolMessage(
                content=f"HITL approval required for {tool_name} but approval system unavailable: {e}",
                tool_call_id=tool_call["id"],
                status="error",
            )
