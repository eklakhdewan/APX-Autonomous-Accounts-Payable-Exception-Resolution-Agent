from __future__ import annotations

import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from apx.data.schemas import (
    Invoice,
    InvoiceLine,
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    Currency,
    CreditStatus,
    POStatus,
    GRNStatus,
    ValidationStatus,
    ExceptionCode,
    GroundTruth,
    APException,
    ExceptionSeverity,
)
from apx.agent.models import InvestigationResult, InvestigationStep
from apx.agent.state_machine import AgentState, TerminalOutcome
from apx.risk.models import RiskAssessment, RiskDimensionScore, RiskDimension, RiskLevel
from apx.guardrail.models import (
    GuardrailDecisionResult,
    ActionType,
    GuardrailDecision,
    GuardrailCheckResult,
    ApprovalStatus,
)
from apx.action.models import ActionPlan, ActionResult, ActionStatus
from apx.persistence import (
    init_database,
    reset_database,
    close_database,
    SQLiteInvoiceRepository,
    SQLiteCaseRepository,
    SQLiteApprovalRepository,
    SQLiteActionRepository,
    SQLiteAuditRepository,
)


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary file-based database for testing with unique path."""
    # Close any existing global engine first
    close_database()
    # Use unique temporary file for each test
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    init_database(database_url=db_url, create_tables=True)
    yield db_url
    close_database()
    import os
    os.unlink(db_path)


@pytest.fixture(scope="function")
def clean_db(temp_db):
    """Ensure database is clean for each test."""
    reset_database()
    yield temp_db
    reset_database()


@pytest.fixture
def sample_invoice() -> Invoice:
    """Create a sample invoice for testing."""
    return Invoice(
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        invoice_number="INV-2026-001",
        po_number="PO-2026-001",
        invoice_date="2026-01-15",
        due_date="2026-02-14",
        currency=Currency.USD,
        subtotal=Decimal("1000.00"),
        tax=Decimal("100.00"),
        total=Decimal("1100.00"),
        discount=Decimal("0.00"),
        line_items=[
            InvoiceLine(
                line_id="L-001",
                description="Test Item",
                po_line_id="POL-001",
                quantity=Decimal("10"),
                unit_price=Decimal("100.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("0.10"),
            )
        ],
    )


@pytest.fixture
def persisted_invoice(clean_db, sample_invoice) -> Invoice:
    """Create and persist a sample invoice for testing."""
    repo = SQLiteInvoiceRepository()
    repo.create(sample_invoice)
    return sample_invoice


@pytest.fixture
def sample_ground_truth() -> GroundTruth:
    """Create sample ground truth for testing."""
    return GroundTruth(
        invoice_id="INV-TEST-001",
        expected_exceptions=[ExceptionCode.AMOUNT_MISMATCH],
        expected_decision="ESCALATE",
        injected_exceptions={"AMOUNT_MISMATCH": {"expected": "1000", "actual": "1100"}},
    )


@pytest.fixture
def sample_investigation_result() -> InvestigationResult:
    """Create a sample investigation result."""
    return InvestigationResult(
        case_id="case-001",
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exception_codes=["AMOUNT_MISMATCH"],
        final_state=TerminalOutcome.ESCALATE,
        outcome=TerminalOutcome.ESCALATE,
        evidence_ids=["ev-001", "ev-002"],
        findings="Amount mismatch detected",
        steps=[
            InvestigationStep(
                step_number=1,
                action="validate_amount",
                state_before=AgentState.DETECTED,
                state_after=AgentState.CONTEXT_RETRIEVED,
                evidence_ids=["ev-001"],
                finding="Invoice total exceeds PO total",
                budget_consumed=1,
            )
        ],
        budget_limit=10,
        budget_used=1,
        termination_reason="Escalation required",
    )


@pytest.fixture
def sample_risk_assessment() -> RiskAssessment:
    """Create a sample risk assessment."""
    return RiskAssessment(
        overall_score=Decimal("0.75"),
        risk_level=RiskLevel.HIGH,
        dimension_scores=[
            RiskDimensionScore(
                dimension=RiskDimension.FINANCIAL,
                score=Decimal("0.8"),
                weight=Decimal("0.25"),
                weighted_score=Decimal("0.2"),
                factors=["Amount exceeds threshold"],
                source_evidence_ids=["ev-001"],
            )
        ],
        investigation_outcome="ESCALATE",
        evidence_ids=["ev-001", "ev-002"],
        calculation_metadata={},
        reasons=["High amount risk"],
    )


@pytest.fixture
def sample_guardrail_result() -> GuardrailDecisionResult:
    """Create a sample guardrail result."""
    return GuardrailDecisionResult(
        decision=GuardrailDecision.REQUIRE_APPROVAL,
        action_type=ActionType.ESCALATE_TO_HUMAN,
        checks=[
            GuardrailCheckResult(
                check_name="risk_level",
                passed=False,
                reason="HIGH risk requires approval",
                severity="WARNING",
            )
        ],
        risk_level="HIGH",
        requires_approval=True,
        approval_status=ApprovalStatus.PENDING,
        approval_reason="HIGH risk requires human approval",
        idempotency_key="idem-001",
        rate_limit_ok=True,
        rate_limit_reason="OK",
        block_reason="",
        allowed_action_types=[ActionType.ESCALATE_TO_HUMAN],
        required_approvals=["human_review"],
        metadata={},
    )


@pytest.fixture
def sample_action_plan(sample_guardrail_result: GuardrailDecisionResult) -> ActionPlan:
    """Create a sample action plan."""
    return ActionPlan(
        action_id=str(uuid4()),
        exception_id="INV-TEST-001",
        action_type=ActionType.ESCALATE_TO_HUMAN,
        target="INV-TEST-001",
        parameters={"reason": "Amount mismatch requires review"},
        risk_assessment=None,
        guardrail_decision=sample_guardrail_result,
        approval_status=ApprovalStatus.PENDING,
        idempotency_key="idem-001",
        rate_limit_ok=True,
        evidence_ids=["ev-001", "ev-002"],
        investigation_result_ref="case-001",
        investigation_outcome="ESCALATE",
        status=ActionStatus.PENDING,
    )


class TestDatabaseInitialization:
    """Tests for database initialization and setup."""

    def test_init_database_creates_tables(self, temp_db):
        """Test that database initialization creates all tables."""
        from sqlalchemy import inspect
        engine = init_database(database_url=temp_db, create_tables=True)
        inspector = inspect(engine)

        tables = inspector.get_table_names()
        expected_tables = {
            "invoices",
            "ground_truth",
            "cases",
            "approvals",
            "actions",
            "audit_events",
        }
        assert expected_tables.issubset(set(tables))

    def test_init_database_idempotent(self, temp_db):
        """Test that multiple initializations work correctly."""
        init_database(database_url=temp_db, create_tables=True)
        init_database(database_url=temp_db, create_tables=True)
        # Should not raise any errors

    def test_reset_database_drops_and_recreates(self, clean_db, sample_invoice):
        """Test that reset_database works correctly."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)

        # Verify data exists
        assert repo.exists("INV-TEST-001")

        # Reset
        reset_database()

        # Verify data is gone
        assert not repo.exists("INV-TEST-001")

    def test_close_database_cleans_up(self, temp_db):
        """Test that close_database disposes engine."""
        init_database(database_url=temp_db)
        close_database()
        # Should not raise errors on re-init
        init_database(database_url=temp_db)


