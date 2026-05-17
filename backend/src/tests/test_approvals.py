"""Tests for HITL approval system."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_platform.auth.jwt import create_access_token
from agent_platform.agent.tools.hitl import HITLWrappedTool
from agent_platform.models.approval import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStrategy,
    HITLRule,
    RiskLevel,
)
from agent_platform.models.org import Org, Team
from agent_platform.models.session import Session
from agent_platform.models.user import User
from agent_platform.services.hitl_rules import HITLRulesEngine


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Org:
    """Create a test organization."""
    org = Org(
        id=str(uuid.uuid4()),
        name="Test Org",
        slug=f"test-org-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(org)
    await db_session.commit()
    return org


@pytest_asyncio.fixture
async def test_team(db_session: AsyncSession, test_org: Org) -> Team:
    """Create a test team."""
    team = Team(
        id=str(uuid.uuid4()),
        org_id=test_org.id,
        name="Test Team",
        slug="test-team",
    )
    db_session.add(team)
    await db_session.commit()
    return team


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_org: Org) -> User:
    """Create a test user."""
    user = User(
        id=str(uuid.uuid4()),
        org_id=test_org.id,
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_password",
        display_name="Test Approver",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
def approval_auth_headers(test_user: User) -> dict:
    """Create authentication headers for the approval test user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create a test session."""
    session = Session(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="Test Session",
        thread_id=f"thread-{uuid.uuid4()}",
    )
    db_session.add(session)
    await db_session.commit()
    return session


@pytest_asyncio.fixture
async def test_task_id() -> str:
    """Generate a test task ID."""
    return str(uuid.uuid4())


@pytest_asyncio.fixture
async def pending_approval(
    db_session: AsyncSession,
    test_user: User,
    test_session: Session,
    test_task_id: str,
) -> ApprovalRequest:
    """Create a pending approval request."""
    approval = ApprovalRequest(
        id=str(uuid.uuid4()),
        task_id=test_task_id,
        session_id=test_session.id,
        thread_id=test_session.thread_id,
        checkpoint_ns="test-checkpoint",
        tool_name="execute_bash",
        tool_input={"command": "rm -rf /important"},
        tool_input_hash="abc123",
        risk_level=RiskLevel.HIGH,
        description="Attempting to delete important files",
        context_summary="User requested file deletion",
        approvers=[{"user_id": test_user.id, "role": "admin"}],
        strategy=ApprovalStrategy.SINGLE,
        status=ApprovalStatus.PENDING,
        requested_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(approval)
    await db_session.commit()
    return approval


@pytest_asyncio.fixture
def hitl_rules_engine() -> HITLRulesEngine:
    """Create a HITL rules engine instance."""
    return HITLRulesEngine()


# =============================================================================
# Model Tests
# =============================================================================


class TestApprovalRequestModel:
    """Tests for ApprovalRequest model."""

    @pytest.mark.asyncio
    async def test_create_approval_request(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_session: Session,
        test_task_id: str,
    ):
        """Test creating an approval request."""
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            checkpoint_ns="test-checkpoint",
            tool_name="execute_bash",
            tool_input={"command": "ls -la"},
            tool_input_hash="hash123",
            risk_level=RiskLevel.MEDIUM,
            description="List directory contents",
            context_summary="User wants to see files",
            approvers=[{"user_id": test_user.id, "role": "admin"}],
            strategy=ApprovalStrategy.SINGLE,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db_session.add(approval)
        await db_session.commit()

        # Verify it was saved
        result = await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval.id)
        )
        saved = result.scalar_one()

        assert str(saved.id) == str(approval.id)
        assert str(saved.task_id) == test_task_id
        assert str(saved.session_id) == str(test_session.id)
        assert saved.tool_name == "execute_bash"
        assert saved.risk_level == RiskLevel.MEDIUM
        assert saved.status == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_approval_request_decisions(
        self,
        db_session: AsyncSession,
        pending_approval: ApprovalRequest,
        test_user: User,
    ):
        """Test adding decisions to an approval request."""
        # Add a decision
        pending_approval.decisions = [
            {
                "user_id": test_user.id,
                "decision": "approved",
                "reason": "Looks safe",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
        pending_approval.status = ApprovalStatus.APPROVED
        pending_approval.decided_at = datetime.utcnow()

        await db_session.commit()

        # Verify decision was saved
        result = await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == pending_approval.id)
        )
        saved = result.scalar_one()

        assert saved.status == ApprovalStatus.APPROVED
        assert len(saved.decisions) == 1
        assert saved.decisions[0]["decision"] == "approved"
        assert saved.decided_at is not None

    @pytest.mark.asyncio
    async def test_approval_request_is_expired(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_session: Session,
        test_task_id: str,
    ):
        """Test checking if an approval request is expired."""
        # Create an expired approval
        expired_approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "ls"},
            tool_input_hash="hash",
            risk_level=RiskLevel.LOW,
            status=ApprovalStatus.PENDING,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(expired_approval)
        await db_session.commit()

        assert expired_approval.is_expired is True

        # Create a non-expired approval
        valid_approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "ls"},
            tool_input_hash="hash2",
            risk_level=RiskLevel.LOW,
            status=ApprovalStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(valid_approval)
        await db_session.commit()

        assert valid_approval.is_expired is False

    @pytest.mark.asyncio
    async def test_approval_request_requires_approval(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_session: Session,
        test_task_id: str,
    ):
        """Test checking if approval requires more decisions."""
        # Single approval strategy with no decisions
        single_pending = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "ls"},
            tool_input_hash="hash",
            risk_level=RiskLevel.MEDIUM,
            strategy=ApprovalStrategy.SINGLE,
            status=ApprovalStatus.PENDING,
            approvers=[{"user_id": test_user.id}],
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(single_pending)
        await db_session.commit()

        assert single_pending.requires_more_approvals is True

        # Add a decision
        single_pending.decisions = [
            {"user_id": test_user.id, "decision": ApprovalDecision.APPROVED}
        ]
        single_pending.status = ApprovalStatus.APPROVED
        await db_session.commit()

        assert single_pending.requires_more_approvals is False


class TestHITLRuleModel:
    """Tests for HITLRule model."""

    @pytest.mark.asyncio
    async def test_create_hitl_rule(
        self,
        db_session: AsyncSession,
        test_org: Org,
    ):
        """Test creating a HITL rule."""
        rule = HITLRule(
            id=str(uuid.uuid4()),
            org_id=test_org.id,
            name="Block dangerous rm commands",
            description="Require approval for rm -rf commands",
            tool_name_pattern="execute_bash",
            argument_patterns={"command": "rm.*-rf.*"},
            risk_level=RiskLevel.HIGH,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        # Verify it was saved
        result = await db_session.execute(
            select(HITLRule).where(HITLRule.id == rule.id)
        )
        saved = result.scalar_one()

        assert saved.name == "Block dangerous rm commands"
        assert saved.tool_name_pattern == "execute_bash"
        assert saved.risk_level == RiskLevel.HIGH
        assert saved.is_active is True

    @pytest.mark.asyncio
    async def test_hitl_rule_team_specific(
        self,
        db_session: AsyncSession,
        test_org: Org,
        test_team: Team,
    ):
        """Test creating a team-specific HITL rule."""
        rule = HITLRule(
            id=str(uuid.uuid4()),
            org_id=test_org.id,
            team_id=test_team.id,
            name="Team-specific rule",
            description="Only applies to specific team",
            tool_name_pattern="write_file",
            risk_level=RiskLevel.MEDIUM,
            is_active=True,
        )
        db_session.add(rule)
        await db_session.commit()

        assert rule.team_id == test_team.id


# =============================================================================
# HITL Rules Engine Tests
# =============================================================================


class TestHITLRulesEngine:
    """Tests for HITLRulesEngine."""

    def test_default_rules_initialization(self, hitl_rules_engine: HITLRulesEngine):
        """Test that default rules are loaded."""
        assert len(hitl_rules_engine.default_rules) > 0

        # Check for critical command patterns
        rule_patterns = [r["tool_name_pattern"] for r in hitl_rules_engine.default_rules]
        assert "execute_bash" in rule_patterns

    def test_match_dangerous_rm_command(self, hitl_rules_engine: HITLRulesEngine):
        """Test matching dangerous rm commands."""
        tool_input = {"command": "rm -rf /important/data"}

        result = hitl_rules_engine.check_rules(
            tool_name="execute_bash",
            tool_input=tool_input,
        )

        assert result["requires_approval"] is True
        assert result["risk_level"] == RiskLevel.CRITICAL

    def test_match_dangerous_sql(self, hitl_rules_engine: HITLRulesEngine):
        """Test matching dangerous SQL commands."""
        tool_input = {"command": "DROP TABLE users;"}

        result = hitl_rules_engine.check_rules(
            tool_name="execute_sql",
            tool_input=tool_input,
        )

        assert result["requires_approval"] is True
        assert result["risk_level"] == RiskLevel.CRITICAL

    def test_no_match_for_safe_command(self, hitl_rules_engine: HITLRulesEngine):
        """Test that safe commands don't trigger approval."""
        tool_input = {"command": "ls -la"}

        result = hitl_rules_engine.check_rules(
            tool_name="execute_bash",
            tool_input=tool_input,
        )

        assert result["requires_approval"] is False

    def test_pattern_matching_with_regex(self, hitl_rules_engine: HITLRulesEngine):
        """Test regex pattern matching in rules."""
        # Should match DELETE pattern
        result = hitl_rules_engine.check_rules(
            tool_name="execute_sql",
            tool_input={"command": "DELETE FROM users WHERE id = 1"},
        )

        assert result["requires_approval"] is True

    def test_multiple_rules_match_highest_risk(self, hitl_rules_engine: HITLRulesEngine):
        """Test that when multiple rules match, highest risk is returned."""
        # This should match both a HIGH and CRITICAL pattern
        result = hitl_rules_engine.check_rules(
            tool_name="execute_bash",
            tool_input={"command": "rm -rf --no-preserve-root /"},
        )

        assert result["requires_approval"] is True
        # Should return CRITICAL as it's the highest risk
        assert result["risk_level"] == RiskLevel.CRITICAL


