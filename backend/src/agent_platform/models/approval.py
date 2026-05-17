"""Approval models for HITL (Human-in-the-Loop) system."""

from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from agent_platform.database import Base

if TYPE_CHECKING:
    from agent_platform.models.org import Org, Team
    from agent_platform.models.session import Session
    from agent_platform.models.user import User


class RiskLevel(str, Enum):
    """Risk level enumeration for approval requests."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: "RiskLevel") -> bool:
        """Compare risk levels for ordering."""
        order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        return order[self] < order[other]

    def __gt__(self, other: "RiskLevel") -> bool:
        """Compare risk levels for ordering."""
        order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }
        return order[self] > order[other]

    def __le__(self, other: "RiskLevel") -> bool:
        return self == other or self < other

    def __ge__(self, other: "RiskLevel") -> bool:
        return self == other or self > other


class ApprovalStatus(str, Enum):
    """Approval status enumeration."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class ApprovalDecision(str, Enum):
    """Individual approval decision enumeration."""

    APPROVED = "approved"
    REJECTED = "rejected"
    ABSTAINED = "abstained"


class ApprovalStrategy(str, Enum):
    """Approval strategy enumeration."""

    SINGLE = "single"  # Any one approver can approve
    MULTI = "multi"  # Multiple approvers required
    ESCALATION = "escalation"  # Escalate if not approved in time
    CONSENSUS = "consensus"  # All approvers must approve