class TestInvoiceRepository:
    """Tests for SQLiteInvoiceRepository."""

    def test_create_and_get_invoice(self, clean_db, sample_invoice):
        """Test creating and retrieving an invoice."""
        repo = SQLiteInvoiceRepository()
        invoice_id = repo.create(sample_invoice)

        assert invoice_id == "INV-TEST-001"

        retrieved = repo.get("INV-TEST-001")
        assert retrieved is not None
        assert retrieved.invoice_id == "INV-TEST-001"
        assert retrieved.vendor_id == "V-0001"
        assert retrieved.total == Decimal("1100.00")

    def test_create_invoice_with_ground_truth(self, clean_db, sample_invoice, sample_ground_truth):
        """Test creating invoice with ground truth."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice, sample_ground_truth)

        invoice, gt = repo.get_with_ground_truth("INV-TEST-001")
        assert invoice is not None
        assert gt is not None
        assert gt.invoice_id == "INV-TEST-001"
        assert ExceptionCode.AMOUNT_MISMATCH in gt.expected_exceptions
        assert gt.expected_decision == "ESCALATE"

    def test_get_nonexistent_invoice(self, clean_db):
        """Test getting non-existent invoice returns None."""
        repo = SQLiteInvoiceRepository()
        result = repo.get("NONEXISTENT")
        assert result is None

    def test_exists(self, clean_db, sample_invoice):
        """Test exists method."""
        repo = SQLiteInvoiceRepository()
        assert not repo.exists("INV-TEST-001")

        repo.create(sample_invoice)
        assert repo.exists("INV-TEST-001")

    def test_list_all_with_pagination(self, clean_db):
        """Test listing invoices with pagination."""
        repo = SQLiteInvoiceRepository()

        # Create multiple invoices
        for i in range(5):
            inv = Invoice(
                invoice_id=f"INV-TEST-{i:03d}",
                vendor_id=f"V-{i:04d}",
                invoice_number=f"INV-2026-{i:03d}",
                invoice_date="2026-01-15",
                due_date="2026-02-14",
                currency=Currency.USD,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                total=Decimal("110.00"),
                line_items=[],
            )
            repo.create(inv)

        all_invoices = repo.list_all(limit=10, offset=0)
        assert len(all_invoices) == 5

        page1 = repo.list_all(limit=2, offset=0)
        assert len(page1) == 2

        page2 = repo.list_all(limit=2, offset=2)
        assert len(page2) == 2

    def test_delete_invoice(self, clean_db, sample_invoice):
        """Test deleting an invoice."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)
        assert repo.exists("INV-TEST-001")

        deleted = repo.delete("INV-TEST-001")
        assert deleted is True
        assert not repo.exists("INV-TEST-001")

        # Deleting non-existent should return False
        deleted = repo.delete("INV-TEST-001")
        assert deleted is False


