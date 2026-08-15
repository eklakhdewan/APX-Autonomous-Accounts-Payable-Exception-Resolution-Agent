from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import date

from apx.action.executor import ActionExecutor, ActionExecutorConfig
from apx.action.models import (
    ActionPlan, ActionResult, ActionType, ActionStatus, 
    ApprovalStatus, ActionExecutorConfig, DeadLetterEntry
)
from apx.approval.engine import ApprovalEngine
from apx.action.pipeline import Phase4Pipeline
from apx.risk.models import RiskAssessment, RiskLevel
from apx.guardrail.models import (
    GuardrailDecisionResult, GuardrailDecision, ActionType, 
    ApprovalStatus as GuardrailApprovalStatus, GuardrailCheckResult
)
from apx.agent.models import InvestigationResult, TerminalOutcome
from apx.agent.state_machine import AgentState
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.schemas import EvidenceSet, Evidence, EvidenceType, SourceAuthority, ValidatedEvidence, ValidityStatus


def create_test_risk_assessment(risk_level="LOW") -> RiskAssessment:
    """Create a test risk assessment."""
    return RiskAssessment(
        overall_score=Decimal("0.2") if risk_level == "LOW" else Decimal("0.5"),
        risk_level=RiskLevel(risk_level),
        dimension_scores=[],
        investigation_outcome="RESOLVE",
        evidence_ids=["EV-001"],
        calculation_metadata={},
        reasons=["Test"],
    )


def create_test_guardrail_result(decision="ALLOW", requires_approval=False) -> GuardrailDecisionResult:
    """Create a test guardrail decision result."""
    return GuardrailDecisionResult(
        decision=GuardrailDecision(decision),
        action_type=ActionType.AUTO_RESOLVE,
        checks=[],
        risk_level="LOW",
        requires_approval=requires_approval,
        approval_status=GuardrailApprovalStatus.PENDING if requires_approval else GuardrailApprovalStatus.NOT_REQUIRED,
    )


def create_test_action_plan(
    action_type=ActionType.AUTO_RESOLVE,
    approval_status=ApprovalStatus.NOT_REQUIRED,
    status=ActionStatus.PENDING,
) -> ActionPlan:
    """Create a test action plan."""
    return ActionPlan(
        action_id="test-action-1",
        exception_id="INV-001",
        action_type=action_type,
        target="INV-001",
        parameters={},
        risk_assessment=create_test_risk_assessment(),
        guardrail_decision=create_test_guardrail_result(),
        approval_status=approval_status,
        idempotency_key="test-key-1",
        rate_limit_ok=True,
        evidence_ids=["EV-001"],
        investigation_result_ref="INV-001",
        investigation_outcome="RESOLVE",
        status=status,
    )


def create_test_evidence_set() -> EvidenceSet:
    """Create a test evidence set."""
    evidence = Evidence(
        evidence_id="EV-00001",
        evidence_type="historical_resolution",
        scope="vendor_exception",
        scope_target="V-0001:AMOUNT_MISMATCH",
        vendor_id="V-0001",
        effective_from=date(2024, 1, 1),
        effective_until=date(2026, 12, 31),
        policy_version="v1.0",
        outcome="AUTO_APPROVED",
        source_authority=SourceAuthority.INTERNAL,
        usage_count=10,
        content="Historical resolution for AMOUNT_MISMATCH on vendor V-0001.",
    )
    validated_evidence = ValidatedEvidence(
        evidence=evidence,
        relevance_score=0.9,
        reranker_score=0.85,
        retrieval_sources=["BM25", "Dense"],
        rank=1,
        validity_status="valid",
        validity_reasons=[],
        scope_metadata={"scope": "vendor_exception"},
        source_authority=SourceAuthority.INTERNAL,
        content=evidence.content,
    )
    return EvidenceSet(
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exception_codes=["AMOUNT_MISMATCH"],
        query="test query",
        validated_evidence=[validated_evidence],
    )