class ApprovalRequest(Base):
    """Approval request model for HITL system.

    Represents a request for human approval before executing a potentially
    dangerous or sensitive tool operation.
    """

    __tablename__ = "approval_requests"

    # Primary key
    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Foreign keys
    task_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # LangGraph checkpoint identifiers
    thread_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    checkpoint_ns: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        index=True,
    )
    checkpoint_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Tool information
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    tool_input: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    tool_input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Risk and description
    risk_level: Mapped[str] = mapped_column(
        String(20),
        default=RiskLevel.MEDIUM,
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    context_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    matched_rule_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("hitl_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Approval configuration
    approvers: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    strategy: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStrategy.SINGLE,
        nullable=False,
    )
    min_approvals_required: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Status and decisions
    status: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStatus.PENDING,
        nullable=False,
        index=True,
    )
    decisions: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Escalation configuration
    escalation_timeout_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    escalation_target_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
    )
    escalated_from_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalation_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="approval_requests")
    matched_rule: Mapped[Optional["HITLRule"]] = relationship("HITLRule", back_populates="approval_requests")
    escalated_from: Mapped[Optional["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        remote_side=[id],
        back_populates="escalated_to",
    )
    escalated_to: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        remote_side=[escalated_from_id],
        back_populates="escalated_from",
    )

    __table_args__ = (
        # Index for querying pending approvals efficiently
        {"sqlite_autoincrement": False},  # For SQLite compatibility
    )

    @property
    def is_expired(self) -> bool:
        """Check if the approval request has expired."""
        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    @property
    def is_pending(self) -> bool:
        """Check if the approval request is pending."""
        return self.status == ApprovalStatus.PENDING

    @property
    def is_decided(self) -> bool:
        """Check if the approval request has been decided."""
        return self.status in (
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
        )

    @property
    def requires_more_approvals(self) -> bool:
        """Check if more approvals are required.

        Returns True if the current number of approvals is less than
        the minimum required for the strategy.
        """
        if self.status != ApprovalStatus.PENDING:
            return False

        approved_count = sum(
            1 for d in self.decisions
            if d.get("decision") == ApprovalDecision.APPROVED
        )

        if self.strategy == ApprovalStrategy.SINGLE:
            return approved_count < 1
        elif self.strategy == ApprovalStrategy.MULTI:
            return approved_count < self.min_approvals_required
        elif self.strategy == ApprovalStrategy.CONSENSUS:
            return approved_count < len(self.approvers)
        else:
            return approved_count < 1

    @property
    def should_escalate(self) -> bool:
        """Check if the approval should be escalated.

        Returns True if escalation is configured and the timeout has passed.
        """
        if self.strategy != ApprovalStrategy.ESCALATION:
            return False

        if self.escalation_timeout_minutes is None:
            return False

        timeout = timedelta(minutes=self.escalation_timeout_minutes)
        elapsed = datetime.utcnow() - self.requested_at.replace(tzinfo=None)

        return elapsed > timeout

    @property
    def approval_count(self) -> int:
        """Get the number of approvals received."""
        return sum(
            1 for d in self.decisions
            if d.get("decision") == ApprovalDecision.APPROVED
        )

    @property
    def rejection_count(self) -> int:
        """Get the number of rejections received."""
        return sum(
            1 for d in self.decisions
            if d.get("decision") == ApprovalDecision.REJECTED
        )

    def add_decision(
        self,
        user_id: str,
        decision: ApprovalDecision,
        reason: Optional[str] = None,
    ) -> None:
        """Add a decision to the approval request.

        Args:
            user_id: ID of the user making the decision
            decision: The decision (approved/rejected/abstained)
            reason: Optional reason for the decision
        """
        decision_record = {
            "user_id": user_id,
            "decision": decision,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if reason:
            decision_record["reason"] = reason

        # Use reassignment for SQLAlchemy JSON change tracking
        self.decisions = [*self.decisions, decision_record]

        # Update status based on decision and strategy
        if decision == ApprovalDecision.REJECTED:
            self.status = ApprovalStatus.REJECTED
            self.decided_at = datetime.utcnow()
        elif decision == ApprovalDecision.APPROVED:
            if not self.requires_more_approvals:
                self.status = ApprovalStatus.APPROVED
                self.decided_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert approval request to dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "checkpoint_ns": self.checkpoint_ns,
            "checkpoint_id": self.checkpoint_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_input_hash": self.tool_input_hash,
            "risk_level": self.risk_level,
            "description": self.description,
            "context_summary": self.context_summary,
            "approvers": self.approvers,
            "strategy": self.strategy,
            "min_approvals_required": self.min_approvals_required,
            "status": self.status,
            "decisions": self.decisions,
            "approval_count": self.approval_count,
            "rejection_count": self.rejection_count,
            "is_expired": self.is_expired,
            "requires_more_approvals": self.requires_more_approvals,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


class HITLRule(Base):
    """HITL rule model for defining when human approval is required.

    Rules can be defined at the organization level or team level.
    """

    __tablename__ = "hitl_rules"

    # Primary key
    id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    # Ownership
    org_id: Mapped[str] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Rule configuration
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Matching criteria
    tool_name_pattern: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    argument_patterns: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    # Risk and approval configuration
    risk_level: Mapped[str] = mapped_column(
        String(20),
        default=RiskLevel.MEDIUM,
        nullable=False,
    )
    strategy: Mapped[str] = mapped_column(
        String(20),
        default=ApprovalStrategy.SINGLE,
        nullable=False,
    )
    min_approvals_required: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    # Default approvers (can be overridden at request time)
    default_approvers: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Escalation configuration
    escalation_enabled: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    escalation_timeout_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Rule status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="hitl_rules")
    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="hitl_rules")
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="matched_rule",
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert HITL rule to dictionary."""
        return {
            "id": self.id,
            "org_id": self.org_id,
            "team_id": self.team_id,
            "name": self.name,
            "description": self.description,
            "tool_name_pattern": self.tool_name_pattern,
            "argument_patterns": self.argument_patterns,
            "risk_level": self.risk_level,
            "strategy": self.strategy,
            "min_approvals_required": self.min_approvals_required,
            "default_approvers": self.default_approvers,
            "escalation_enabled": self.escalation_enabled,
            "escalation_timeout_minutes": self.escalation_timeout_minutes,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