class TestCaseRepository:
    """Tests for SQLiteCaseRepository."""

    def test_create_case(self, clean_db, persisted_invoice):
        """Test creating a case."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        returned_id = repo.create(case_id, "INV-TEST-001", "V-0001", "idem-001")

        assert returned_id == case_id

        case = repo.get(case_id)
        assert case is not None
        assert case["case_id"] == case_id
        assert case["invoice_id"] == "INV-TEST-001"
        assert case["vendor_id"] == "V-0001"
        assert case["status"] == "NEW"
        assert case["idempotency_key"] == "idem-001"

    def test_get_by_invoice(self, clean_db, persisted_invoice):
        """Test getting case by invoice ID."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        case = repo.get_by_invoice("INV-TEST-001")
        assert case is not None
        assert case["case_id"] == case_id

    def test_get_by_idempotency_key(self, clean_db, persisted_invoice):
        """Test getting case by idempotency key."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001", "idem-unique")

        case = repo.get_by_idempotency_key("idem-unique")
        assert case is not None
        assert case["case_id"] == case_id

        # Non-existent key
        case = repo.get_by_idempotency_key("nonexistent")
        assert case is None

    def test_update_status(self, clean_db, persisted_invoice):
        """Test updating case status."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        updated = repo.update_status(case_id, "VALIDATING", current_phase="phase1")
        assert updated is True

        case = repo.get(case_id)
        assert case["status"] == "VALIDATING"
        assert case["current_phase"] == "phase1"

    def test_update_phase1_result(self, clean_db, persisted_invoice):
        """Test updating Phase 1 results."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        updated = repo.update_phase1_result(
            case_id,
            ["AMOUNT_MISMATCH", "TAX_ERROR"],
            "EXCEPTIONS",
        )
        assert updated is True

        case = repo.get(case_id)
        assert case["exception_codes"] == ["AMOUNT_MISMATCH", "TAX_ERROR"]
        assert case["validation_status"] == "EXCEPTIONS"
        assert case["current_phase"] == "phase2"

    def test_update_phase2_result(self, clean_db, persisted_invoice):
        """Test updating Phase 2 results."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        updated = repo.update_phase2_result(case_id, 10, 7)
        assert updated is True

        case = repo.get(case_id)
        assert case["evidence_count"] == 10
        assert case["valid_evidence_count"] == 7
        assert case["current_phase"] == "phase3"

    def test_update_phase3_result(self, clean_db, persisted_invoice, sample_investigation_result):
        """Test updating Phase 3 results."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        updated = repo.update_phase3_result(case_id, sample_investigation_result)
        assert updated is True

        case = repo.get(case_id)
        assert case["investigation_outcome"] == "ESCALATE"
        assert case["investigation_findings"] == "Amount mismatch detected"
        assert case["investigation_budget_limit"] == 10
        assert case["investigation_budget_used"] == 1
        assert len(case["investigation_steps"]) == 1

    def test_update_phase4_result(
        self, clean_db, persisted_invoice, sample_risk_assessment, sample_guardrail_result, sample_action_plan
    ):
        """Test updating Phase 4 results."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        updated = repo.update_phase4_result(
            case_id,
            sample_risk_assessment,
            sample_guardrail_result,
            sample_action_plan,
        )
        assert updated is True

        case = repo.get(case_id)
        assert case["risk_level"] == "HIGH"
        # Decimal precision: 0.75 == 0.750
        assert Decimal(case["risk_score"]) == Decimal("0.75")
        assert case["action_type"] == "ESCALATE_TO_HUMAN"
        assert case["guardrail_decision"] == "REQUIRE_APPROVAL"
        assert len(case["guardrail_checks"]) == 1

    def test_list_all_with_status_filter(self, clean_db, persisted_invoice):
        """Test listing cases with status filter."""
        repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()

        # Create invoices first (using different IDs to avoid conflict with persisted_invoice)
        for i, (inv_id, vend_id) in enumerate([
            ("INV-LIST-001", "V-LIST-001"),
            ("INV-LIST-002", "V-LIST-002"),
            ("INV-LIST-003", "V-LIST-003"),
        ]):
            inv = Invoice(
                invoice_id=inv_id,
                vendor_id=vend_id,
                invoice_number=f"INV-2026-{i+1:03d}",
                invoice_date="2026-01-15",
                due_date="2026-02-14",
                currency=Currency.USD,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                total=Decimal("110.00"),
                line_items=[],
            )
            invoice_repo.create(inv)

        case1 = uuid4()
        case2 = uuid4()
        case3 = uuid4()

        repo = SQLiteCaseRepository()
        repo.create(case1, "INV-LIST-001", "V-LIST-001")
        repo.create(case2, "INV-LIST-002", "V-LIST-002")
        repo.create(case3, "INV-LIST-003", "V-LIST-003")

        repo.update_status(case1, "COMPLETED")
        repo.update_status(case2, "COMPLETED")

        all_cases = repo.list_all(limit=10)
        assert len(all_cases) == 3

        completed = repo.list_all(status="COMPLETED", limit=10)
        assert len(completed) == 2

        new_cases = repo.list_all(status="NEW", limit=10)
        assert len(new_cases) == 1

    def test_delete_case(self, clean_db, persisted_invoice):
        """Test deleting a case."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")

        assert repo.get(case_id) is not None
        deleted = repo.delete(case_id)
        assert deleted is True
        assert repo.get(case_id) is None


class TestApprovalRepository:
    """Tests for SQLiteApprovalRepository."""

    def test_create_approval(self, clean_db, persisted_invoice):
        """Test creating an approval request."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        from apx.action.models import ApprovalRequest, ApprovalStatus
        approval_request = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=str(case_id),
            action_type="ESCALATE_TO_HUMAN",
            risk_level="HIGH",
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=["reviewer1", "reviewer2"],
        )
        approval_id = repo.create(approval_request)

        assert approval_id is not None

        approval = repo.get(approval_id)
        assert approval is not None
        assert approval.action_type == "ESCALATE_TO_HUMAN"
        assert approval.risk_level == "HIGH"
        assert approval.status == ApprovalStatus.PENDING
        assert approval.required_approvers == ["reviewer1", "reviewer2"]

    def test_get_by_case(self, clean_db, persisted_invoice):
        """Test getting approval by case ID."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        from apx.action.models import ApprovalRequest, ApprovalStatus
        approval_request = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=str(case_id),
            action_type="AUTO_RESOLVE",
            risk_level="LOW",
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=[],
        )
        repo.create(approval_request)

        approval = repo.get_by_case(case_id)
        assert approval is not None
        assert approval.approval_id == approval_request.approval_id

    def test_update_status(self, clean_db, persisted_invoice):
        """Test updating approval status."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        from apx.action.models import ApprovalRequest, ApprovalStatus
        approval_request = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=str(case_id),
            action_type="ESCALATE_TO_HUMAN",
            risk_level="HIGH",
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=["reviewer1"],
        )
        approval_id = repo.create(approval_request)

        updated = repo.update_status(approval_id, ApprovalStatus.APPROVED, "reviewer1", "Looks good")
        assert updated is True

        approval = repo.get(approval_id)
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.resolved_by == "reviewer1"
        assert approval.resolution_notes == "Looks good"
        assert approval.resolved_at is not None

    def test_add_approval(self, clean_db, persisted_invoice):
        """Test adding individual approver decision."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        from apx.action.models import ApprovalRequest, ApprovalStatus
        approval_request = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=str(case_id),
            action_type="ESCALATE_TO_HUMAN",
            risk_level="HIGH",
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=["reviewer1", "reviewer2"],
        )
        approval_id = repo.create(approval_request)

        # First approval
        added = repo.add_approval(approval_id, "reviewer1", True, "Approved")
        assert added is True

        approval = repo.get(approval_id)
        assert "reviewer1" in approval.approvals
        assert approval.approvals["reviewer1"] is True

        # Second approval
        added = repo.add_approval(approval_id, "reviewer2", False, "Rejected")
        assert added is True

        approval = repo.get(approval_id)
        assert "reviewer2" in approval.approvals
        assert approval.approvals["reviewer2"] is False

    def test_list_pending(self, clean_db, persisted_invoice):
        """Test listing pending approvals."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()

        # Create multiple cases and approvals
        for i in range(3):
            # Create invoice first
            inv = Invoice(
                invoice_id=f"INV-{i}",
                vendor_id=f"V-{i}",
                invoice_number=f"INV-2026-{i:04d}",
                invoice_date="2026-01-15",
                due_date="2026-02-14",
                currency=Currency.USD,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                total=Decimal("110.00"),
                line_items=[],
            )
            invoice_repo.create(inv)
            
            case_id = uuid4()
            case_repo.create(case_id, f"INV-{i}", f"V-{i}")
            from apx.action.models import ApprovalRequest, ApprovalStatus
            approval_request = ApprovalRequest(
                approval_id=str(uuid4()),
                action_plan_id=str(case_id),
                action_type="ESCALATE_TO_HUMAN",
                risk_level="HIGH",
                requested_by="system",
                status=ApprovalStatus.PENDING,
                required_approvers=["reviewer1"],
            )
            repo.create(approval_request)

        # Update one to approved
        # Note: we can't easily get the approval_id here, so just test listing
        pending = repo.list_pending(limit=10)
        assert len(pending) == 3

    def test_delete_approval(self, clean_db, persisted_invoice):
        """Test deleting an approval."""
        repo = SQLiteApprovalRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        from apx.action.models import ApprovalRequest, ApprovalStatus
        approval_request = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=str(case_id),
            action_type="AUTO_RESOLVE",
            risk_level="LOW",
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=[],
        )
        approval_id = repo.create(approval_request)

        deleted = repo.delete(approval_id)
        assert deleted is True
        assert repo.get(approval_id) is None