# =============================================================================
# HITLWrappedTool Tests
# =============================================================================


class TestHITLWrappedTool:
    """Tests for HITLWrappedTool."""

    def test_wrap_existing_tool(self):
        """Test wrapping an existing tool function."""
        def sample_tool(command: str) -> str:
            return f"Executed: {command}"

        wrapped = HITLWrappedTool(
            tool=sample_tool,
            tool_name="sample_tool",
            rules_engine=HITLRulesEngine(),
        )

        assert wrapped.tool_name == "sample_tool"
        assert wrapped.original_tool == sample_tool

    def test_check_rules_invoked(self):
        """Test that rules are checked when calling wrapped tool."""
        mock_rules_engine = MagicMock()
        mock_rules_engine.check_rules.return_value = {
            "requires_approval": True,
            "risk_level": RiskLevel.HIGH,
            "matched_rule": "test_rule",
        }

        def sample_tool(command: str) -> str:
            return f"Executed: {command}"

        wrapped = HITLWrappedTool(
            tool=sample_tool,
            tool_name="execute_bash",
            rules_engine=mock_rules_engine,
        )

        # Check rules method should be called
        result = wrapped.check_rules({"command": "rm -rf /"})

        mock_rules_engine.check_rules.assert_called_once_with(
            tool_name="execute_bash",
            tool_input={"command": "rm -rf /"},
        )
        assert result["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_interrupt_on_approval_required(self):
        """Test that tool interrupts when approval is required."""
        mock_rules_engine = MagicMock()
        mock_rules_engine.check_rules.return_value = {
            "requires_approval": True,
            "risk_level": RiskLevel.HIGH,
            "matched_rule": "dangerous_command",
            "description": "Dangerous command detected",
        }

        def sample_tool(command: str) -> str:
            return f"Executed: {command}"

        wrapped = HITLWrappedTool(
            tool=sample_tool,
            tool_name="execute_bash",
            rules_engine=mock_rules_engine,
        )

        # Mock LangGraph's interrupt since we're outside a runnable context
        with patch("agent_platform.agent.tools.hitl.interrupt") as mock_interrupt:
            mock_interrupt.side_effect = Exception("HITL approval required: interrupt")
            with pytest.raises(Exception) as exc_info:
                await wrapped(command="rm -rf /")

            # The exception should contain interrupt information
            assert "interrupt" in str(exc_info.value).lower() or "approval" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_when_no_approval_needed(self):
        """Test that tool executes normally when no approval is required."""
        mock_rules_engine = MagicMock()
        mock_rules_engine.check_rules.return_value = {
            "requires_approval": False,
            "risk_level": RiskLevel.LOW,
        }

        def sample_tool(command: str) -> str:
            return f"Executed: {command}"

        wrapped = HITLWrappedTool(
            tool=sample_tool,
            tool_name="execute_bash",
            rules_engine=mock_rules_engine,
        )

        result = await wrapped(command="ls -la")

        assert result == "Executed: ls -la"


# =============================================================================
# API Tests
# =============================================================================


class TestApprovalsAPI:
    """Tests for approvals API endpoints."""

    @pytest.mark.asyncio
    async def test_list_pending_approvals(
        self,
        client: AsyncClient,
        pending_approval: ApprovalRequest,
        approval_auth_headers: dict,
    ):
        """Test GET /approvals/pending endpoint."""
        response = await client.get("/api/v1/approvals/pending", headers=approval_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

        # Check that our pending approval is in the list
        approval_ids = [item["id"] for item in data["items"]]
        assert pending_approval.id in approval_ids

    @pytest.mark.asyncio
    async def test_get_approval_detail(
        self,
        client: AsyncClient,
        pending_approval: ApprovalRequest,
        approval_auth_headers: dict,
    ):
        """Test GET /approvals/{id} endpoint."""
        response = await client.get(f"/api/v1/approvals/{pending_approval.id}", headers=approval_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pending_approval.id
        assert data["tool_name"] == pending_approval.tool_name
        assert data["status"] == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_approval_not_found(self, client: AsyncClient, approval_auth_headers: dict):
        """Test GET /approvals/{id} with non-existent ID."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/v1/approvals/{fake_id}", headers=approval_auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_approval_decision(
        self,
        client: AsyncClient,
        pending_approval: ApprovalRequest,
        test_user: User,
        approval_auth_headers: dict,
    ):
        """Test POST /approvals/{id} endpoint."""
        decision_data = {
            "decision": "approved",
            "reason": "Looks safe to me",
        }

        response = await client.post(
            f"/api/v1/approvals/{pending_approval.id}",
            headers=approval_auth_headers,
            json=decision_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ApprovalStatus.APPROVED
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_submit_approval_uses_authenticated_user_not_body_user_id(
        self,
        client: AsyncClient,
        pending_approval: ApprovalRequest,
        test_user: User,
    ):
        """Test POST /approvals/{id} ignores forged body user_id."""
        forged_user_id = str(uuid.uuid4())
        token = create_access_token({"sub": str(test_user.id)})
        response = await client.post(
            f"/api/v1/approvals/{pending_approval.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "decision": "approved",
                "reason": "body user_id should be ignored",
                "user_id": forged_user_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["decisions"][0]["user_id"] == str(test_user.id)
        assert data["decisions"][0]["user_id"] != forged_user_id

    @pytest.mark.asyncio
    async def test_submit_rejection_decision(
        self,
        client: AsyncClient,
        pending_approval: ApprovalRequest,
        test_user: User,
        approval_auth_headers: dict,
    ):
        """Test rejecting an approval request."""
        decision_data = {
            "decision": "rejected",
            "reason": "Too dangerous",
        }

        response = await client.post(
            f"/api/v1/approvals/{pending_approval.id}",
            headers=approval_auth_headers,
            json=decision_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_list_approval_rules(self, client: AsyncClient, approval_auth_headers: dict):
        """Test GET /approvals/rules endpoint."""
        response = await client.get("/api/v1/approvals/rules", headers=approval_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "rules" in data
        assert "default_rules" in data
        assert data["total"] >= 0

    @pytest.mark.asyncio
    async def test_approval_history_route_is_not_captured_by_approval_id(self, client: AsyncClient, approval_auth_headers: dict):
        response = await client.get("/api/v1/approvals/history", headers=approval_auth_headers)
        assert response.status_code != 422

    @pytest.mark.asyncio
    async def test_approval_rules_route_is_not_captured_by_approval_id(self, client: AsyncClient, approval_auth_headers: dict):
        response = await client.get("/api/v1/approvals/rules", headers=approval_auth_headers)
        assert response.status_code != 422

    @pytest.mark.asyncio
    async def test_approval_expiration(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_session: Session,
        test_task_id: str,
        approval_auth_headers: dict,
    ):
        """Test that expired approvals cannot be decided."""
        # Create an expired approval
        expired_approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "rm -rf /"},
            tool_input_hash="hash",
            risk_level=RiskLevel.HIGH,
            status=ApprovalStatus.PENDING,
            approvers=[{"user_id": str(test_user.id), "role": "admin"}],
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add(expired_approval)
        await db_session.commit()

        # Try to submit a decision
        decision_data = {
            "decision": "approved",
            "reason": "Should fail - expired",
        }

        response = await client.post(
            f"/api/v1/approvals/{expired_approval.id}",
            headers=approval_auth_headers,
            json=decision_data,
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestHITLIntegration:
    """Integration tests for HITL system."""

    @pytest.mark.asyncio
    @patch("agent_platform.agent.factory.HITLWrappedTool")
    @patch("agent_platform.agent.factory.create_checkpointer")
    async def test_agent_creation_with_hitl(self, mock_create_checkpointer, mock_hitl_wrapper):
        """Test that agent can be created with HITL-enabled tools."""
        mock_hitl_wrapper.return_value = AsyncMock()
        mock_checkpointer = MagicMock()
        mock_create_checkpointer.return_value = mock_checkpointer

        # Import here to avoid circular imports
        from agent_platform.agent.factory import create_agent

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            agent, checkpointer = await create_agent(
                model_name="claude-sonnet-4-6",
                thread_id=f"test-thread-{uuid.uuid4()}",
                enable_hitl=True,
            )

        assert agent is not None
        assert checkpointer is not None

    @pytest.mark.asyncio
    async def test_interrupt_and_resume_flow(
        self,
        db_session: AsyncSession,
        test_session: Session,
        test_task_id: str,
        test_user: User,
    ):
        """Test the full interrupt and resume flow."""
        # This test simulates the complete HITL flow:
        # 1. Tool execution triggers interrupt
        # 2. Approval request is created
        # 3. Human approves
        # 4. Tool execution resumes

        # Step 1: Create approval request (simulating interrupt)
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            checkpoint_ns="test-checkpoint-ns",
            tool_name="execute_bash",
            tool_input={"command": "rm -rf /tmp/test"},
            tool_input_hash="hash123",
            risk_level=RiskLevel.HIGH,
            description="Delete test files",
            status=ApprovalStatus.PENDING,
            approvers=[{"user_id": test_user.id}],
            strategy=ApprovalStrategy.SINGLE,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db_session.add(approval)
        await db_session.commit()

        # Step 2: Verify it's pending
        assert approval.status == ApprovalStatus.PENDING

        # Step 3: Approve
        approval.decisions = [
            {
                "user_id": test_user.id,
                "decision": ApprovalDecision.APPROVED,
                "reason": "Test files can be deleted",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
        approval.status = ApprovalStatus.APPROVED
        approval.decided_at = datetime.utcnow()
        await db_session.commit()

        # Step 4: Verify approved
        result = await db_session.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval.id)
        )
        saved = result.scalar_one()

        assert saved.status == ApprovalStatus.APPROVED
        assert not saved.requires_more_approvals

    @pytest.mark.asyncio
    async def test_multi_approval_strategy(
        self,
        db_session: AsyncSession,
        test_session: Session,
        test_task_id: str,
        test_user: User,
    ):
        """Test multi-approval strategy requiring multiple approvers."""
        second_user = User(
            id=str(uuid.uuid4()),
            org_id=test_user.org_id,
            email="second@example.com",
        )
        db_session.add(second_user)
        await db_session.commit()

        # Create approval with multi strategy
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "deploy --production"},
            tool_input_hash="hash456",
            risk_level=RiskLevel.CRITICAL,
            description="Deploy to production",
            status=ApprovalStatus.PENDING,
            approvers=[
                {"user_id": test_user.id},
                {"user_id": second_user.id},
            ],
            strategy=ApprovalStrategy.MULTI,
            min_approvals_required=2,
            requested_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        db_session.add(approval)
        await db_session.commit()

        # First approval - should still require more
        approval.decisions = [
            {
                "user_id": test_user.id,
                "decision": ApprovalDecision.APPROVED,
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
        await db_session.commit()

        assert approval.requires_more_approvals is True

        # Second approval - should be complete
        approval.decisions.append(
            {
                "user_id": second_user.id,
                "decision": ApprovalDecision.APPROVED,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        approval.status = ApprovalStatus.APPROVED
        await db_session.commit()

        assert approval.requires_more_approvals is False

    @pytest.mark.asyncio
    async def test_escalation_strategy(
        self,
        db_session: AsyncSession,
        test_session: Session,
        test_task_id: str,
        test_user: User,
    ):
        """Test escalation strategy when no one approves in time."""
        # Create approval with escalation strategy
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id=test_session.thread_id,
            tool_name="execute_bash",
            tool_input={"command": "critical-operation"},
            tool_input_hash="hash789",
            risk_level=RiskLevel.CRITICAL,
            status=ApprovalStatus.PENDING,
            approvers=[{"user_id": test_user.id}],
            strategy=ApprovalStrategy.ESCALATION,
            escalation_timeout_minutes=5,
            requested_at=datetime.utcnow() - timedelta(minutes=10),  # Past escalation time
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(approval)
        await db_session.commit()

        # Check if should escalate
        assert approval.should_escalate is True


# =============================================================================
# Risk Level Tests
# =============================================================================


class TestRiskLevels:
    """Tests for risk level classification."""

    def test_risk_level_ordering(self):
        """Test that risk levels are properly ordered."""
        assert RiskLevel.LOW < RiskLevel.MEDIUM
        assert RiskLevel.MEDIUM < RiskLevel.HIGH
        assert RiskLevel.HIGH < RiskLevel.CRITICAL

    def test_risk_level_from_string(self):
        """Test creating risk level from string."""
        assert RiskLevel("low") == RiskLevel.LOW
        assert RiskLevel("medium") == RiskLevel.MEDIUM
        assert RiskLevel("high") == RiskLevel.HIGH
        assert RiskLevel("critical") == RiskLevel.CRITICAL


# =============================================================================
# Checkpoint Integration Tests
# =============================================================================


class TestCheckpointIntegration:
    """Tests for LangGraph checkpoint integration."""

    @pytest.mark.asyncio
    async def test_approval_request_stores_checkpoint(
        self,
        db_session: AsyncSession,
        test_session: Session,
        test_task_id: str,
    ):
        """Test that approval request stores checkpoint information."""
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            task_id=test_task_id,
            session_id=test_session.id,
            thread_id="thread-123",
            checkpoint_ns="checkpoint-ns-456",
            tool_name="execute_bash",
            tool_input={"command": "ls"},
            tool_input_hash="hash",
            risk_level=RiskLevel.LOW,
            status=ApprovalStatus.PENDING,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        db_session.add(approval)
        await db_session.commit()

        assert approval.thread_id == "thread-123"
        assert approval.checkpoint_ns == "checkpoint-ns-456"