def create_test_exception_report() -> ExceptionReport:
    """Create a test exception report."""
    return ExceptionReport(
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exceptions=[
            APException(
                exception_code=ExceptionCode.AMOUNT_MISMATCH,
                severity=ExceptionSeverity.MEDIUM,
                message="Test amount mismatch",
                details={"amount": "500"},
            ),
        ],
        validation_status=ValidationStatus.EXCEPTIONS,
    )


def create_test_investigation(outcome="RESOLVE") -> InvestigationResult:
    """Create a test investigation result."""
    return InvestigationResult(
        case_id="INV-TEST-001",
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exception_codes=["AMOUNT_MISMATCH"],
        final_state=AgentState.DECISION_READY,
        outcome=TerminalOutcome.RESOLVE if outcome == "RESOLVE" else TerminalOutcome.ESCALATE,
        evidence_ids=["EV-001"],
        findings="Test findings",
        steps=[],
        budget_limit=10,
        budget_used=3,
        termination_reason="Test completed",
    )


class TestActionExecutor:
    """Tests for ActionExecutor."""

    def test_executor_initialization(self):
        """Test executor initializes with default adapters."""
        executor = ActionExecutor()
        assert "AUTO_RESOLVE" in executor._adapters
        assert "REQUEST_INFORMATION" in executor._adapters
        assert "ESCALATE_TO_HUMAN" in executor._adapters
        assert "ADJUST_PAYMENT" in executor._adapters
        assert "VOID_INVOICE" in executor._adapters
        assert "CONTACT_VENDOR" in executor._adapters
        assert "UPDATE_RECORDS" in executor._adapters
        assert "MANUAL_REVIEW" in executor._adapters
        assert len(executor._compensation_adapters) == 8

    def test_register_custom_adapter(self):
        """Test registering a custom adapter."""
        executor = ActionExecutor()
        
        def custom_adapter(action_plan):
            return {"custom": True}
        
        executor.register_adapter("CUSTOM_ACTION", custom_adapter)
        assert "CUSTOM_ACTION" in executor._adapters
        assert executor._adapters["CUSTOM_ACTION"] == custom_adapter

    def test_register_compensation_adapter(self):
        """Test registering a custom compensation adapter."""
        executor = ActionExecutor()
        
        def custom_compensate(action_plan, error):
            return {"compensated": True}
        
        executor.register_compensation_adapter("CUSTOM_ACTION", custom_compensate)
        assert "CUSTOM_ACTION" in executor._compensation_adapters
        assert executor._compensation_adapters["CUSTOM_ACTION"] == custom_compensate

    def test_execute_approved_action_success(self):
        """Test successful execution of approved action."""
        executor = ActionExecutor()
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is True
        assert result.action_id == action_plan.action_id
        assert result.idempotency_key == action_plan.idempotency_key
        assert action_plan.status == ActionStatus.EXECUTED
        assert action_plan.execution_result is not None

    def test_execute_unapproved_action_fails(self):
        """Test execution fails when action not approved."""
        executor = ActionExecutor()
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.PENDING,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is False
        assert "not approved" in result.error_message.lower()
        assert action_plan.status == ActionStatus.PENDING

    def test_execute_blocked_by_guardrail_fails(self):
        """Test execution fails when guardrail blocks."""
        executor = ActionExecutor()
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        action_plan.guardrail_decision = create_test_guardrail_result(decision="BLOCK")
        
        result = executor.execute(action_plan)
        
        assert result.success is False
        assert "blocked by guardrail" in result.error_message.lower()

    def test_execute_with_retry_success_on_retry(self):
        """Test retry logic - succeeds on second attempt."""
        executor = ActionExecutor()
        call_count = [0]
        
        def flaky_adapter(action_plan):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First attempt fails")
            return {"success": True, "attempt": call_count[0]}
        
        executor.register_adapter("AUTO_RESOLVE", flaky_adapter)
        
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is True
        assert call_count[0] == 2
        assert action_plan.retry_count == 1

    def test_execute_all_retries_fail_triggers_compensation_and_dlq(self):
        """Test compensation and DLQ when all retries fail."""
        executor = ActionExecutor(config=ActionExecutorConfig(
            max_retries=2,
            retry_delay_seconds=0,
            enable_compensation=True,
            enable_dead_letter_queue=True,
        ))
        
        def always_fails_adapter(action_plan):
            raise Exception("Always fails")
        
        executor.register_adapter("AUTO_RESOLVE", always_fails_adapter)
        
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is False
        assert action_plan.status == ActionStatus.FAILED
        assert action_plan.error_message == "Always fails"
        
        dlq = executor.get_dead_letter_queue()
        assert len(dlq) == 1
        entry = dlq[0]
        assert entry.action_id == action_plan.action_id
        assert entry.compensation_attempted is True
        assert entry.compensation_result is not None
        assert entry.compensation_result["status"] == "success"

    def test_execute_compensation_failure_recorded_in_dlq(self):
        """Test DLQ records compensation failure."""
        executor = ActionExecutor(config=ActionExecutorConfig(
            max_retries=1,
            retry_delay_seconds=0,
            enable_compensation=True,
            enable_dead_letter_queue=True,
        ))
        
        def always_fails_adapter(action_plan):
            raise Exception("Always fails")
        
        def failing_compensate(action_plan, error):
            raise Exception("Compensation also fails")
        
        executor.register_adapter("AUTO_RESOLVE", always_fails_adapter)
        executor.register_compensation_adapter("AUTO_RESOLVE", failing_compensate)
        
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is False
        dlq = executor.get_dead_letter_queue()
        assert len(dlq) == 1
        entry = dlq[0]
        assert entry.compensation_attempted is True
        assert entry.compensation_result["status"] == "failed"
        assert "Compensation also fails" in entry.compensation_result["error"]

    def test_execute_disabled_compensation_no_dlq(self):
        """Test compensation and DLQ can be disabled."""
        executor = ActionExecutor(config=ActionExecutorConfig(
            max_retries=1,
            retry_delay_seconds=0,
            enable_compensation=False,
            enable_dead_letter_queue=False,
        ))
        
        def always_fails_adapter(action_plan):
            raise Exception("Always fails")
        
        executor.register_adapter("AUTO_RESOLVE", always_fails_adapter)
        
        action_plan = create_test_action_plan(
            approval_status=ApprovalStatus.NOT_REQUIRED,
        )
        
        result = executor.execute(action_plan)
        
        assert result.success is False
        assert len(executor.get_dead_letter_queue()) == 0

    def test_dead_letter_queue_operations(self):
        """Test DLQ get and clear operations."""
        executor = ActionExecutor(config=ActionExecutorConfig(
            max_retries=1,
            retry_delay_seconds=0,
            enable_compensation=True,
            enable_dead_letter_queue=True,
        ))
        
        def always_fails_adapter(action_plan):
            raise Exception("Fails")
        
        executor.register_adapter("AUTO_RESOLVE", always_fails_adapter)
        
        action_plan = create_test_action_plan(approval_status=ApprovalStatus.NOT_REQUIRED)
        executor.execute(action_plan)
        
        dlq = executor.get_dead_letter_queue()
        assert len(dlq) == 1
        
        executor.clear_dead_letter_queue()
        assert len(executor.get_dead_letter_queue()) == 0

    def test_dry_run_mode(self):
        """Test dry_run mode returns dry_run=True in result."""
        executor = ActionExecutor(config=ActionExecutorConfig(dry_run=True))
        action_plan = create_test_action_plan(approval_status=ApprovalStatus.NOT_REQUIRED)
        
        result = executor.execute(action_plan)
        
        assert result.dry_run is True
        assert result.success is True