class TestActionRepository:
    """Tests for SQLiteActionRepository."""

    def test_create_action(self, clean_db, persisted_invoice, sample_action_plan):
        """Test creating an action record."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        # Update sample_action_plan to use the correct case_id
        sample_action_plan.exception_id = str(case_id)
        action_id = repo.create(sample_action_plan)

        assert str(action_id) == str(sample_action_plan.action_id)

        action = repo.get(action_id)
        assert action is not None
        assert action["action_id"] == str(sample_action_plan.action_id)
        assert action["action_type"] == "ESCALATE_TO_HUMAN"
        assert action["status"] == "PENDING"

    def test_get_by_case(self, clean_db, persisted_invoice, sample_action_plan):
        """Test getting action by case ID."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        sample_action_plan.exception_id = str(case_id)
        action_id = repo.create(sample_action_plan)

        action = repo.get_by_case(case_id)
        assert action is not None
        assert action["action_id"] == str(sample_action_plan.action_id)

    def test_get_by_idempotency_key(self, clean_db, persisted_invoice, sample_action_plan):
        """Test getting action by idempotency key."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        sample_action_plan.exception_id = str(case_id)
        repo.create(sample_action_plan)

        action = repo.get_by_idempotency_key("idem-001")
        assert action is not None
        assert action["idempotency_key"] == "idem-001"

    def test_update_execution(self, clean_db, persisted_invoice, sample_action_plan):
        """Test updating action execution status."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        sample_action_plan.exception_id = str(case_id)
        action_id = repo.create(sample_action_plan)

        result = ActionResult(
            action_id="action-001",
            success=True,
            result_data={"status": "escalated"},
            executed_at="2026-01-15T10:00:00",
        )

        updated = repo.update_execution(action_id, "EXECUTED", result=result)
        assert updated is True

        action = repo.get(action_id)
        assert action["status"] == "EXECUTED"
        assert action["result"]["status"] == "escalated"

    def test_update_compensation(self, clean_db, persisted_invoice, sample_action_plan):
        """Test recording compensation attempt."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        sample_action_plan.exception_id = str(case_id)
        action_id = repo.create(sample_action_plan)

        updated = repo.update_compensation(action_id, {"status": "compensated", "reason": "timeout"})
        assert updated is True

        action = repo.get(action_id)
        assert "compensation" in action["result"]
        assert action["result"]["compensation"]["status"] == "compensated"


class TestAuditRepository:
    """Tests for SQLiteAuditRepository."""

    def test_log_audit_event(self, clean_db, persisted_invoice):
        """Test logging an audit event."""
        repo = SQLiteAuditRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")

        event_id = repo.log(
            case_id=case_id,
            event_type="INVOICE_SUBMITTED",
            phase="phase1",
            component="validator",
            payload={"invoice_id": "INV-001", "vendor_id": "V-001"},
            metadata={"source": "api"},
            request_id="req-001",
            correlation_id="corr-001",
            user_id="user-001",
            duration_ms=15.5,
        )

        assert event_id is not None

        events = repo.get_by_case(case_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "INVOICE_SUBMITTED"
        assert events[0]["request_id"] == "req-001"
        assert events[0]["duration_ms"] == 15.5

    def test_get_by_case(self, clean_db, persisted_invoice):
        """Test getting audit events for a case."""
        repo = SQLiteAuditRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")

        # Log multiple events
        for i in range(3):
            repo.log(
                case_id=case_id,
                event_type=f"EVENT_{i}",
                phase="phase1",
                component="test",
                payload={"index": i},
            )

        events = repo.get_by_case(case_id, limit=10)
        assert len(events) == 3
        # Should be ordered by created_at ASC
        assert events[0]["event_type"] == "EVENT_0"
        assert events[1]["event_type"] == "EVENT_1"
        assert events[2]["event_type"] == "EVENT_2"

    def test_get_by_type(self, clean_db, persisted_invoice):
        """Test getting audit events by type."""
        repo = SQLiteAuditRepository()
        case_repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()

        # Create invoices first
        for inv_id, vend_id in [("INV-1", "V-1"), ("INV-2", "V-2")]:
            inv = Invoice(
                invoice_id=inv_id,
                vendor_id=vend_id,
                invoice_number=f"INV-2026-{inv_id[-1]}",
                invoice_date="2026-01-15",
                due_date="2026-02-14",
                currency=Currency.USD,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                total=Decimal("110.00"),
                line_items=[],
            )
            invoice_repo.create(inv)

        case_id1 = uuid4()
        case_id2 = uuid4()
        case_repo.create(case_id1, "INV-1", "V-1")
        case_repo.create(case_id2, "INV-2", "V-2")

        repo.log(case_id=case_id1, event_type="VALIDATION_COMPLETE", phase="phase1", component="validator", payload={})
        repo.log(case_id=case_id2, event_type="VALIDATION_COMPLETE", phase="phase1", component="validator", payload={})
        repo.log(case_id=case_id1, event_type="INVESTIGATION_COMPLETE", phase="phase3", component="agent", payload={})

        events = repo.get_by_type("VALIDATION_COMPLETE")
        assert len(events) == 2

    def test_list_all(self, clean_db, persisted_invoice):
        """Test listing all audit events."""
        repo = SQLiteAuditRepository()
        case_repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()

        # Create invoice first
        inv = Invoice(
            invoice_id="INV-LIST-ALL",
            vendor_id="V-LIST-ALL",
            invoice_number="INV-2026-LIST",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency=Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            line_items=[],
        )
        invoice_repo.create(inv)

        case_id = uuid4()
        case_repo.create(case_id, "INV-LIST-ALL", "V-LIST-ALL")

        for i in range(5):
            repo.log(case_id=case_id, event_type=f"EVENT_{i}", phase="phase1", component="test", payload={})

        events = repo.list_all(limit=10)
        assert len(events) == 5


class TestTransactionBehavior:
    """Tests for transaction commit/rollback behavior."""

    def test_transaction_commit(self, clean_db, sample_invoice):
        """Test that successful operations commit."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)

        # Verify in new session
        repo2 = SQLiteInvoiceRepository()
        assert repo2.exists("INV-TEST-001")

    def test_transaction_rollback_on_error(self, clean_db, sample_invoice):
        """Test that failed operations rollback."""
        from apx.persistence.database import session_scope
        from apx.persistence.models import InvoiceORM

        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)

        # Try to create duplicate (should fail due to unique constraint)
        with pytest.raises(Exception):
            with session_scope() as session:
                duplicate = InvoiceORM(
                    invoice_id="INV-TEST-001",  # Same ID
                    vendor_id="V-0002",
                    invoice_number="INV-2026-002",
                    invoice_date="2026-01-15",
                    due_date="2026-02-14",
                    currency="USD",
                    subtotal=Decimal("100.00"),
                    tax=Decimal("10.00"),
                    total=Decimal("110.00"),
                    discount=Decimal("0.00"),
                    payload_json={},
                )
                session.add(duplicate)
                session.flush()

        # Original should still exist
        assert repo.exists("INV-TEST-001")
        retrieved = repo.get("INV-TEST-001")
        assert retrieved.vendor_id == "V-0001"  # Original vendor


