from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from apx.action.models import ActionPlan, ActionType, ActionStatus, ApprovalStatus
from apx.action.pipeline import Phase4Pipeline
from apx.agent.controller import run_investigation
from apx.agent.models import InvestigationResult
from apx.data.schemas import Invoice, ExceptionReport
from apx.api.schemas import InvoiceLineResponse
from apx.evidence.engine import HybridContextEngine
from apx.evidence.schemas import EvidenceSet
from apx.intelligence.validator import InvoiceValidator
from apx.persistence import (
    InvoiceRepository,
    CaseRepository,
    ApprovalRepository,
    ActionRepository,
    AuditRepository,
)
from apx.persistence.database import init_database, get_session_factory
from apx.persistence.models import InvoiceORM, CaseORM, GroundTruthORM
from apx.config.settings import get_settings
from apx.data.generate_synthetic import SyntheticGenerator


class InvoiceService:
    """Service for invoice operations."""

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
        validator: InvoiceValidator,
        evidence_engine: HybridContextEngine,
        pipeline: Phase4Pipeline,
    ):
        self.invoice_repo = invoice_repo
        self.case_repo = case_repo
        self.audit_repo = audit_repo
        self.validator = validator
        self.evidence_engine = evidence_engine
        self.pipeline = pipeline
        self.logger = logging.getLogger("apx.application.services.invoice")

    def submit_invoice(self, invoice: Any, idempotency_key: Optional[str] = None) -> dict[str, Any]:
        """Submit an invoice for processing."""
        # Check if invoice already exists
        if self.invoice_repo.exists(invoice.invoice_id):
            return {
                "invoice_id": invoice.invoice_id,
                "case_id": None,
                "status": "already_exists",
                "message": f"Invoice {invoice.invoice_id} already exists",
            }

        # Create invoice in persistence
        self.invoice_repo.create(invoice)

        # Create case
        case_id = uuid4()
        self.case_repo.create(case_id, invoice.invoice_id, invoice.vendor_id, idempotency_key)

        # Log audit event
        self.audit_repo.log(
            case_id=case_id,
            event_type="INVOICE_SUBMITTED",
            phase="phase1",
            component="invoice_service",
            payload={
                "invoice_id": invoice.invoice_id,
                "vendor_id": invoice.vendor_id,
                "total": str(invoice.total),
            },
            request_id=None,
            correlation_id=None,
        )

        return {
            "invoice_id": invoice.invoice_id,
            "case_id": str(case_id),
            "status": "submitted",
            "message": "Invoice submitted successfully",
        }

    def get_invoice(self, invoice_id: str) -> Optional[dict[str, Any]]:
        """Get invoice with case status."""
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            return None

        case = self.case_repo.get_by_invoice(invoice_id)

        # Build response matching InvoiceResponse schema
        result = {
            "invoice_id": invoice.invoice_id,
            "vendor_id": invoice.vendor_id,
            "invoice_number": invoice.invoice_number,
            "po_number": invoice.po_number,
            "invoice_date": str(invoice.invoice_date),
            "due_date": str(invoice.due_date),
            "currency": invoice.currency.value,
            "subtotal": invoice.subtotal,
            "tax": invoice.tax,
            "total": invoice.total,
            "discount": invoice.discount,
            "line_items": [
                InvoiceLineResponse(
                    line_id=line.line_id,
                    description=line.description,
                    po_line_id=line.po_line_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    tax_rate=line.tax_rate,
                    line_total=line.line_total(),
                    line_tax=line.line_tax(),
                )
                for line in invoice.line_items
            ],
            "created_at": invoice.created_at,
        }
        if case:
            result["case"] = case
        return result

    def process_invoice(self, invoice_id: str, idempotency_key: Optional[str] = None) -> dict[str, Any]:
        """Process an invoice through the full APX pipeline."""
        start_time = datetime.utcnow()

        # Get invoice
        invoice = self.invoice_repo.get(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Get related entities for validation
        generator = SyntheticGenerator(seed=42)
        generator.generate_vendors(count=35)
        generator.generate_purchase_orders(count=100)
        generator.generate_goods_receipts(count=88)
        generator.generate_invoices(count=500, multi_exception_rate=0.15)

        po = next((p for p in generator.purchase_orders if p.po_number == invoice.po_number), None)
        grn = next((g for g in generator.goods_receipts if g.po_id == po.po_id), None) if po else None
        vendor = next((v for v in generator.vendors if v.vendor_id == invoice.vendor_id), None)

        if not vendor:
            raise ValueError(f"Vendor {invoice.vendor_id} not found")

        # Get or create case
        case = self.case_repo.get_by_invoice(invoice_id)
        if not case:
            raise ValueError(f"Case for invoice {invoice_id} not found")
        case_id = UUID(case["case_id"])

        # Phase 1: Validation
        self.logger.info(f"Phase 1: Validating invoice {invoice_id}")
        self.case_repo.update_status(UUID(case["case_id"]), "VALIDATING", current_phase="phase1")

        exception_report = self.validator.validate_invoice(
            invoice=invoice, po=po, grn=grn, vendor=vendor
        )

        # Log validation complete
        self.audit_repo.log(
            case_id=UUID(case["case_id"]),
            event_type="VALIDATION_COMPLETE",
            phase="phase1",
            component="validator",
            payload={
                "invoice_id": invoice_id,
                "exception_codes": [e.value for e in exception_report.exception_codes],
                "validation_status": exception_report.validation_status.value,
            },
        )

        self.case_repo.update_phase1_result(
            UUID(case["case_id"]),
            [e.value for e in exception_report.exception_codes],
            exception_report.validation_status.value,
        )

        # Phase 2: Evidence Retrieval
        self.logger.info(f"Phase 2: Retrieving evidence for {invoice_id}")
        evidence_set = self.evidence_engine.retrieve(exception_report)

        self.audit_repo.log(
            case_id=UUID(case["case_id"]),
            event_type="RETRIEVAL_COMPLETE",
            phase="phase2",
            component="evidence_engine",
            payload={
                "invoice_id": invoice_id,
                "evidence_count": len(evidence_set.candidates),
                "valid_evidence_count": evidence_set.valid_count,
            },
        )

        self.case_repo.update_phase2_result(
            UUID(case["case_id"]),
            len(evidence_set.candidates),
            evidence_set.valid_count,
        )

        # Phase 3: Investigation
        self.logger.info(f"Phase 3: Investigating {invoice_id}")
        investigation_result = run_investigation(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=10,
        )

        self.audit_repo.log(
            case_id=UUID(case["case_id"]),
            event_type="INVESTIGATION_COMPLETE",
            phase="phase3",
            component="agent",
            payload={
                "invoice_id": invoice_id,
                "outcome": investigation_result.outcome.value if investigation_result.outcome else "UNKNOWN",
                "evidence_ids": investigation_result.evidence_ids,
                "budget_used": investigation_result.budget_used,
            },
        )

        self.case_repo.update_phase3_result(UUID(case["case_id"]), investigation_result)

        # Phase 4: Decision & Action
        self.logger.info(f"Phase 4: Decision & Action for {invoice_id}")
        action_plan = self.pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
            evidence_set=evidence_set,
        )

        self.audit_repo.log(
            case_id=UUID(case["case_id"]),
            event_type="DECISION_COMPLETE",
            phase="phase4",
            component="pipeline",
            payload={
                "invoice_id": invoice_id,
                "action_type": action_plan.action_type.value if hasattr(action_plan.action_type, 'value') else str(action_plan.action_type),
                "risk_level": str(action_plan.risk_assessment.risk_level) if action_plan.risk_assessment else "UNKNOWN",
                "guardrail_decision": action_plan.guardrail_decision.decision.value if hasattr(action_plan.guardrail_decision.decision, 'value') else str(action_plan.guardrail_decision.decision),
                "requires_approval": action_plan.guardrail_decision.requires_approval,
            },
        )

        self.case_repo.update_phase4_result(
            UUID(case["case_id"]),
            action_plan.risk_assessment,
            action_plan.guardrail_decision,
            action_plan,
        )

        # Execute if approved
        action_result = None
        if action_plan.status in ["APPROVED", "EXECUTING"]:
            self.logger.info(f"Executing action for {invoice_id}")
            action_result = self.pipeline.execute_action(action_plan)

            self.audit_repo.log(
                case_id=UUID(case["case_id"]),
                event_type="ACTION_EXECUTED",
                phase="phase4",
                component="action_executor",
                payload={
                    "invoice_id": invoice_id,
                    "action_type": action_plan.action_type.value if hasattr(action_plan.action_type, 'value') else str(action_plan.action_type),
                    "success": action_result.success if action_result else False,
                    "error": action_result.error_message if action_result and not action_result.success else None,
                },
            )

        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        # Update case status
        self.case_repo.update_status(UUID(case["case_id"]), "COMPLETED", completed_at=datetime.utcnow())

        return {
            "case_id": str(case["case_id"]),
            "invoice_id": invoice_id,
            "status": "completed",
            "current_phase": "phase4",
            "exception_codes": [e.value for e in exception_report.exception_codes],
            "investigation_outcome": investigation_result.outcome.value if investigation_result.outcome else "UNKNOWN",
            "risk_level": str(action_plan.risk_assessment.risk_level) if action_plan.risk_assessment else "UNKNOWN",
            "risk_score": str(action_plan.risk_assessment.overall_score) if action_plan.risk_assessment else "UNKNOWN",
            "action_type": action_plan.action_type.value if hasattr(action_plan.action_type, 'value') else str(action_plan.action_type),
            "action_status": action_plan.status.value if hasattr(action_plan.status, 'value') else str(action_plan.status),
            "guardrail_decision": action_plan.guardrail_decision.decision.value if hasattr(action_plan.guardrail_decision.decision, 'value') else str(action_plan.guardrail_decision.decision),
            "processing_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
        }

    def _request_to_invoice(self, request: Any) -> Any:
        """Convert API request to domain Invoice."""
        from apx.data.schemas import Invoice, InvoiceLine, Currency

        line_items = [
            InvoiceLine(
                line_id=line.line_id,
                description=line.description,
                po_line_id=line.po_line_id,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount=line.discount,
                tax_rate=line.tax_rate,
            )
            for line in request.line_items
        ]

        from apx.data.schemas import Invoice as InvoiceSchema, Currency
        return InvoiceSchema(
            invoice_id=request.invoice_id,
            vendor_id=request.vendor_id,
            invoice_number=request.invoice_number,
            po_number=request.po_number,
            invoice_date=request.invoice_date,
            due_date=request.due_date,
            currency=Currency(request.currency),
            subtotal=request.subtotal,
            tax=request.tax,
            total=request.total,
            discount=request.discount,
            line_items=[
                InvoiceLine(
                    line_id=line.line_id,
                    description=line.description,
                    po_line_id=line.po_line_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount=line.discount,
                    tax_rate=line.tax_rate,
                )
                for line in request.line_items
            ],
        )