class TestApprovalEngine:
    """Tests for ApprovalEngine."""

    def test_engine_initialization(self):
        """Test engine initializes with empty state."""
        engine = ApprovalEngine()
        assert engine.get_pending_approvals() == []
        assert engine._approval_history == []

    def test_request_approval_creates_request(self):
        """Test requesting approval creates proper request."""
        engine = ApprovalEngine()
        
        approval = engine.request_approval(
            action_plan_id="plan-123",
            action_type="AUTO_RESOLVE",
            risk_level="MEDIUM",
            required_approvers=["finance", "manager"],
        )
        
        assert approval.action_plan_id == "plan-123"
        assert approval.action_type == "AUTO_RESOLVE"
        assert approval.risk_level == "MEDIUM"
        assert approval.required_approvers == ["finance", "manager"]
        assert approval.status == "PENDING"

    def test_approve_with_all_approvers(self):
        """Test approve with all required approvers."""
        engine = ApprovalEngine()
        
        approval = engine.request_approval(
            action_plan_id="plan-123",
            action_type="AUTO_RESOLVE",
            risk_level="MEDIUM",
            required_approvers=["finance", "manager"],
        )
        
        result1 = engine.approve(approval.approval_id, "finance")
        assert result1 is True
        assert approval.status == "PENDING"
        
        result2 = engine.approve(approval.approval_id, "manager")
        assert result2 is True
        assert approval.status == "APPROVED"
        
        assert len(engine._approval_history) == 1
        assert engine.get_approval(approval.approval_id) is None

    def test_approve_nonexistent_returns_false(self):
        """Test approve returns False for non-existent approval."""
        engine = ApprovalEngine()
        result = engine.approve("nonexistent", "finance")
        assert result is False

    def test_reject_immediately_rejects(self):
        """Test reject immediately rejects regardless of approvers."""
        engine = ApprovalEngine()
        
        approval = engine.request_approval(
            action_plan_id="plan-123",
            action_type="AUTO_RESOLVE",
            risk_level="MEDIUM",
            required_approvers=["finance", "manager"],
        )
        
        result = engine.reject(approval.approval_id, "finance")
        assert result is True
        assert approval.status == "REJECTED"
        
        assert len(engine._approval_history) == 1

    def test_get_pending_approvals(self):
        """Test getting pending approvals."""
        engine = ApprovalEngine()
        
        approval1 = engine.request_approval("plan-1", "AUTO_RESOLVE", "LOW", ["finance"])
        approval2 = engine.request_approval("plan-2", "ADJUST_PAYMENT", "HIGH", ["finance", "manager"])
        engine.approve(approval1.approval_id, "finance")
        
        pending = engine.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0].approval_id == approval2.approval_id

    def test_approval_history_tracking(self):
        """Test approval history is tracked."""
        engine = ApprovalEngine()
        
        approval = engine.request_approval("plan-1", "AUTO_RESOLVE", "LOW", ["finance"])
        engine.approve(approval.approval_id, "finance")
        
        assert len(engine._approval_history) == 1
        hist = engine._approval_history[0]
        assert hist["action_plan_id"] == "plan-1"
        assert hist["status"] == "APPROVED"
        assert "resolved_at" in hist