class TestIdempotencyConstraints:
    """Tests for idempotency and unique constraints."""

    def test_case_idempotency_key_unique(self, clean_db, persisted_invoice):
        """Test that case idempotency keys must be unique (enforced by unique constraint)."""
        repo = SQLiteCaseRepository()
        case_id1 = uuid4()
        case_id2 = uuid4()

        # First case with idempotency key should succeed
        repo.create(case_id1, "INV-TEST-001", "V-0001", "idem-same")
        
        # Second case with same idempotency key should fail due to unique constraint
        with pytest.raises(Exception):
            repo.create(case_id2, "INV-TEST-002", "V-0002", "idem-same")

        # First case should still exist
        case1 = repo.get(case_id1)
        assert case1 is not None
        assert case1["idempotency_key"] == "idem-same"

    def test_action_idempotency_key_unique(self, clean_db, persisted_invoice, sample_action_plan):
        """Test that action idempotency keys must be unique (enforced by unique constraint)."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()
        action_id1 = uuid4()
        action_id2 = uuid4()

        # Create first invoice and case with idempotency key
        inv1 = Invoice(
            invoice_id="INV-1",
            vendor_id="V-1",
            invoice_number="INV-2026-001",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency=Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            line_items=[],
        )
        invoice_repo.create(inv1)
        
        case_id1 = uuid4()
        case_repo.create(case_id1, "INV-1", "V-1")
        
        plan1 = ActionPlan(
            action_id=str(action_id1),
            exception_id=str(case_id1),
            action_type=ActionType.ESCALATE_TO_HUMAN,
            target="INV-1",
            parameters={},
            idempotency_key="idem-action",
        )
        repo.create(plan1)
        
        # Create second invoice and case with same idempotency key - should fail
        inv2 = Invoice(
            invoice_id="INV-2",
            vendor_id="V-2",
            invoice_number="INV-2026-002",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency=Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            line_items=[],
        )
        invoice_repo.create(inv2)
        
        case_id2 = uuid4()
        case_repo.create(case_id2, "INV-2", "V-2")
        
        plan2 = ActionPlan(
            action_id=str(action_id2),
            exception_id=str(case_id2),
            action_type=ActionType.ESCALATE_TO_HUMAN,
            target="INV-2",
            parameters={},
            idempotency_key="idem-action",
        )
        
        with pytest.raises(Exception):
            repo.create(plan2)
        
        # First action should still exist
        action1 = repo.get(action_id1)
        assert action1 is not None

    def test_invoice_id_unique(self, clean_db, sample_invoice):
        """Test that invoice IDs must be unique."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)

        # Try to create another invoice with same ID
        duplicate = Invoice(
            invoice_id="INV-TEST-001",
            vendor_id="V-0002",
            invoice_number="INV-2026-002",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency=Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            line_items=[],
        )

        with pytest.raises(Exception):
            repo.create(duplicate)


