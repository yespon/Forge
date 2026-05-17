"""HITL (Human-in-the-Loop) tool wrapper for LangGraph integration."""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from langchain_core.tools import StructuredTool
from langgraph.types import interrupt

from agent_platform.models.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStrategy,
    RiskLevel,
)
from agent_platform.services.hitl_rules import HITLRulesEngine


class HITLInterrupt(Exception):
    """Exception raised when HITL approval is required.

    This exception is caught by LangGraph and triggers the interrupt mechanism.
    """

    def __init__(
        self,
        approval_request: ApprovalRequest,
        message: str = "Human approval required",
    ):
        self.approval_request = approval_request
        self.message = message
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert interrupt to dictionary for LangGraph."""
        return {
            "type": "hitl_interrupt",
            "approval_request_id": self.approval_request.id,
            "tool_name": self.approval_request.tool_name,
            "tool_input": self.approval_request.tool_input,
            "risk_level": self.approval_request.risk_level,
            "description": self.approval_request.description,
            "message": self.message,
        }


class HITLWrappedTool:
    """Wrapper for tools that require Human-in-the-Loop approval.

    This wrapper intercepts tool calls and checks them against HITL rules.
    If a rule matches, it raises an interrupt that pauses execution until
    human approval is received.
    """

    def __init__(
        self,
        tool: Callable | StructuredTool,
        tool_name: str,
        rules_engine: HITLRulesEngine,
        description: Optional[str] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        checkpoint_ns: Optional[str] = None,
        db_session: Optional[Any] = None,
    ):
        """Initialize HITL wrapped tool.

        Args:
            tool: The original tool function or StructuredTool
            tool_name: Name of the tool
            rules_engine: HITL rules engine instance
            description: Optional tool description
            session_id: Optional session ID for tracking
            task_id: Optional task ID for tracking
            thread_id: Optional LangGraph thread ID
            checkpoint_ns: Optional checkpoint namespace
            db_session: Optional database session for persisting approvals
        """
        self.original_tool = tool
        self.tool_name = tool_name
        self.rules_engine = rules_engine
        self.description = description or getattr(tool, "description", None)
        self.session_id = session_id
        self.task_id = task_id
        self.thread_id = thread_id
        self.checkpoint_ns = checkpoint_ns
        self.db_session = db_session

        # If tool is already a StructuredTool, extract the function
        if isinstance(tool, StructuredTool):
            self._func = tool.func
            self._args_schema = tool.args_schema
        else:
            self._func = tool
            self._args_schema = None

    def check_rules(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Check if the tool call requires HITL approval.

        Args:
            tool_input: Input arguments for the tool

        Returns:
            Dictionary with rule check results
        """
        return self.rules_engine.check_rules(
            tool_name=self.tool_name,
            tool_input=tool_input,
        )

    async def __call__(self, **kwargs: Any) -> Any:
        """Execute the tool with HITL checks.

        This method:
        1. Checks if the tool call matches any HITL rules
        2. If no rules match, executes the tool normally
        3. If rules match, creates an approval request and raises interrupt

        Args:
            **kwargs: Tool input arguments

        Returns:
            Tool execution result

        Raises:
            HITLInterrupt: If approval is required
        """
        # Check rules
        rule_result = self.check_rules(kwargs)

        if not rule_result["requires_approval"]:
            # No approval needed, execute directly
            if hasattr(self._func, "__call__"):
                if hasattr(self._func, "__wrapped__") or hasattr(self._func, "__code__"):
                    # Check if it's async
                    import inspect
                    if inspect.iscoroutinefunction(self._func):
                        return await self._func(**kwargs)
                    else:
                        return self._func(**kwargs)
            return self._func(**kwargs)

        # Approval required - create approval request
        approval_request = self._create_approval_request(rule_result, kwargs)

        # Persist approval request to database if session available
        if self.db_session:
            self.db_session.add(approval_request)
            await self.db_session.commit()

        # Raise interrupt for LangGraph
        # This will pause execution and wait for human input
        interrupt_value = {
            "type": "hitl_approval_required",
            "approval_request": approval_request.to_dict(),
            "tool_name": self.tool_name,
            "tool_input": kwargs,
            "risk_level": rule_result["risk_level"].value,
            "description": rule_result.get("description"),
        }

        # Use LangGraph's interrupt mechanism
        result = interrupt(interrupt_value)

        # Execution resumes here after human provides input
        # Result should contain the approval decision
        if isinstance(result, dict):
            decision = result.get("decision")
            if decision == ApprovalDecision.APPROVED:
                # Approval granted, execute the tool
                return await self._execute_tool(kwargs)
            else:
                # Approval denied or rejected
                raise HITLInterrupt(
                    approval_request=approval_request,
                    message=f"Tool execution {decision}: {result.get('reason', 'No reason provided')}",
                )
        else:
            # Handle case where result is not a dict
            raise HITLInterrupt(
                approval_request=approval_request,
                message="Invalid approval response",
            )

    def _create_approval_request(
        self,
        rule_result: dict[str, Any],
        tool_input: dict[str, Any],
    ) -> ApprovalRequest:
        """Create an approval request based on rule match.

        Args:
            rule_result: Result from rules engine
            tool_input: Tool input arguments

        Returns:
            ApprovalRequest instance
        """
        # Compute hash for deduplication
        input_hash = self.rules_engine.compute_input_hash(
            self.tool_name, tool_input
        )

        # Determine expiration time
        risk_level = rule_result.get("risk_level", RiskLevel.MEDIUM)
        if risk_level == RiskLevel.CRITICAL:
            expires_minutes = 60  # 1 hour for critical
        elif risk_level == RiskLevel.HIGH:
            expires_minutes = 120  # 2 hours for high
        else:
            expires_minutes = 240  # 4 hours for medium/low

        # Build approvers list
        approvers = rule_result.get("approvers", [])
        if not approvers:
            # Default approvers based on risk level
            approvers = [{"role": "admin", "required": True}]

        # Build description
        description = rule_result.get("description", "Tool execution requires approval")
        context_summary = f"Tool: {self.tool_name}\nInput: {json.dumps(tool_input, indent=2)}"

        return ApprovalRequest(
            task_id=self.task_id,
            session_id=self.session_id or "",
            thread_id=self.thread_id,
            checkpoint_ns=self.checkpoint_ns,
            tool_name=self.tool_name,
            tool_input=tool_input,
            tool_input_hash=input_hash,
            risk_level=risk_level.value if isinstance(risk_level, RiskLevel) else risk_level,
            description=description,
            context_summary=context_summary,
            approvers=approvers,
            strategy=rule_result.get("strategy", ApprovalStrategy.SINGLE),
            min_approvals_required=rule_result.get("min_approvals_required", 1),
            status=ApprovalStatus.PENDING,
            decisions=[],
            escalation_timeout_minutes=rule_result.get("escalation_timeout_minutes"),
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=expires_minutes),
        )

    async def _execute_tool(self, tool_input: dict[str, Any]) -> Any:
        """Execute the wrapped tool.

        Args:
            tool_input: Tool input arguments

        Returns:
            Tool execution result
        """
        import inspect

        if inspect.iscoroutinefunction(self._func):
            return await self._func(**tool_input)
        else:
            return self._func(**tool_input)

    def to_structured_tool(self) -> StructuredTool:
        """Convert this HITL wrapped tool to a StructuredTool.

        Returns:
            StructuredTool instance
        """
        return StructuredTool.from_function(
            func=self,
            name=self.tool_name,
            description=self.description or f"HITL wrapped {self.tool_name}",
            args_schema=self._args_schema,
        )


