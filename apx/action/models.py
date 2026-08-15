from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class ActionType(str, Enum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    REQUEST_INFORMATION = "REQUEST_INFORMATION"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    ADJUST_PAYMENT = "ADJUST_PAYMENT"
    VOID_INVOICE = "VOID_INVOICE"
    CONTACT_VENDOR = "CONTACT_VENDOR"
    UPDATE_RECORDS = "UPDATE_RECORDS"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ActionPlan(BaseModel):
    """Complete action plan including risk assessment and guardrail decision."""
    action_id: str = Field(default_factory=lambda: str(uuid4()))
    exception_id: str = ""
    action_type: ActionType
    target: str = ""  # e.g., invoice ID, vendor ID
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_assessment: Any = None  # RiskAssessment
    guardrail_decision: Any = None  # GuardrailDecisionResult
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    approval_requested_at: Optional[datetime] = None
    approval_resolved_at: Optional[datetime] = None
    approval_notes: str = ""
    idempotency_key: str = Field(default_factory=lambda: str(uuid4()))
    rate_limit_ok: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    investigation_result_ref: str = ""
    investigation_outcome: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    executed_by: str = ""
    execution_result: Optional[dict[str, Any]] = None
    error_message: str = ""
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionResult(BaseModel):
    """Result of action execution."""
    action_id: str
    success: bool
    result_data: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    executed_by: str = ""
    idempotency_key: str = ""
    dry_run: bool = False


class ApprovalRequest(BaseModel):
    """Request for human approval."""
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    action_plan_id: str
    action_type: str
    risk_level: str
    requested_by: str = "system"
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_by: str = ""
    resolved_at: Optional[datetime] = None
    resolution_notes: str = ""
    required_approvers: list[str] = Field(default_factory=list)
    approvals: dict[str, bool] = Field(default_factory=dict)  # approver_id -> approved


class ActionExecutorConfig(BaseModel):
    dry_run: bool = True
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    enable_compensation: bool = True
    enable_dead_letter_queue: bool = True


class DeadLetterEntry(BaseModel):
    """Entry in the dead letter queue for failed actions."""
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    action_id: str
    action_type: ActionType
    target: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    retry_count: int = 0
    last_attempt_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    compensation_attempted: bool = False
    compensation_result: Optional[dict[str, Any]] = None