class TestConcurrency:
    """Tests for concurrent access patterns."""

    def test_concurrent_case_creation(self, temp_db):
        """Test concurrent case creation with different IDs."""
        def create_case(index: int, errors: list):
            try:
                init_database(database_url=temp_db, create_tables=False)
                case_repo = SQLiteCaseRepository()
                invoice_repo = SQLiteInvoiceRepository()
                case_id = uuid4()
                invoice_id = f"INV-CONCURRENT-{index}"
                vendor_id = f"V-CONCURRENT-{index}"
                
                # Create invoice first
                inv = Invoice(
                    invoice_id=invoice_id,
                    vendor_id=vendor_id,
                    invoice_number=f"INV-2026-{index:04d}",
                    invoice_date="2026-01-15",
                    due_date="2026-02-14",
                    currency=Currency.USD,
                    subtotal=Decimal("100.00"),
                    tax=Decimal("10.00"),
                    total=Decimal("110.00"),
                    line_items=[],
                )
                invoice_repo.create(inv)
                
                # Create case
                case_repo.create(case_id, invoice_id, vendor_id)
            except Exception as e:
                errors.append(e)

        errors = []
        threads = []
        for i in range(10):
            t = threading.Thread(target=create_case, args=(i, errors))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

        # Verify all cases created
        init_database(database_url=temp_db, create_tables=False)
        case_repo = SQLiteCaseRepository()
        cases = case_repo.list_all(limit=20)
        assert len(cases) == 10

    def test_concurrent_approval_updates(self, temp_db):
        """Test concurrent approval status updates."""
        from apx.action.models import ApprovalRequest, ApprovalStatus
        
        def update_approval(index: int, errors: list):
            try:
                init_database(database_url=temp_db, create_tables=False)
                repo = SQLiteApprovalRepository()
                # All threads try to add approval to the same pre-created approval request
                repo.add_approval(approval_id, f"reviewer{index % 2 + 1}", True)
            except Exception as e:
                errors.append(e)

        init_database(database_url=temp_db, create_tables=True)
        case_repo = SQLiteCaseRepository()
        invoice_repo = SQLiteInvoiceRepository()
        
        # Create invoice and case first (once)
        inv = Invoice(
            invoice_id="INV-CONCURRENT-APPROVAL",
            vendor_id="V-CONCURRENT-APPROVAL",
            invoice_number="INV-2026-CONCURRENT",
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency=Currency.USD,
            subtotal=Decimal("100.00"),
            tax=Decimal("10.00"),
            total=Decimal("110.00"),
            line_items=[],
        )
        invoice_repo.create(inv)
        case_id = uuid4()
        case_repo.create(case_id, "INV-CONCURRENT-APPROVAL", "V-CONCURRENT-APPROVAL")
        
        repo = SQLiteApprovalRepository()
        approval_id = repo.create(
            ApprovalRequest(
                approval_id=str(uuid4()),
                action_plan_id=str(case_id),
                action_type="ESCALATE_TO_HUMAN",
                risk_level="HIGH",
                requested_by="system",
                status=ApprovalStatus.PENDING,
                required_approvers=["reviewer1", "reviewer2"],
            )
        )

        errors = []
        threads = []
        for i in range(5):
            t = threading.Thread(target=update_approval, args=(i, errors))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

        # Verify final state
        approval = repo.get(approval_id)
        assert len(approval.approvals) >= 1


