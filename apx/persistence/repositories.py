from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional, List, Dict
from uuid import UUID

from apx.data.schemas import Invoice, ExceptionCode, GroundTruth
from apx.agent.models import InvestigationResult, InvestigationStep
from apx.risk.models import RiskAssessment, RiskLevel
from apx.guardrail.models import GuardrailDecisionResult, ActionType, GuardrailDecision
from apx.action.models import ActionPlan, ActionResult, ApprovalRequest, ApprovalStatus
from apx.evidence.schemas import EvidenceSet


class InvoiceRepository(ABC):
    """Repository for invoice persistence."""

    @abstractmethod
    def create(self, invoice: Invoice, ground_truth: Optional[GroundTruth] = None) -> str:
        """Create a new invoice record. Returns invoice_id."""

    @abstractmethod
    def get(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID."""

    @abstractmethod
    def get_with_ground_truth(self, invoice_id: str) -> Optional[tuple[Invoice, Optional[GroundTruth]]]:
        """Get invoice with its ground truth."""

    @abstractmethod
    def exists(self, invoice_id: str) -> bool:
        """Check if invoice exists."""

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Invoice]:
        """List invoices with pagination."""

    @abstractmethod
    def delete(self, invoice_id: str) -> bool:
        """Delete invoice. Returns True if deleted."""


class CaseRepository(ABC):
    """Repository for case (processing lifecycle) persistence."""

    @abstractmethod
    def create(
        self,
        case_id: UUID,
        invoice_id: str,
        vendor_id: str,
        idempotency_key: Optional[str] = None,
    ) -> UUID:
        """Create a new case. Returns case_id."""

    @abstractmethod
    def get(self, case_id: UUID) -> Optional[Dict[str, Any]]:
        """Get case by ID."""

    @abstractmethod
    def get_by_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Get case by invoice ID."""

    @abstractmethod
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get case by idempotency key."""

    @abstractmethod
    def update_status(
        self,
        case_id: UUID,
        status: str,
        current_phase: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """Update case status and optional fields. Returns True if updated."""

    @abstractmethod
    def update_phase1_result(
        self,
        case_id: UUID,
        exception_codes: List[str],
        validation_status: str,
    ) -> bool:
        """Update case with Phase 1 validation results."""

    @abstractmethod
    def update_phase2_result(
        self,
        case_id: UUID,
        evidence_count: int,
        valid_evidence_count: int,
    ) -> bool:
        """Update case with Phase 2 retrieval results."""

    @abstractmethod
    def update_phase3_result(
        self,
        case_id: UUID,
        investigation_result: InvestigationResult,
    ) -> bool:
        """Update case with Phase 3 investigation results."""

    @abstractmethod
    def update_phase4_result(
        self,
        case_id: UUID,
        risk_assessment: RiskAssessment,
        guardrail_result: GuardrailDecisionResult,
        action_plan: ActionPlan,
    ) -> bool:
        """Update case with Phase 4 decision/action results."""

    @abstractmethod
    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List cases with optional status filter."""

    @abstractmethod
    def delete(self, case_id: UUID) -> bool:
        """Delete case. Returns True if deleted."""


class ApprovalRepository(ABC):
    """Repository for approval persistence."""

    @abstractmethod
    def create(self, approval: ApprovalRequest) -> UUID:
        """Create approval request. Returns approval_id."""

    @abstractmethod
    def get(self, approval_id: UUID) -> Optional[ApprovalRequest]:
        """Get approval by ID."""

    @abstractmethod
    def get_by_case(self, case_id: UUID) -> Optional[ApprovalRequest]:
        """Get approval by case ID."""

    @abstractmethod
    def update_status(
        self,
        approval_id: UUID,
        status: ApprovalStatus,
        approver_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> bool:
        """Update approval status. Returns True if updated."""

    @abstractmethod
    def add_approval(
        self,
        approval_id: UUID,
        approver_id: str,
        approved: bool,
        notes: Optional[str] = None,
    ) -> bool:
        """Record an individual approver's decision. Returns True if recorded."""

    @abstractmethod
    def list_pending(self, limit: int = 100, offset: int = 0) -> List[ApprovalRequest]:
        """List pending approvals."""

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[ApprovalRequest]:
        """List all approvals."""

    @abstractmethod
    def delete(self, approval_id: UUID) -> bool:
        """Delete approval. Returns True if deleted."""


class ActionRepository(ABC):
    """Repository for action execution persistence."""

    @abstractmethod
    def create(self, action_plan: ActionPlan) -> UUID:
        """Create action record. Returns action_id."""

    @abstractmethod
    def get(self, action_id: UUID) -> Optional[Dict[str, Any]]:
        """Get action by ID."""

    @abstractmethod
    def get_by_case(self, case_id: UUID) -> Optional[Dict[str, Any]]:
        """Get action by case ID."""

    @abstractmethod
    def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Get action by idempotency key."""

    @abstractmethod
    def update_execution(
        self,
        action_id: UUID,
        status: str,
        result: Optional[ActionResult] = None,
        error_message: Optional[str] = None,
        retry_count: Optional[int] = None,
    ) -> bool:
        """Update action execution status. Returns True if updated."""

    @abstractmethod
    def update_compensation(
        self,
        action_id: UUID,
        compensation_result: Dict[str, Any],
    ) -> bool:
        """Record compensation attempt. Returns True if recorded."""

    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all actions."""

    @abstractmethod
    def delete(self, action_id: UUID) -> bool:
        """Delete action. Returns True if deleted."""


class AuditRepository(ABC):
    """Repository for immutable audit event log."""

    @abstractmethod
    def log(
        self,
        case_id: UUID,
        event_type: str,
        phase: str,
        component: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ) -> UUID:
        """Log an audit event. Returns event_id."""

    @abstractmethod
    def get_by_case(
        self,
        case_id: UUID,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get audit events for a case."""

    @abstractmethod
    def get_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get audit events by type."""

    @abstractmethod
    def list_all(self, limit: int = 1000, offset: int = 0) -> List[Dict[str, Any]]:
        """List all audit events."""