class TestPhase4Pipeline:
    """Tests for Phase4Pipeline."""

    def test_pipeline_initialization(self):
        """Test pipeline initializes with default components."""
        pipeline = Phase4Pipeline()
        assert pipeline.risk_engine is not None
        assert pipeline.guardrail is not None
        assert pipeline.executor is not None

    def test_process_creates_action_plan(self):
        """Test process creates action plan with correct structure."""
        pipeline = Phase4Pipeline()
        investigation_result = create_test_investigation()
        exception_report = create_test_exception_report()
        
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
        )
        
        assert action_plan is not None
        assert action_plan.action_id is not None
        assert action_plan.exception_id == "INV-TEST-001"
        assert action_plan.action_type is not None
        assert action_plan.risk_assessment is not None
        assert action_plan.guardrail_decision is not None
        assert action_plan.approval_status in [ApprovalStatus.NOT_REQUIRED, ApprovalStatus.PENDING, ApprovalStatus.APPROVED]
        assert action_plan.idempotency_key is not None
        assert action_plan.evidence_ids == ["EV-001"]
        assert action_plan.investigation_result_ref == "INV-TEST-001"

    def test_process_status_transition_no_approval_needed(self):
        """Test status transitions to APPROVED when no approval needed."""
        pipeline = Phase4Pipeline()
        investigation_result = create_test_investigation()
        exception_report = create_test_exception_report()
        
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
        )
        
        if action_plan.approval_status == ApprovalStatus.NOT_REQUIRED:
            assert action_plan.status == ActionStatus.APPROVED

    def test_process_dev_mode_auto_approve(self):
        """Test DEV mode auto-approves pending actions."""
        pipeline = Phase4Pipeline()
        investigation_result = create_test_investigation(outcome="ESCALATE")
        exception_report = create_test_exception_report()
        
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
        )
        
        if action_plan.approval_status == ApprovalStatus.PENDING:
            assert action_plan.approval_status == ApprovalStatus.APPROVED
            assert action_plan.status == ActionStatus.APPROVED

    def test_execute_action(self):
        """Test execute_action delegates to executor."""
        pipeline = Phase4Pipeline()
        action_plan = create_test_action_plan(approval_status=ApprovalStatus.NOT_REQUIRED)
        
        result = pipeline.execute_action(action_plan)
        
        assert isinstance(result, ActionResult)
        assert result.success is True

    def test_run_full_pipeline(self):
        """Test full pipeline execution."""
        pipeline = Phase4Pipeline()
        exception_report = create_test_exception_report()
        evidence_set = create_test_evidence_set()
        
        investigation_result, action_plan, action_result = pipeline.run_full_pipeline(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=10,
        )
        
        assert investigation_result is not None
        assert action_plan is not None
        assert action_result is not None
        assert action_result.success is True

    def test_run_full_pipeline_with_custom_action_type(self):
        """Test full pipeline with custom action type."""
        pipeline = Phase4Pipeline()
        exception_report = create_test_exception_report()
        evidence_set = create_test_evidence_set()
        
        investigation_result, action_plan, action_result = pipeline.run_full_pipeline(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=10,
            action_type="REQUEST_INFORMATION",
        )
        
        assert action_plan.action_type == ActionType.REQUEST_INFORMATION