class TestSerialization:
    """Tests for serialization/deserialization of APX domain objects."""

    def test_invoice_serialization_roundtrip(self, clean_db, sample_invoice):
        """Test invoice serialization preserves all fields."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)

        retrieved = repo.get("INV-TEST-001")
        assert retrieved.invoice_id == sample_invoice.invoice_id
        assert retrieved.vendor_id == sample_invoice.vendor_id
        assert retrieved.invoice_number == sample_invoice.invoice_number
        assert retrieved.po_number == sample_invoice.po_number
        assert retrieved.currency == sample_invoice.currency
        assert retrieved.subtotal == sample_invoice.subtotal
        assert retrieved.tax == sample_invoice.tax
        assert retrieved.total == sample_invoice.total
        assert retrieved.discount == sample_invoice.discount
        assert len(retrieved.line_items) == len(sample_invoice.line_items)
        assert retrieved.line_items[0].line_id == "L-001"
        assert retrieved.line_items[0].quantity == Decimal("10")

    def test_ground_truth_serialization_roundtrip(self, clean_db, sample_invoice, sample_ground_truth):
        """Test ground truth serialization preserves all fields."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice, sample_ground_truth)

        invoice, gt = repo.get_with_ground_truth("INV-TEST-001")
        assert gt is not None
        assert gt.invoice_id == sample_ground_truth.invoice_id
        assert ExceptionCode.AMOUNT_MISMATCH in gt.expected_exceptions
        assert gt.expected_decision == "ESCALATE"
        assert gt.injected_exceptions == sample_ground_truth.injected_exceptions

    def test_investigation_result_serialization(self, clean_db, persisted_invoice, sample_investigation_result):
        """Test investigation result serialization."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")
        repo.update_phase3_result(case_id, sample_investigation_result)

        case = repo.get(case_id)
        steps = case["investigation_steps"]
        assert len(steps) == 1
        assert steps[0]["action"] == "validate_amount"
        assert steps[0]["finding"] == "Invoice total exceeds PO total"
        assert steps[0]["budget_consumed"] == 1

    def test_risk_assessment_serialization(self, clean_db, persisted_invoice, sample_risk_assessment, sample_guardrail_result, sample_action_plan):
        """Test risk assessment serialization."""
        repo = SQLiteCaseRepository()
        case_id = uuid4()
        repo.create(case_id, "INV-TEST-001", "V-0001")
        repo.update_phase4_result(case_id, sample_risk_assessment, sample_guardrail_result, sample_action_plan)

        case = repo.get(case_id)
        assert case["risk_level"] == "HIGH"
        # Decimal precision: 0.75 == 0.750
        assert Decimal(case["risk_score"]) == Decimal("0.75")
        assert len(case["guardrail_checks"]) == 1
        assert case["guardrail_checks"][0]["check_name"] == "risk_level"

    def test_action_plan_serialization(self, clean_db, persisted_invoice, sample_action_plan):
        """Test action plan serialization."""
        repo = SQLiteActionRepository()
        case_repo = SQLiteCaseRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")
        
        sample_action_plan.exception_id = str(case_id)
        action_id = repo.create(sample_action_plan)

        action = repo.get(action_id)
        assert action["action_id"] == str(sample_action_plan.action_id)
        assert action["action_type"] == "ESCALATE_TO_HUMAN"
        assert action["parameters"]["reason"] == "Amount mismatch requires review"
        assert action["idempotency_key"] == "idem-001"
        # evidence_ids is not stored in the database model
        assert action["target"] == "INV-TEST-001"


class TestPersistenceIsolation:
    """Tests for test isolation and cleanup."""

    def test_database_isolation_between_tests(self, clean_db, sample_invoice):
        """Test that each test gets a clean database."""
        repo = SQLiteInvoiceRepository()
        repo.create(sample_invoice)
        assert repo.exists("INV-TEST-001")

    def test_repository_instances_independent(self, clean_db, sample_invoice):
        """Test that multiple repository instances see same data."""
        repo1 = SQLiteInvoiceRepository()
        repo2 = SQLiteInvoiceRepository()

        repo1.create(sample_invoice)

        assert repo2.exists("INV-TEST-001")
        retrieved = repo2.get("INV-TEST-001")
        assert retrieved is not None


class TestMissingEntityBehavior:
    """Tests for handling of missing entities."""

    def test_get_missing_case(self, clean_db):
        """Test getting non-existent case."""
        repo = SQLiteCaseRepository()
        result = repo.get(uuid4())
        assert result is None

    def test_get_missing_approval(self, clean_db):
        """Test getting non-existent approval."""
        repo = SQLiteApprovalRepository()
        result = repo.get(uuid4())
        assert result is None

    def test_get_missing_action(self, clean_db):
        """Test getting non-existent action."""
        repo = SQLiteActionRepository()
        result = repo.get(uuid4())
        assert result is None

    def test_get_missing_audit_events(self, clean_db):
        """Test getting audit events for non-existent case."""
        repo = SQLiteAuditRepository()
        events = repo.get_by_case(uuid4())
        assert events == []


class TestAuditEventImmutability:
    """Tests for audit event immutability - events must survive parent deletion."""

    def test_audit_events_survive_case_deletion_attempt(self, clean_db, persisted_invoice):
        """Test that audit events cannot be cascade-deleted when case is deleted.
        
        The FK constraint with ondelete=RESTRICT should prevent case deletion
        when audit events exist, or at minimum, audit events must not be
        silently deleted via ORM cascade.
        """
        case_repo = SQLiteCaseRepository()
        audit_repo = SQLiteAuditRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")

        # Log some audit events
        for i in range(3):
            audit_repo.log(
                case_id=case_id,
                event_type=f"TEST_EVENT_{i}",
                phase="phase1",
                component="test",
                payload={"index": i},
            )

        # Verify events exist
        events = audit_repo.get_by_case(case_id)
        assert len(events) == 3

        # Attempt to delete the case - should fail due to RESTRICT FK
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            case_repo.delete(case_id)

        # Audit events should still exist
        events = audit_repo.get_by_case(case_id)
        assert len(events) == 3
        assert events[0]["event_type"] == "TEST_EVENT_0"

    def test_audit_events_survive_invoice_deletion_attempt(self, clean_db, persisted_invoice):
        """Test that audit events cannot be cascade-deleted when invoice is deleted."""
        case_repo = SQLiteCaseRepository()
        audit_repo = SQLiteAuditRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")

        # Log some audit events
        audit_repo.log(
            case_id=case_id,
            event_type="INVOICE_SUBMITTED",
            phase="phase1",
            component="validator",
            payload={"invoice_id": "INV-TEST-001"},
        )

        # Attempt to delete the invoice - should fail due to RESTRICT FK on case
        from sqlalchemy.exc import IntegrityError
        invoice_repo = SQLiteInvoiceRepository()
        with pytest.raises(IntegrityError):
            invoice_repo.delete("INV-TEST-001")

        # Audit events should still exist
        events = audit_repo.get_by_case(case_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "INVOICE_SUBMITTED"

    def test_orm_cascade_does_not_delete_audit_events(self, clean_db, persisted_invoice):
        """Test that ORM-level cascade='save-update, merge, refresh-expire, expunge'
        does not delete audit events when case is deleted via ORM.
        
        This test uses raw SQLAlchemy session to verify the ORM relationship
        configuration is correct.
        """
        from apx.persistence.database import get_session_factory
        from apx.persistence.models import CaseORM, AuditEventORM
        from sqlalchemy import select

        case_repo = SQLiteCaseRepository()
        audit_repo = SQLiteAuditRepository()
        case_id = uuid4()
        case_repo.create(case_id, "INV-TEST-001", "V-0001")

        # Log audit events
        for i in range(2):
            audit_repo.log(
                case_id=case_id,
                event_type=f"ORM_TEST_{i}",
                phase="phase1",
                component="test",
                payload={"index": i},
            )

        # Verify events exist
        events = audit_repo.get_by_case(case_id)
        assert len(events) == 2

        # Delete case using raw SQLAlchemy session (bypassing repository)
        # Use a separate session that we can control
        factory = get_session_factory()
        session = factory()
        try:
            case_orm = session.get(CaseORM, case_id)
            assert case_orm is not None
            # This should fail due to RESTRICT FK at DB level
            from sqlalchemy.exc import IntegrityError
            with pytest.raises(IntegrityError):
                session.delete(case_orm)
                session.flush()
        except IntegrityError:
            session.rollback()
        finally:
            session.close()

        # Audit events should still exist
        events = audit_repo.get_by_case(case_id)
        assert len(events) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])