class HITLToolManager:
    """Manager for creating and managing HITL-wrapped tools."""

    def __init__(
        self,
        rules_engine: Optional[HITLRulesEngine] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        db_session: Optional[Any] = None,
    ):
        """Initialize HITL tool manager.

        Args:
            rules_engine: HITL rules engine (creates default if not provided)
            session_id: Optional session ID for tracking
            task_id: Optional task ID for tracking
            thread_id: Optional LangGraph thread ID
            db_session: Optional database session
        """
        self.rules_engine = rules_engine or HITLRulesEngine()
        self.session_id = session_id
        self.task_id = task_id
        self.thread_id = thread_id
        self.db_session = db_session
        self._wrapped_tools: dict[str, HITLWrappedTool] = {}

    def wrap_tool(
        self,
        tool: Callable | StructuredTool,
        tool_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> HITLWrappedTool:
        """Wrap a tool with HITL functionality.

        Args:
            tool: Tool to wrap
            tool_name: Optional name override
            description: Optional description override

        Returns:
            HITLWrappedTool instance
        """
        name = tool_name or getattr(tool, "name", tool.__name__)

        wrapped = HITLWrappedTool(
            tool=tool,
            tool_name=name,
            rules_engine=self.rules_engine,
            description=description or getattr(tool, "description", None),
            session_id=self.session_id,
            task_id=self.task_id,
            thread_id=self.thread_id,
            db_session=self.db_session,
        )

        self._wrapped_tools[name] = wrapped
        return wrapped

    def wrap_tools(
        self,
        tools: list[Callable | StructuredTool],
    ) -> list[HITLWrappedTool]:
        """Wrap multiple tools with HITL functionality.

        Args:
            tools: List of tools to wrap

        Returns:
            List of HITLWrappedTool instances
        """
        return [self.wrap_tool(tool) for tool in tools]

    def get_wrapped_tool(self, tool_name: str) -> Optional[HITLWrappedTool]:
        """Get a wrapped tool by name.

        Args:
            tool_name: Name of the wrapped tool

        Returns:
            HITLWrappedTool if found, None otherwise
        """
        return self._wrapped_tools.get(tool_name)

    def to_structured_tools(self) -> list[StructuredTool]:
        """Convert all wrapped tools to StructuredTool instances.

        Returns:
            List of StructuredTool instances
        """
        return [tool.to_structured_tool() for tool in self._wrapped_tools.values()]


def wrap_tool_with_hitl(
    tool: Callable | StructuredTool,
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    db_session: Optional[Any] = None,
    custom_rules: Optional[list[dict]] = None,
) -> HITLWrappedTool:
    """Convenience function to wrap a single tool with HITL.

    Args:
        tool: Tool to wrap
        session_id: Optional session ID
        task_id: Optional task ID
        thread_id: Optional LangGraph thread ID
        db_session: Optional database session
        custom_rules: Optional custom HITL rules

    Returns:
        HITLWrappedTool instance
    """
    rules_engine = HITLRulesEngine(custom_rules=custom_rules)
    manager = HITLToolManager(
        rules_engine=rules_engine,
        session_id=session_id,
        task_id=task_id,
        thread_id=thread_id,
        db_session=db_session,
    )
    return manager.wrap_tool(tool)
