from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DECIMAL,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from apx.data.schemas import Currency, ValidationStatus


class Base(DeclarativeBase):
    pass


class InvoiceORM(Base):
    """ORM model for submitted invoices."""

    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    po_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    invoice_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(DECIMAL(18, 2), default=Decimal("0"))
    payload_json: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    ground_truth: Mapped[Optional["GroundTruthORM"]] = relationship(
        back_populates="invoice", uselist=False, cascade="all, delete-orphan"
    )
    case: Mapped[Optional["CaseORM"]] = relationship(
        back_populates="invoice", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_invoices_vendor_date", "vendor_id", "invoice_date"),
        Index("ix_invoices_po_number", "po_number"),
    )


class GroundTruthORM(Base):
    """ORM model for ground truth labels."""

    __tablename__ = "ground_truth"

    invoice_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), primary_key=True
    )
    expected_exceptions: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    expected_decision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    injected_exceptions: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    invoice: Mapped["InvoiceORM"] = relationship(back_populates="ground_truth")


class CaseORM(Base):
    """ORM model for case processing lifecycle."""

    __tablename__ = "cases"

    case_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    invoice_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("invoices.invoice_id", ondelete="CASCADE"), unique=True, index=True
    )
    vendor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW", index=True)
    current_phase: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    exception_codes: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    validation_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    valid_evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    risk_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(4, 3), nullable=True)
    investigation_outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    investigation_findings: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    investigation_budget_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    investigation_budget_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    investigation_steps: Mapped[List[Dict[str, Any]]] = mapped_column(SQLiteJSON, default=list)
    action_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    action_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    guardrail_decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    guardrail_checks: Mapped[List[Dict[str, Any]]] = mapped_column(SQLiteJSON, default=list)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    invoice: Mapped["InvoiceORM"] = relationship(back_populates="case")
    approval: Mapped[Optional["ApprovalORM"]] = relationship(
        back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    action: Mapped[Optional["ActionORM"]] = relationship(
        back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["AuditEventORM"]] = relationship(
        back_populates="case", cascade="save-update, merge, refresh-expire, expunge"
    )

    __table_args__ = (
        Index("ix_cases_status_updated", "status", "updated_at"),
        Index("ix_cases_vendor_status", "vendor_id", "status"),
    )


class ApprovalORM(Base):
    """ORM model for human approval workflow."""

    __tablename__ = "approvals"

    approval_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, index=True
    )
    action_plan_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    required_approvers: Mapped[List[str]] = mapped_column(SQLiteJSON, default=list)
    approvals_json: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["CaseORM"] = relationship(back_populates="approval")

    __table_args__ = (
        Index("ix_approvals_status", "status"),
    )


class ActionORM(Base):
    """ORM model for executed actions."""

    __tablename__ = "actions"

    action_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.case_id", ondelete="CASCADE"), unique=True, index=True
    )
    approval_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("approvals.approval_id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, default=dict)
    risk_score: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(4, 3), nullable=True)
    guardrail_decision: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    guardrail_checks: Mapped[List[Dict[str, Any]]] = mapped_column(SQLiteJSON, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(SQLiteJSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    case: Mapped["CaseORM"] = relationship(back_populates="action")

    __table_args__ = (
        Index("ix_actions_status", "status"),
        Index("ix_actions_type_status", "action_type", "status"),
    )


class AuditEventORM(Base):
    """ORM model for immutable audit event log."""

    __tablename__ = "audit_events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("cases.case_id", ondelete="RESTRICT"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phase: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    component: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(SQLiteJSON, default=dict)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    case: Mapped["CaseORM"] = relationship(back_populates="audit_events")

    __table_args__ = (
        Index("ix_audit_case_created", "case_id", "created_at"),
        Index("ix_audit_type_created", "event_type", "created_at"),
        Index("ix_audit_request_correlation", "request_id", "correlation_id"),
    )