"""Audit logger service for recording all tool executions and system actions.

This module provides the AuditLogger class for creating and querying
audit log entries. It integrates with the database to provide an
immutable audit trail for compliance and security.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from agent_platform.models.audit_log import AuditAction, AuditLog, ResourceType
from agent_platform.models.execution_context import ExecutionContext
from agent_platform.models.tool_call import HITLCheckResult, ToolCall, ToolResult


class AuditLogger:
    """Service for logging audit events.

    This class provides methods for creating audit log entries
    for tool calls, results, approval requests, and other system actions.
    """

    def __init__(self, db: AsyncSession):
        """Initialize audit logger.

        Args:
            db: Database session for persisting audit logs
        """
        self.db = db

    async def log_tool_call(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
        details: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        """Log a tool call before execution.

        Args:
            tool_call: The tool call being made
            context: Execution context with user/session info
            details: Additional details to log

        Returns:
            The created audit log entry
        """
        audit_entry = AuditLog(
            user_id=context.user_id,
            org_id=context.org_id,
            session_id=context.session_id,
            task_id=context.task_id,
            action=AuditAction.TOOL_CALL,
            resource_type=ResourceType.TOOL,
            resource_id=tool_call.tool_name,
            details={
                "tool_call": tool_call.to_dict(),
                **(details or {}),
            },
            success=None,  # Will be updated after execution
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def log_tool_result(
        self,
        audit_log_id: str,
        result: ToolResult,
        success: bool,
    ) -> AuditLog:
        """Log the result of a tool execution.

        Args:
            audit_log_id: ID of the original audit log entry
            result: The tool execution result
            success: Whether the execution was successful

        Returns:
            The updated audit log entry
        """
        # Fetch the existing audit log
        stmt = select(AuditLog).where(AuditLog.id == audit_log_id)
        result_row = await self.db.execute(stmt)
        audit_entry = result_row.scalar_one_or_none()

        if not audit_entry:
            raise ValueError(f"Audit log entry not found: {audit_log_id}")

        # Update with result information
        audit_entry.success = success
        audit_entry.details["tool_result"] = result.to_dict()

        if not success and result.error:
            audit_entry.error_message = result.error
            audit_entry.action = AuditAction.TOOL_ERROR

        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def log_approval_request(
        self,
        tool_call: ToolCall,
        context: ExecutionContext,
        hitl_result: HITLCheckResult,
        approval_request_id: Optional[str] = None,
    ) -> AuditLog:
        """Log an approval request.

        Args:
            tool_call: The tool call requiring approval
            context: Execution context
            hitl_result: HITL check result
            approval_request_id: ID of the approval request

        Returns:
            The created audit log entry
        """
        audit_entry = AuditLog(
            user_id=context.user_id,
            org_id=context.org_id,
            session_id=context.session_id,
            task_id=context.task_id,
            action=AuditAction.APPROVAL_REQUESTED,
            resource_type=ResourceType.APPROVAL,
            resource_id=approval_request_id,
            details={
                "tool_call": tool_call.to_dict(),
                "hitl_result": hitl_result.to_dict(),
                "approval_request_id": approval_request_id,
            },
            success=None,  # Pending approval
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def log_approval_decision(
        self,
        approval_request_id: str,
        decision: str,
        decided_by: str,
        context: ExecutionContext,
        reason: Optional[str] = None,
    ) -> AuditLog:
        """Log an approval decision.

        Args:
            approval_request_id: ID of the approval request
            decision: The decision made (approved/rejected)
            decided_by: User ID who made the decision
            context: Execution context
            reason: Optional reason for the decision

        Returns:
            The created audit log entry
        """
        audit_entry = AuditLog(
            user_id=decided_by,
            org_id=context.org_id,
            session_id=context.session_id,
            task_id=context.task_id,
            action=AuditAction.APPROVAL_DECISION,
            resource_type=ResourceType.APPROVAL,
            resource_id=approval_request_id,
            details={
                "approval_request_id": approval_request_id,
                "decision": decision,
                "decided_by": decided_by,
                "reason": reason,
            },
            success=(decision == "approved"),
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def log_task_event(
        self,
        task_id: str,
        action: AuditAction,
        context: ExecutionContext,
        details: Optional[dict[str, Any]] = None,
        success: Optional[bool] = None,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """Log a task lifecycle event.

        Args:
            task_id: ID of the task
            action: The task action (created, started, completed, etc.)
            context: Execution context
            details: Additional details
            success: Whether the action was successful
            error_message: Optional error message

        Returns:
            The created audit log entry
        """
        audit_entry = AuditLog(
            user_id=context.user_id,
            org_id=context.org_id,
            session_id=context.session_id,
            task_id=task_id,
            action=action,
            resource_type=ResourceType.TASK,
            resource_id=task_id,
            details=details or {},
            success=success,
            error_message=error_message,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def log_session_event(
        self,
        session_id: str,
        action: AuditAction,
        context: ExecutionContext,
        details: Optional[dict[str, Any]] = None,
        success: Optional[bool] = None,
    ) -> AuditLog:
        """Log a session lifecycle event.

        Args:
            session_id: ID of the session
            action: The session action
            context: Execution context
            details: Additional details
            success: Whether the action was successful

        Returns:
            The created audit log entry
        """
        audit_entry = AuditLog(
            user_id=context.user_id,
            org_id=context.org_id,
            session_id=session_id,
            action=action,
            resource_type=ResourceType.SESSION,
            resource_id=session_id,
            details=details or {},
            success=success,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            request_id=context.request_id,
        )

        self.db.add(audit_entry)
        await self.db.commit()
        await self.db.refresh(audit_entry)

        return audit_entry

    async def query_logs(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "timestamp",
        descending: bool = True,
    ) -> list[AuditLog]:
        """Query audit logs with filters.

        Args:
            filters: Dictionary of filter conditions
            limit: Maximum number of results
            offset: Offset for pagination
            order_by: Column to order by
            descending: Whether to order in descending order

        Returns:
            List of audit log entries
        """
        stmt = select(AuditLog)

        # Apply filters
        if filters:
            if "user_id" in filters:
                stmt = stmt.where(AuditLog.user_id == filters["user_id"])
            if "org_id" in filters:
                stmt = stmt.where(AuditLog.org_id == filters["org_id"])
            if "session_id" in filters:
                stmt = stmt.where(AuditLog.session_id == filters["session_id"])
            if "task_id" in filters:
                stmt = stmt.where(AuditLog.task_id == filters["task_id"])
            if "action" in filters:
                stmt = stmt.where(AuditLog.action == filters["action"])
            if "resource_type" in filters:
                stmt = stmt.where(AuditLog.resource_type == filters["resource_type"])
            if "success" in filters:
                stmt = stmt.where(AuditLog.success == filters["success"])
            if "from_date" in filters:
                stmt = stmt.where(AuditLog.timestamp >= filters["from_date"])
            if "to_date" in filters:
                stmt = stmt.where(AuditLog.timestamp <= filters["to_date"])
            if "request_id" in filters:
                stmt = stmt.where(AuditLog.request_id == filters["request_id"])

        # Apply ordering
        order_col = getattr(AuditLog, order_by, AuditLog.timestamp)
        if descending:
            stmt = stmt.order_by(order_col.desc())
        else:
            stmt = stmt.order_by(order_col.asc())

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_log_by_id(self, log_id: str) -> Optional[AuditLog]:
        """Get a single audit log entry by ID.

        Args:
            log_id: The audit log ID

        Returns:
            The audit log entry or None
        """
        stmt = select(AuditLog).where(AuditLog.id == log_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def count_logs(
        self,
        filters: Optional[dict[str, Any]] = None,
    ) -> int:
        """Count audit logs matching filters.

        Args:
            filters: Dictionary of filter conditions

        Returns:
            Number of matching audit log entries
        """
        stmt = select(func.count(AuditLog.id))

        # Apply filters
        if filters:
            if "user_id" in filters:
                stmt = stmt.where(AuditLog.user_id == filters["user_id"])
            if "org_id" in filters:
                stmt = stmt.where(AuditLog.org_id == filters["org_id"])
            if "session_id" in filters:
                stmt = stmt.where(AuditLog.session_id == filters["session_id"])
            if "task_id" in filters:
                stmt = stmt.where(AuditLog.task_id == filters["task_id"])
            if "action" in filters:
                stmt = stmt.where(AuditLog.action == filters["action"])
            if "resource_type" in filters:
                stmt = stmt.where(AuditLog.resource_type == filters["resource_type"])
            if "success" in filters:
                stmt = stmt.where(AuditLog.success == filters["success"])
            if "from_date" in filters:
                stmt = stmt.where(AuditLog.timestamp >= filters["from_date"])
            if "to_date" in filters:
                stmt = stmt.where(AuditLog.timestamp <= filters["to_date"])

        result = await self.db.execute(stmt)
        return result.scalar() or 0


class AuditLoggerFactory:
    """Factory for creating AuditLogger instances."""

    @staticmethod
    async def create(db: AsyncSession) -> AuditLogger:
        """Create an AuditLogger instance.

        Args:
            db: Database session

        Returns:
            AuditLogger instance
        """
        return AuditLogger(db=db)
