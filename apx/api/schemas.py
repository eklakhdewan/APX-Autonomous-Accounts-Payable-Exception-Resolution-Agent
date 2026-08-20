from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ErrorResponse(BaseModel):
    """Standard error response schema (RFC 7807 inspired)."""
    error: str
    message: str
    request_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    ready: bool
    checks: dict[str, bool]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str


# Invoice schemas
class InvoiceLineRequest(BaseModel):
    """Invoice line item in request."""
    line_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    po_line_id: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    @field_validator("quantity", "unit_price", "discount", "tax_rate", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price) - self.discount

    def line_tax(self) -> Decimal:
        return self.line_total() * self.tax_rate


class InvoiceRequest(BaseModel):
    """Request schema for submitting an invoice."""
    invoice_id: str = Field(..., min_length=1)
    vendor_id: str = Field(..., min_length=1)
    invoice_number: str = Field(..., min_length=1)
    po_number: Optional[str] = None
    invoice_date: str  # ISO date string
    due_date: str  # ISO date string
    currency: str = Field(..., min_length=3, max_length=3)
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    line_items: list[InvoiceLineRequest] = Field(default_factory=list)

    @field_validator("subtotal", "tax", "total", "discount", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v):
        return v.upper()


class InvoiceLineResponse(BaseModel):
    """Invoice line item in response."""
    line_id: str
    description: str
    po_line_id: Optional[str]
    quantity: Decimal
    unit_price: Decimal
    discount: Decimal
    tax_rate: Decimal
    line_total: Decimal
    line_tax: Decimal


class InvoiceResponse(BaseModel):
    """Response schema for invoice."""
    invoice_id: str
    vendor_id: str
    invoice_number: str
    po_number: Optional[str]
    invoice_date: str
    due_date: str
    currency: str
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    discount: Decimal
    line_items: list[InvoiceLineResponse]
    created_at: datetime


# Case schemas
class CaseResponse(BaseModel):
    """Case processing state response."""
    case_id: str
    invoice_id: str
    vendor_id: str
    status: str
    current_phase: Optional[str]
    exception_codes: list[str]
    validation_status: Optional[str]
    evidence_count: int
    valid_evidence_count: int
    risk_level: Optional[str]
    risk_score: Optional[str]
    investigation_outcome: Optional[str]
    investigation_findings: Optional[str]
    investigation_budget_limit: Optional[int]
    investigation_budget_used: Optional[int]
    action_type: Optional[str]
    action_status: Optional[str]
    guardrail_decision: Optional[str]
    idempotency_key: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


# Approval schemas
class ApproveRequest(BaseModel):
    """Request to approve a case."""
    approver_id: str
    notes: Optional[str] = ""


class RejectRequest(BaseModel):
    """Request to reject a case."""
    approver_id: str
    notes: str


class ApprovalResponse(BaseModel):
    """Approval response."""
    approval_id: str
    case_id: str
    action_type: str
    risk_level: str
    status: str
    required_approvers: list[str]
    approvals: dict[str, dict]
    requested_by: str
    requested_at: datetime
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    notes: Optional[str]


# Approval schemas
class AuditEventResponse(BaseModel):
    """Audit event response."""
    event_id: str
    case_id: str
    event_type: str
    phase: Optional[str]
    component: Optional[str]
    payload: dict[str, Any]
    metadata: dict[str, Any]
    request_id: Optional[str]
    correlation_id: Optional[str]
    user_id: Optional[str]
    duration_ms: Optional[float]
    created_at: datetime


# Process schemas
class ProcessResponse(BaseModel):
    """Response for invoice processing."""
    case_id: str
    invoice_id: str
    status: str
    current_phase: str
    exception_codes: list[str]
    investigation_outcome: Optional[str]
    risk_level: Optional[str]
    risk_score: Optional[str]
    action_type: Optional[str]
    action_status: Optional[str]
    guardrail_decision: Optional[str]
    processing_time_ms: float


# Invoice submission response
class InvoiceSubmitResponse(BaseModel):
    """Response for invoice submission."""
    invoice_id: str
    case_id: str
    status: str
    message: str


# Metrics response
class MetricsResponse(BaseModel):
    """Metrics response."""
    metrics: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Error response models
class ValidationErrorDetail(BaseModel):
    """Validation error detail."""
    field: str
    message: str
    value: Any = None


class ValidationErrorResponse(ErrorResponse):
    """Validation error response (422)."""
    error: str = "validation_error"
    details: list[ValidationErrorDetail] = Field(default_factory=list)


# Idempotency
class IdempotencyResponse(BaseModel):
    """Response for idempotent operations."""
    idempotency_key: str
    already_processed: bool
    original_response: Optional[dict[str, Any]] = None