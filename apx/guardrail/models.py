from __future__ import annotations

from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class GuardrailDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    BLOCK = "BLOCK"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActionType(str, Enum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    REQUEST_INFORMATION = "REQUEST_INFORMATION"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"
    ADJUST_PAYMENT = "ADJUST_PAYMENT"
    VOID_INVOICE = "VOID_INVOICE"
    CONTACT_VENDOR = "CONTACT_VENDOR"
    UPDATE_RECORDS = "UPDATE_RECORDS"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class GuardrailCheckResult(BaseModel):
    check_name: str
    passed: bool
    reason: str = ""
    severity: str = "INFO"  # INFO, WARNING, ERROR


class GuardrailDecisionResult(BaseModel):
    decision: GuardrailDecision
    action_type: ActionType
    checks: list[GuardrailCheckResult] = Field(default_factory=list)
    risk_level: str = ""
    requires_approval: bool = False
    approval_status: ApprovalStatus = ApprovalStatus.NOT_REQUIRED
    approval_reason: str = ""
    idempotency_key: str = ""
    rate_limit_ok: bool = True
    rate_limit_reason: str = ""
    block_reason: str = ""
    allowed_action_types: list[ActionType] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionPolicy(BaseModel):
    action_type: ActionType
    allowed_risk_levels: list[str] = Field(default_factory=list)
    requires_approval_above_risk: str = "MEDIUM"
    max_amount_without_approval: Decimal = Decimal("0")
    requires_idempotency: bool = True
    rate_limit_per_hour: int = 10
    required_evidence_min: int = 1
    required_approvals: list[str] = Field(default_factory=list)
    blocked_risk_levels: list[str] = Field(default_factory=list)


class ActionGuardrailConfig(BaseModel):
    policies: dict[str, ActionPolicy] = Field(default_factory=dict)
    default_policy: ActionPolicy = Field(default_factory=lambda: ActionPolicy(
        action_type=ActionType.MANUAL_REVIEW,
        allowed_risk_levels=["LOW", "MEDIUM"],
        requires_approval_above_risk="MEDIUM",
        max_amount_without_approval=Decimal("1000"),
        requires_idempotency=True,
        rate_limit_per_hour=10,
        required_evidence_min=1,
        required_approvals=[],
        blocked_risk_levels=["CRITICAL"],
    ))
    global_rate_limit_per_hour: int = 100
    idempotency_window_hours: int = 24