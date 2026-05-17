"""Tool Gateway service for unified tool execution.

This module provides the ToolGateway class that wraps all tool executions
with audit logging, HITL checks, and permission validation. It serves as
the single entry point for all tool invocations in the system.
"""

import time
from typing import Any, Callable, Coroutine, Optional

from agent_platform.models.audit_log import AuditAction, AuditLog, ResourceType
from agent_platform.models.execution_context import ExecutionContext, GatewayConfig
from agent_platform.models.tool_call import (
    HITLCheckResult,
    HITLInterrupt,
    ToolCall,
    ToolCallStatus,
    ToolResult,
)
from agent_platform.services.audit_logger import AuditLogger
from agent_platform.services.hitl_rules import HITLRulesEngine

# Type alias for tool functions
ToolFunction = Callable[..., Coroutine[Any, Any, Any]]


class ToolGateway:
    """Unified gateway for all tool executions.

    The ToolGateway provides a single entry point for executing tools
    with integrated:
    - Audit logging (pre and post execution)
    - HITL (Human-in-the-Loop) approval checks
    - Permission validation
    - Error handling and retries
    - Execution context tracking

    All tool calls should go through this gateway to ensure proper
    logging and compliance.
    """

    def __init__(
        self,
        audit_logger: AuditLogger,
        hitl_engine: Optional[HITLRulesEngine] = None,
        config: Optional[GatewayConfig] = None,
    ):
        """Initialize the Tool Gateway.

        Args:
            audit_logger: Service for logging audit events
            hitl_engine: Optional HITL rules engine for approval checks
            config: Optional gateway configuration
        """
        self.audit = audit_logger
        self.hitl = hitl_engine or HITLRulesEngine()
        self.config = config or GatewayConfig()
        self._tool_registry: dict[str, ToolFunction] = {}

    def register_tool(self, name: str, func: ToolFunction) -> None:
        """Register a tool function with the gateway.

        Args:
            name: The tool name
            func: The async function to execute
        """
        self._tool_registry[name] = func

    def register_tools(self, tools: dict[str, ToolFunction]) -> None:
        """Register multiple tools at once.

        Args:
            tools: Dictionary of tool names to functions
        """
        self._tool_registry.update(tools)

    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool from the gateway.

        Args:
            name: The tool name to unregister

        Returns:
            True if the tool was found and removed
        """
        if name in self._tool_registry:
            del self._tool_registry[name]
            return True
        return False

    def get_registered_tools(self) -> list[str]:
        """Get list of registered tool names.

        Returns:
            List of registered tool names
        """
        return list(self._tool_registry.keys())

    async def execute(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """Execute a tool through the gateway.

        This is the main entry point for tool execution. It performs:
        1. Pre-execution audit logging
        2. HITL approval checks
        3. Tool execution with error handling
        4. Post-execution audit logging

        Args:
            tool_call: The tool call to execute
            context: Execution context with user/session info

        Returns:
            ToolResult with execution results

        Raises:
            HITLInterrupt: If human approval is required
            ValueError: If the tool is not registered
            Exception: Any exception from tool execution (after logging)
        """
        start_time = time.time()
        audit_entry: Optional[AuditLog] = None

        try:
            # 1. Pre-execution audit logging
            if self.config.enable_audit:
                audit_entry = await self.audit.log_tool_call(
                    tool_call=tool_call,
                    context=context,
                    details={
                        "config": self.config.to_dict(),
                        "gateway_version": "1.0",
                    },
                )

            # 2. HITL check (if enabled)
            if self.config.enable_hitl:
                hitl_check = self._check_hitl(tool_call)
                if hitl_check.requires_approval:
                    # Log approval request
                    if self.config.enable_audit and audit_entry:
                        await self.audit.log_approval_request(
                            tool_call=tool_call,
                            context=context,
                            hitl_result=hitl_check,
                            approval_request_id=hitl_check.approval_request_id,
                        )

                    # Raise interrupt for LangGraph integration
                    raise HITLInterrupt(
                        hitl_result=hitl_check,
                        approval_request_id=hitl_check.approval_request_id,
                        message=f"Approval required: {hitl_check.description}",
                    )

            # 3. Execute the tool
            result = await self._execute_tool(tool_call, context)

            # 4. Post-execution audit logging
            execution_time_ms = int((time.time() - start_time) * 1000)
            result.execution_time_ms = execution_time_ms

            if self.config.enable_audit and audit_entry:
                await self.audit.log_tool_result(
                    audit_log_id=str(audit_entry.id),
                    result=result,
                    success=result.success,
                )

            return result

        except HITLInterrupt:
            # Re-raise HITL interrupts without modification
            raise

        except Exception as e:
            # Handle execution errors
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Create error result
            error_result = ToolResult.error_result(
                error=str(e),
                execution_time_ms=execution_time_ms,
                call_id=tool_call.call_id,
            )

            # Log the error
            if self.config.enable_audit and audit_entry:
                await self.audit.log_tool_result(
                    audit_log_id=str(audit_entry.id),
                    result=error_result,
                    success=False,
                )

            # Re-raise the exception
            raise

    async def execute_with_retry(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """Execute a tool with automatic retry on failure.

        Args:
            tool_call: The tool call to execute
            context: Execution context

        Returns:
            ToolResult with execution results

        Raises:
            Exception: If all retries fail
        """
        last_error: Optional[Exception] = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await self.execute(tool_call, context)
            except HITLInterrupt:
                # Never retry HITL interrupts
                raise
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries:
                    # Wait before retry
                    import asyncio
                    await asyncio.sleep(
                        self.config.retry_delay_seconds * (2 ** attempt)
                    )

        # All retries exhausted
        if last_error:
            raise last_error

        # Should never reach here
        raise RuntimeError("Unexpected error in retry loop")

    def _check_hitl(self, tool_call: ToolCall) -> HITLCheckResult:
        """Check if HITL approval is required for a tool call.

        Args:
            tool_call: The tool call to check

        Returns:
            HITLCheckResult indicating if approval is needed
        """
        result = self.hitl.check_rules(
            tool_name=tool_call.tool_name,
            tool_input=tool_call.tool_input,
            context={
                "session_id": tool_call.session_id,
                "task_id": tool_call.task_id,
            },
        )

        return HITLCheckResult.from_rules_engine_result(result)

    async def _execute_tool(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> ToolResult:
        """Execute the actual tool function.

        Args:
            tool_call: The tool call to execute
            context: Execution context

        Returns:
            ToolResult with execution results

        Raises:
            ValueError: If tool is not registered
        """
        tool_name = tool_call.tool_name

        # Check if tool is registered
        if tool_name not in self._tool_registry:
            raise ValueError(f"Tool not registered: {tool_name}")

        tool_func = self._tool_registry[tool_name]

        # Execute with timeout if configured
        if self.config.timeout_seconds:
            import asyncio
            try:
                output = await asyncio.wait_for(
                    tool_func(**tool_call.tool_input),
                    timeout=self.config.timeout_seconds,
                )
            except asyncio.TimeoutError:
                return ToolResult(
                    success=False,
                    error=f"Tool execution timed out after {self.config.timeout_seconds}s",
                    status=ToolCallStatus.TIMEOUT,
                    call_id=tool_call.call_id,
                )
        else:
            output = await tool_func(**tool_call.tool_input)

        return ToolResult.success_result(
            output=output,
            call_id=tool_call.call_id,
        )

    async def check_permissions(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
    ) -> bool:
        """Check if the user has permission to execute the tool.

        Args:
            tool_call: The tool call to check
            context: Execution context

        Returns:
            True if permitted, False otherwise
        """
        if not self.config.check_permissions:
            return True

        # TODO: Implement permission checking based on user roles and tool permissions
        # For now, allow all (placeholder implementation)
        return True

    async def batch_execute(
        self,
        tool_calls: list[ToolCall],
        context: ExecutionContext,
    ) -> list[ToolResult]:
        """Execute multiple tools in sequence.

        Args:
            tool_calls: List of tool calls to execute
            context: Execution context

        Returns:
            List of tool results (one per call)
        """
        results = []
        for tool_call in tool_calls:
            try:
                result = await self.execute(tool_call, context)
                results.append(result)
            except HITLInterrupt as e:
                # Create a result indicating HITL was required
                results.append(
                    ToolResult(
                        success=False,
                        error=f"HITL approval required: {e.message}",
                        status=ToolCallStatus.APPROVAL_REQUIRED,
                        call_id=tool_call.call_id,
                        metadata={"hitl_result": e.hitl_result.to_dict()},
                    )
                )
            except Exception as e:
                results.append(
                    ToolResult.error_result(
                        error=str(e),
                        call_id=tool_call.call_id,
                    )
                )
        return results


class ToolGatewayFactory:
    """Factory for creating ToolGateway instances."""

    @staticmethod
    async def create(
        audit_logger: AuditLogger,
        hitl_engine: Optional[HITLRulesEngine] = None,
        config: Optional[GatewayConfig] = None,
    ) -> ToolGateway:
        """Create a ToolGateway instance.

        Args:
            audit_logger: Audit logger service
            hitl_engine: Optional HITL rules engine
            config: Optional gateway configuration

        Returns:
            ToolGateway instance
        """
        return ToolGateway(
            audit_logger=audit_logger,
            hitl_engine=hitl_engine,
            config=config,
        )

    @staticmethod
    async def create_with_db(
        db: Any,
        enable_hitl: bool = True,
        enable_audit: bool = True,
    ) -> ToolGateway:
        """Create a ToolGateway with database dependencies.

        Args:
            db: Database session
            enable_hitl: Whether to enable HITL checks
            enable_audit: Whether to enable audit logging

        Returns:
            ToolGateway instance
        """
        from agent_platform.services.audit_logger import AuditLogger

        audit_logger = AuditLogger(db=db)
        hitl_engine = HITLRulesEngine() if enable_hitl else None
        config = GatewayConfig(
            enable_hitl=enable_hitl,
            enable_audit=enable_audit,
        )

        return ToolGateway(
            audit_logger=audit_logger,
            hitl_engine=hitl_engine,
            config=config,
        )