class TestPhase4PipelineIntegration:
    """Integration tests for Phase4Pipeline with real components."""

    def test_pipeline_with_real_risk_and_guardrail(self):
        """Test pipeline with actual risk engine and guardrail."""
        pipeline = Phase4Pipeline()
        investigation_result = create_test_investigation("RESOLVE")
        exception_report = create_test_exception_report()
        
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
        )
        
        assert action_plan.risk_assessment is not None
        assert action_plan.risk_assessment.overall_score is not None
        assert action_plan.risk_assessment.risk_level is not None
        assert action_plan.guardrail_decision is not None
        assert action_plan.guardrail_decision.decision in ["ALLOW", "REQUIRE_APPROVAL", "BLOCK"]

    def test_pipeline_amount_triggers_approval(self):
        """Test pipeline triggers approval for high amount with LOW risk."""
        pipeline = Phase4Pipeline()
        investigation_result = InvestigationResult(
            case_id="INV-TEST-001",
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            final_state=AgentState.DECISION_READY,
            outcome=TerminalOutcome.RESOLVE,
            evidence_ids=["EV-001", "EV-002", "EV-003", "EV-004"],
            findings="Test findings",
            steps=[],
            budget_limit=10,
            budget_used=3,
            termination_reason="Test completed",
        )
        
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.AMOUNT_MISMATCH,
                    severity=ExceptionSeverity.LOW,
                    message="Small amount mismatch",
                    details={"amount": "100"},
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )
        
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
            action_params={"amount": "5000"},
            idempotency_key="test-idempotency-key",
        )
        
        assert action_plan.guardrail_decision.decision.value == "REQUIRE_APPROVAL"
        assert action_plan.guardrail_decision.requires_approval is True

    def test_end_to_end_phase1_to_4_pipeline(self):
        """Test complete Phase 1->4 pipeline: Validator -> Evidence -> Agent -> Risk -> Guardrail -> Action."""
        from apx.intelligence.validator import InvoiceValidator
        from apx.evidence.engine import HybridContextEngine
        from apx.agent.controller import run_investigation
        from apx.data.schemas import Invoice, PurchaseOrder, Vendor, GoodsReceipt
        from decimal import Decimal
        from datetime import date
        
        # Phase 1: Create test data and run validator
        vendor = Vendor(
            vendor_id="V-0001",
            vendor_name="Test Vendor",
            tax_id="TAX-001",
            currency="USD",
            payment_terms_days=30,
            credit_status="ACTIVE",
            status="ACTIVE",
        )
        
        po = PurchaseOrder(
            po_id="PO-001",
            vendor_id="V-0001",
            po_number="PO-001",
            po_date=date(2024, 1, 1),
            currency="USD",
            subtotal=Decimal("1000.00"),
            tax=Decimal("100.00"),
            total=Decimal("1100.00"),
            line_items=[],
            status="OPEN",
        )
        
        grn = GoodsReceipt(
            grn_id="GRN-001",
            po_id="PO-001",
            vendor_id="V-0001",
            receipt_date=date(2024, 1, 15),
            line_items=[],
            status="RECEIVED",
        )
        
        invoice = Invoice(
            invoice_id="INV-E2E-001",
            vendor_id="V-0001",
            invoice_number="INV-E2E-001",
            po_number="PO-001",
            invoice_date=date(2024, 1, 20),
            due_date=date(2024, 2, 20),
            currency="USD",
            subtotal=Decimal("1800.00"),
            tax=Decimal("200.00"),
            total=Decimal("2000.00"),
            discount=Decimal("0.00"),
            line_items=[],
        )
        
        # Phase 1: Validate invoice
        validator = InvoiceValidator()
        exception_report = validator.validate_invoice(
            invoice=invoice,
            po=po,
            grn=grn,
            vendor=vendor,
        )
        
        assert exception_report.validation_status.value == "EXCEPTIONS"
        assert any(e.exception_code.value == "AMOUNT_MISMATCH" for e in exception_report.exceptions)
        
        # Phase 2: Retrieve evidence
        evidence_engine = HybridContextEngine()
        evidence_set = evidence_engine.retrieve(exception_report)
        
        assert evidence_set is not None
        assert evidence_set.invoice_id == "INV-E2E-001"
        assert len(evidence_set.validated_evidence) >= 0
        
        # Phase 3: Run investigation
        investigation_result = run_investigation(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=10,
        )
        
        assert investigation_result is not None
        assert investigation_result.outcome is not None
        assert investigation_result.invoice_id == "INV-E2E-001"
        
        # Phase 4: Process through pipeline
        pipeline = Phase4Pipeline()
        action_plan = pipeline.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
            evidence_set=evidence_set,
        )
        
        assert action_plan is not None
        assert action_plan.action_id is not None
        assert action_plan.risk_assessment is not None
        assert action_plan.guardrail_decision is not None
        assert action_plan.guardrail_decision.decision in ["ALLOW", "REQUIRE_APPROVAL", "BLOCK"]
        
        # Execute action
        action_result = pipeline.execute_action(action_plan)
        
        assert action_result is not None
        assert isinstance(action_result.success, bool)
        
        print(f"Phase 1: Exception report - {len(exception_report.exceptions)} exceptions")
        print(f"Phase 2: Evidence set - {len(evidence_set.validated_evidence)} validated evidence")
        print(f"Phase 3: Investigation - outcome={investigation_result.outcome}")
        print(f"Phase 4: Action - decision={action_plan.guardrail_decision.decision.value}, success={action_result.success}")