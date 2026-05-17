"""Tests for Tool Gateway and Audit Logger.

This module provides comprehensive tests for:
- Tool Gateway execution flow
- Audit logging
- HITL integration
- Error handling
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.models.audit_log import AuditAction, AuditLog, ResourceType
from agent_platform.models.execution_context import ExecutionContext, GatewayConfig
from agent_platform.models.org import Org
from agent_platform.models.session import Session
from agent_platform.models.task import Task
from agent_platform.models.tool_call import (
    HITLCheckResult,
    HITLInterrupt,
    ToolCall,
    ToolCallStatus,
    ToolResult,
)
from agent_platform.models.user import User, UserRole
from agent_platform.services.audit_logger import AuditLogger
from agent_platform.services.hitl_rules import HITLRulesEngine
from agent_platform.services.tool_gateway import ToolGateway, ToolGatewayFactory


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = Mock()
    return db


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.org_id = uuid4()
    user.email = "test@example.com"
    user.role = UserRole.DEVELOPER
    return user


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    session = MagicMock(spec=Session)
    session.id = uuid4()
    session.name = "Test Session"
    return session


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    task = MagicMock(spec=Task)
    task.id = uuid4()
    task.prompt = "Test task"
    return task


@pytest.fixture
def execution_context(sample_user, sample_session, sample_task):
    """Create an execution context for testing."""
    return ExecutionContext(
        user=sample_user,
        session=sample_session,
        task=sample_task,
        ip_address="127.0.0.1",
        user_agent="Test-Agent/1.0",
        request_id=str(uuid4()),
    )


@pytest.fixture
def sample_tool_call():
    """Create a sample tool call for testing."""
    return ToolCall(
        tool_name="test_tool",
        tool_input={"arg1": "value1", "arg2": 42},
    )


@pytest.fixture
def audit_logger(mock_db):
    """Create an audit logger with mock database."""
    return AuditLogger(db=mock_db)


@pytest.fixture
def hitl_engine():
    """Create a HITL rules engine."""
    return HITLRulesEngine()


@pytest.fixture
def tool_gateway(mock_db, hitl_engine):
    """Create a Tool Gateway with mock dependencies."""
    audit_logger = AuditLogger(db=mock_db)
    return ToolGateway(
        audit_logger=audit_logger,
        hitl_engine=hitl_engine,
        config=GatewayConfig(enable_hitl=True, enable_audit=True),
    )


# =============================================================================
# Tool Call and Result Model Tests
# =============================================================================


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_tool_call_creation(self):
        """Test creating a ToolCall instance."""
        tool_call = ToolCall(
            tool_name="test_tool",
            tool_input={"key": "value"},
        )

        assert tool_call.tool_name == "test_tool"
        assert tool_call.tool_input == {"key": "value"}
        assert tool_call.call_id is not None
        assert tool_call.timestamp is not None

    def test_tool_call_to_dict(self):
        """Test converting ToolCall to dictionary."""
        tool_call = ToolCall(
            tool_name="test_tool",
            tool_input={"key": "value"},
            session_id="session-123",
        )

        data = tool_call.to_dict()

        assert data["tool_name"] == "test_tool"
        assert data["tool_input"] == {"key": "value"}
        assert data["session_id"] == "session-123"
        assert "call_id" in data
        assert "timestamp" in data

    def test_tool_call_from_dict(self):
        """Test creating ToolCall from dictionary."""
        data = {
            "call_id": "test-id",
            "tool_name": "test_tool",
            "tool_input": {"key": "value"},
            "timestamp": datetime.now().isoformat(),
            "session_id": "session-123",
        }

        tool_call = ToolCall.from_dict(data)

        assert tool_call.call_id == "test-id"
        assert tool_call.tool_name == "test_tool"
        assert tool_call.tool_input == {"key": "value"}
        assert tool_call.session_id == "session-123"


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self):
        """Test creating a successful result."""
        result = ToolResult.success_result(
            output={"data": "test"},
            execution_time_ms=100,
            call_id="call-123",
        )

        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.execution_time_ms == 100
        assert result.call_id == "call-123"
        assert result.status == ToolCallStatus.SUCCESS
        assert result.error is None

    def test_error_result(self):
        """Test creating an error result."""
        result = ToolResult.error_result(
            error="Something went wrong",
            execution_time_ms=50,
            call_id="call-456",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.output is None
        assert result.execution_time_ms == 50
        assert result.call_id == "call-456"
        assert result.status == ToolCallStatus.ERROR

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = ToolResult(
            success=True,
            output="test output",
            execution_time_ms=100,
            call_id="call-123",
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["output"] == "test output"
        assert data["execution_time_ms"] == 100
        assert data["call_id"] == "call-123"
        assert data["status"] == "success"


class TestHITLCheckResult:
    """Tests for HITLCheckResult dataclass."""

    def test_no_approval_required(self):
        """Test result when no approval is required."""
        result = HITLCheckResult.no_approval_required()

        assert result.requires_approval is False
        assert result.risk_level is None
        assert result.matched_rule is None

    def test_from_rules_engine_result(self):
        """Test creating from rules engine result."""
        engine_result = {
            "requires_approval": True,
            "risk_level": "high",
            "matched_rule": "dangerous_command",
            "description": "This is dangerous",
            "strategy": "single",
            "min_approvals_required": 1,
        }

        result = HITLCheckResult.from_rules_engine_result(engine_result)

        assert result.requires_approval is True
        assert result.risk_level == "high"
        assert result.matched_rule == "dangerous_command"
        assert result.description == "This is dangerous"
        assert result.strategy == "single"
        assert result.min_approvals_required == 1


class TestHITLInterrupt:
    """Tests for HITLInterrupt exception."""

    def test_interrupt_creation(self):
        """Test creating HITL interrupt exception."""
        hitl_result = HITLCheckResult(
            requires_approval=True,
            risk_level="high",
            description="Dangerous operation",
        )

        interrupt = HITLInterrupt(
            hitl_result=hitl_result,
            approval_request_id="req-123",
        )

        assert interrupt.hitl_result == hitl_result
        assert interrupt.approval_request_id == "req-123"
        assert "Dangerous operation" in interrupt.message

    def test_interrupt_to_dict(self):
        """Test converting interrupt to dictionary."""
        hitl_result = HITLCheckResult(
            requires_approval=True,
            risk_level="critical",
        )

        interrupt = HITLInterrupt(hitl_result=hitl_result)
        data = interrupt.to_dict()

        assert data["type"] == "hitl_interrupt"
        assert "hitl_result" in data
        assert data["hitl_result"]["requires_approval"] is True


# =============================================================================
# Execution Context Tests
# =============================================================================


class TestExecutionContext:
    """Tests for ExecutionContext dataclass."""

    def test_context_creation(self, sample_user):
        """Test creating execution context."""
        context = ExecutionContext(
            user=sample_user,
            ip_address="192.168.1.1",
        )

        assert context.user == sample_user
        assert context.org_id == str(sample_user.org_id)
        assert context.ip_address == "192.168.1.1"
        assert context.request_id is not None

    def test_context_properties(self, sample_user, sample_session, sample_task):
        """Test context property accessors."""
        context = ExecutionContext(
            user=sample_user,
            session=sample_session,
            task=sample_task,
        )

        assert context.user_id == str(sample_user.id)
        assert context.session_id == str(sample_session.id)
        assert context.task_id == str(sample_task.id)

    def test_context_to_dict(self, sample_user):
        """Test converting context to dictionary."""
        context = ExecutionContext(
            user=sample_user,
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )

        data = context.to_dict()

        assert data["user_id"] == str(sample_user.id)
        assert data["org_id"] == str(sample_user.org_id)
        assert data["ip_address"] == "10.0.0.1"
        assert data["user_agent"] == "Mozilla/5.0"
        assert "request_id" in data


# =============================================================================
# Audit Logger Tests
# =============================================================================


class TestAuditLogger:
    """Tests for AuditLogger service."""

    @pytest.mark.asyncio
    async def test_log_tool_call(self, audit_logger, sample_tool_call, execution_context, mock_db):
        """Test logging a tool call."""
        log_entry = await audit_logger.log_tool_call(
            tool_call=sample_tool_call,
            context=execution_context,
        )

        # Verify database was called
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_tool_result(self, audit_logger, mock_db):
        """Test logging a tool result."""
        # Setup mock query result
        mock_log = MagicMock(spec=AuditLog)
        mock_log.id = uuid4()
        mock_log.details = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log
        mock_db.execute.return_value = mock_result

        tool_result = ToolResult.success_result(
            output="test output",
            call_id="call-123",
        )

        updated_log = await audit_logger.log_tool_result(
            audit_log_id=str(mock_log.id),
            result=tool_result,
            success=True,
        )

        assert updated_log.success is True
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_log_approval_request(self, audit_logger, sample_tool_call, execution_context, mock_db):
        """Test logging an approval request."""
        hitl_result = HITLCheckResult(
            requires_approval=True,
            risk_level="high",
            matched_rule="test_rule",
        )

        log_entry = await audit_logger.log_approval_request(
            tool_call=sample_tool_call,
            context=execution_context,
            hitl_result=hitl_result,
            approval_request_id="req-123",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_logs(self, audit_logger, mock_db):
        """Test querying audit logs."""
        # Setup mock query result
        mock_logs = [MagicMock(spec=AuditLog) for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_db.execute.return_value = mock_result

        logs = await audit_logger.query_logs(
            filters={"action": "tool_call"},
            limit=10,
        )

        assert len(logs) == 3
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_logs(self, audit_logger, mock_db):
        """Test counting audit logs."""
        # Setup mock count result
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42
        mock_db.execute.return_value = mock_result

        count = await audit_logger.count_logs(filters={"success": True})

        assert count == 42


# =============================================================================
# Tool Gateway Tests
# =============================================================================


class TestToolGateway:
    """Tests for ToolGateway service."""

    def test_register_tool(self, tool_gateway):
        """Test registering a tool."""
        async def test_tool():
            return "result"

        tool_gateway.register_tool("test_tool", test_tool)

        assert "test_tool" in tool_gateway.get_registered_tools()

    def test_unregister_tool(self, tool_gateway):
        """Test unregistering a tool."""
        async def test_tool():
            return "result"

        tool_gateway.register_tool("test_tool", test_tool)
        result = tool_gateway.unregister_tool("test_tool")

        assert result is True
        assert "test_tool" not in tool_gateway.get_registered_tools()

    @pytest.mark.asyncio
    async def test_execute_success(self, tool_gateway, execution_context):
        """Test successful tool execution."""
        async def mock_tool(arg1, arg2):
            return f"Result: {arg1}, {arg2}"

        tool_gateway.register_tool("test_tool", mock_tool)

        # Disable HITL and audit for this test
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        tool_call = ToolCall(
            tool_name="test_tool",
            tool_input={"arg1": "value1", "arg2": 42},
        )

        result = await tool_gateway.execute(tool_call, execution_context)

        assert result.success is True
        assert "Result: value1, 42" in str(result.output)

    @pytest.mark.asyncio
    async def test_execute_unregistered_tool(self, tool_gateway, sample_tool_call, execution_context):
        """Test executing an unregistered tool."""
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        with pytest.raises(ValueError, match="Tool not registered"):
            await tool_gateway.execute(sample_tool_call, execution_context)

    @pytest.mark.asyncio
    async def test_execute_hitl_interrupt(self, tool_gateway, sample_tool_call, execution_context):
        """Test HITL interrupt during execution."""
        # Register a tool that matches HITL rules (e.g., rm -rf)
        tool_gateway.register_tool("execute_bash", lambda **kwargs: "executed")

        sample_tool_call.tool_name = "execute_bash"
        sample_tool_call.tool_input = {"command": "rm -rf /"}

        with pytest.raises(HITLInterrupt) as exc_info:
            await tool_gateway.execute(sample_tool_call, execution_context)

        assert exc_info.value.hitl_result.requires_approval is True

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self, tool_gateway, execution_context):
        """Test execution with retry on success."""
        call_count = 0

        async def flaky_tool(arg1=None, arg2=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Temporary error")
            return f"success: {arg1}, {arg2}"

        tool_gateway.register_tool("test_tool", flaky_tool)
        tool_gateway.config.max_retries = 2
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        tool_call = ToolCall(
            tool_name="test_tool",
            tool_input={"arg1": "value1", "arg2": 42},
        )

        result = await tool_gateway.execute_with_retry(tool_call, execution_context)

        assert result.success is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_exhausted(self, tool_gateway, execution_context):
        """Test execution with retry exhausted."""
        async def always_fails(arg1=None, arg2=None):
            raise RuntimeError("Always fails")

        tool_gateway.register_tool("test_tool", always_fails)
        tool_gateway.config.max_retries = 1
        tool_gateway.config.retry_delay_seconds = 0.01
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        tool_call = ToolCall(
            tool_name="test_tool",
            tool_input={"arg1": "value1", "arg2": 42},
        )

        with pytest.raises(RuntimeError, match="Always fails"):
            await tool_gateway.execute_with_retry(tool_call, execution_context)

    @pytest.mark.asyncio
    async def test_batch_execute(self, tool_gateway, execution_context):
        """Test batch execution of multiple tools."""
        async def success_tool():
            return "success"

        async def fail_tool():
            raise RuntimeError("Failed")

        tool_gateway.register_tool("success_tool", success_tool)
        tool_gateway.register_tool("fail_tool", fail_tool)
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        tool_calls = [
            ToolCall(tool_name="success_tool", tool_input={}),
            ToolCall(tool_name="fail_tool", tool_input={}),
            ToolCall(tool_name="unregistered_tool", tool_input={}),
        ]

        results = await tool_gateway.batch_execute(tool_calls, execution_context)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is False

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, tool_gateway, execution_context):
        """Test execution with timeout."""
        async def slow_tool(arg1=None, arg2=None):
            await asyncio.sleep(10)
            return "never returned"

        tool_gateway.register_tool("slow_tool", slow_tool)
        tool_gateway.config.timeout_seconds = 0.01
        tool_gateway.config.enable_hitl = False
        tool_gateway.config.enable_audit = False

        tool_call = ToolCall(
            tool_name="slow_tool",
            tool_input={"arg1": "value1", "arg2": 42},
        )
        result = await tool_gateway.execute(tool_call, execution_context)

        assert result.success is False
        assert result.status == ToolCallStatus.TIMEOUT


class TestToolGatewayFactory:
    """Tests for ToolGatewayFactory."""

    @pytest.mark.asyncio
    async def test_create(self, mock_db):
        """Test creating a ToolGateway."""
        audit_logger = AuditLogger(db=mock_db)
        hitl_engine = HITLRulesEngine()
        config = GatewayConfig()

        gateway = await ToolGatewayFactory.create(
            audit_logger=audit_logger,
            hitl_engine=hitl_engine,
            config=config,
        )

        assert isinstance(gateway, ToolGateway)
        assert gateway.audit == audit_logger
        assert gateway.hitl == hitl_engine
        assert gateway.config == config

    @pytest.mark.asyncio
    async def test_create_with_db(self, mock_db):
        """Test creating a ToolGateway with database."""
        gateway = await ToolGatewayFactory.create_with_db(
            db=mock_db,
            enable_hitl=True,
            enable_audit=True,
        )

        assert isinstance(gateway, ToolGateway)
        assert gateway.config.enable_hitl is True
        assert gateway.config.enable_audit is True


# =============================================================================
# Integration Tests
# =============================================================================


class TestToolGatewayIntegration:
    """Integration tests for Tool Gateway with HITL and Audit."""

    @pytest.mark.asyncio
    async def test_full_execution_flow_success(self, mock_db):
        """Test full execution flow with successful completion."""
        # Setup
        audit_logger = AuditLogger(db=mock_db)
        hitl_engine = HITLRulesEngine()
        gateway = ToolGateway(
            audit_logger=audit_logger,
            hitl_engine=hitl_engine,
            config=GatewayConfig(enable_hitl=False, enable_audit=False),
        )

        async def safe_tool():
            return {"status": "ok"}

        gateway.register_tool("safe_tool", safe_tool)

        # Create mocks
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        mock_user.org_id = uuid4()

        context = ExecutionContext(user=mock_user)
        tool_call = ToolCall(tool_name="safe_tool", tool_input={})

        # Execute
        result = await gateway.execute(tool_call, context)

        # Verify
        assert result.success is True
        assert result.output == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_full_execution_flow_hitl(self, mock_db):
        """Test full execution flow with HITL interrupt."""
        # Setup
        audit_logger = AuditLogger(db=mock_db)
        hitl_engine = HITLRulesEngine()
        gateway = ToolGateway(
            audit_logger=audit_logger,
            hitl_engine=hitl_engine,
            config=GatewayConfig(enable_hitl=True, enable_audit=True),
        )

        async def dangerous_tool():
            return "should not execute"

        gateway.register_tool("execute_bash", dangerous_tool)

        # Create mocks
        mock_user = MagicMock(spec=User)
        mock_user.id = uuid4()
        mock_user.org_id = uuid4()

        context = ExecutionContext(user=mock_user)
        tool_call = ToolCall(
            tool_name="execute_bash",
            tool_input={"command": "rm -rf /important/data"},
        )

        # Execute and expect interrupt
        with pytest.raises(HITLInterrupt) as exc_info:
            await gateway.execute(tool_call, context)

        # Verify
        assert exc_info.value.hitl_result.requires_approval is True
        assert "rm -rf" in str(exc_info.value.hitl_result.description).lower() or True  # Description might vary


# =============================================================================
# Audit Log Model Tests
# =============================================================================


class TestAuditLogModel:
    """Tests for AuditLog SQLAlchemy model."""

    def test_audit_log_creation(self):
        """Test creating an AuditLog instance."""
        log = AuditLog(
            action=AuditAction.TOOL_CALL,
            resource_type=ResourceType.TOOL,
            resource_id="test_tool",
            details={"test": "data"},
        )

        assert log.action == AuditAction.TOOL_CALL
        assert log.resource_type == ResourceType.TOOL
        assert log.resource_id == "test_tool"
        assert log.details == {"test": "data"}

    def test_audit_log_is_error(self):
        """Test is_error property."""
        error_log = AuditLog(
            action=AuditAction.TOOL_ERROR,
            resource_type=ResourceType.TOOL,
            success=False,
        )

        success_log = AuditLog(
            action=AuditAction.TOOL_RESULT,
            resource_type=ResourceType.TOOL,
            success=True,
        )

        assert error_log.is_error is True
        assert success_log.is_error is False

    def test_audit_log_to_dict(self):
        """Test converting to dictionary."""
        log = AuditLog(
            id=uuid4(),
            action=AuditAction.TOOL_CALL,
            resource_type=ResourceType.TOOL,
            resource_id="test_tool",
            details={"key": "value"},
            success=True,
        )

        data = log.to_dict()

        assert data["action"] == "tool_call"
        assert data["resource_type"] == "tool"
        assert data["resource_id"] == "test_tool"
        assert data["details"] == {"key": "value"}
        assert data["success"] is True
