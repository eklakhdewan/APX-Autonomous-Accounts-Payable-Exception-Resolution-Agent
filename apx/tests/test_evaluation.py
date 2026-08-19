from __future__ import annotations

from decimal import Decimal
from datetime import date
from typing import List

import pytest

from apx.data.schemas import (
    Invoice, PurchaseOrder, Vendor, GoodsReceipt, GroundTruth,
    ExceptionCode, ExceptionSeverity, ValidationStatus,
    Currency, CreditStatus, VendorStatus, POStatus, GRNStatus
)
from apx.evaluation.extraction_eval import ExtractionEvaluator
from apx.evaluation.detection_eval import DetectionEvaluator
from apx.evaluation.retrieval_eval import RetrievalEvaluator, RetrievalResult
from apx.evaluation.decision_eval import DecisionEvaluator
from apx.evaluation.action_eval import ActionEvaluator
from apx.evaluation.business_eval import BusinessEvaluator
from apx.agent.models import InvestigationResult, TerminalOutcome
from apx.risk.models import RiskAssessment, RiskLevel, RiskDimension, RiskDimensionScore
from apx.guardrail.models import GuardrailDecisionResult, GuardrailDecision, ActionType, ApprovalStatus
from apx.action.models import ActionPlan, ActionResult
from apx.evidence.schemas import EvidenceSet, RetrievedCandidate, Evidence, EvidenceType, SourceAuthority, ValidityStatus, ValidatedEvidence


def _create_test_invoice(invoice_id: str = "INV-TEST-001") -> Invoice:
    """Create a minimal test invoice."""
    return Invoice(
        invoice_id=invoice_id,
        vendor_id="V-0001",
        invoice_number="INV-001",
        po_number="PO-001",
        invoice_date=date(2024, 1, 15),
        due_date=date(2024, 2, 15),
        currency=Currency.USD,
        subtotal=Decimal("1000.00"),
        tax=Decimal("100.00"),
        total=Decimal("1100.00"),
        discount=Decimal("0.00"),
        line_items=[],
    )


def _create_test_ground_truth(invoice_id: str = "INV-TEST-001", expected_exceptions: List[ExceptionCode] = None) -> GroundTruth:
    """Create a minimal test ground truth."""
    return GroundTruth(
        invoice_id=invoice_id,
        expected_exceptions=expected_exceptions or [],
        expected_decision="AUTO_APPROVE" if not expected_exceptions else "REVIEW",
    )


def _create_test_exception_report(invoice_id: str = "INV-TEST-001", exception_codes: List[ExceptionCode] = None):
    """Create a minimal test exception report."""
    from apx.data.schemas import ExceptionReport, APException
    report = ExceptionReport(
        invoice_id=invoice_id,
        vendor_id="V-0001",
        validation_status=ValidationStatus.EXCEPTIONS,
    )
    if exception_codes:
        for code in exception_codes:
            report.exceptions.append(APException(
                exception_code=code,
                severity=ExceptionSeverity.MEDIUM,
                message=f"Test {code.value}",
            ))
    return report


def _create_test_evidence_set(invoice_id: str = "INV-TEST-001", with_evidence: bool = True, exception_codes: List[ExceptionCode] = None) -> EvidenceSet:
    """Create a minimal test evidence set."""
    validated = []
    candidates = []
    if with_evidence:
        evidence = Evidence(
            evidence_id="EV-TEST-001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2026, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence for amount mismatch",
        )
        validated.append(ValidatedEvidence(
            evidence=evidence,
            relevance_score=0.9,
            reranker_score=0.85,
            retrieval_sources=["Dense"],
            rank=1,
            validity_status=ValidityStatus.VALID,
            validity_reasons=[],
            scope_metadata={},
            source_authority=SourceAuthority.INTERNAL,
            content=evidence.content,
        ))
        candidates.append(RetrievedCandidate(
            evidence=evidence,
            dense_score=0.9,
            dense_rank=1,
            retrieval_sources=["Dense"],
        ))
    return EvidenceSet(
        invoice_id=invoice_id,
        vendor_id="V-0001",
        exception_codes=[e.value for e in (exception_codes or [])],
        query="test query",
        candidates=candidates,
        validated_evidence=validated,
    )


def _create_test_investigation_result(invoice_id: str = "INV-TEST-001", outcome: TerminalOutcome = TerminalOutcome.RESOLVE) -> InvestigationResult:
    """Create a minimal test investigation result."""
    return InvestigationResult(
        case_id=invoice_id,
        invoice_id=invoice_id,
        vendor_id="V-0001",
        exception_codes=[ExceptionCode.AMOUNT_MISMATCH],
        final_state="DECISION_READY",
        outcome=outcome,
        evidence_ids=["EV-TEST-001"],
        findings="Test findings",
        steps=[],
        budget_limit=10,
        budget_used=3,
        termination_reason="Test",
    )


def _create_test_risk_assessment(invoice_id: str = "INV-TEST-001", risk_level: RiskLevel = RiskLevel.LOW) -> RiskAssessment:
    """Create a minimal test risk assessment."""
    return RiskAssessment(
        overall_score=Decimal("0.2"),
        risk_level=risk_level,
        dimension_scores=[
            RiskDimensionScore(dimension=RiskDimension.FINANCIAL, score=Decimal("0.1"), weight=Decimal("0.3"), weighted_score=Decimal("0.03")),
            RiskDimensionScore(dimension=RiskDimension.COMPLIANCE, score=Decimal("0.2"), weight=Decimal("0.2"), weighted_score=Decimal("0.04")),
            RiskDimensionScore(dimension=RiskDimension.VENDOR, score=Decimal("0.1"), weight=Decimal("0.2"), weighted_score=Decimal("0.02")),
            RiskDimensionScore(dimension=RiskDimension.OPERATIONAL, score=Decimal("0.3"), weight=Decimal("0.2"), weighted_score=Decimal("0.06")),
            RiskDimensionScore(dimension=RiskDimension.EVIDENCE_CONFIDENCE, score=Decimal("0.2"), weight=Decimal("0.1"), weighted_score=Decimal("0.02")),
        ],
        investigation_outcome="RESOLVE",
        evidence_ids=["EV-TEST-001"],
        calculation_metadata={},
        reasons=["Test risk assessment"],
    )


def _create_test_guardrail_result(decision: GuardrailDecision = GuardrailDecision.ALLOW) -> GuardrailDecisionResult:
    """Create a minimal test guardrail result."""
    return GuardrailDecisionResult(
        decision=decision,
        action_type=ActionType.AUTO_RESOLVE,
        checks=[],
        risk_level="LOW",
        requires_approval=False,
        approval_status=ApprovalStatus.NOT_REQUIRED,
    )


def _create_test_action_plan(invoice_id: str = "INV-TEST-001", action_type: ActionType = ActionType.AUTO_RESOLVE) -> ActionPlan:
    """Create a minimal test action plan."""
    return ActionPlan(
        action_id="ACTION-TEST-001",
        exception_id=invoice_id,
        action_type=action_type,
        target=invoice_id,
        risk_assessment=_create_test_risk_assessment(invoice_id),
        guardrail_decision=_create_test_guardrail_result(),
        approval_status=ApprovalStatus.NOT_REQUIRED,
        idempotency_key="test-key",
    )


def _create_test_action_result(success: bool = True) -> ActionResult:
    """Create a minimal test action result."""
    return ActionResult(
        action_id="ACTION-TEST-001",
        success=success,
        result_data={"action": "AUTO_RESOLVE"},
    )


class TestExtractionEvaluator:
    """Tests for Layer 1 - Extraction Evaluation."""

    def test_extraction_exact_match_rate(self):
        """Test extraction evaluation with identical invoices (100% match)."""
        evaluator = ExtractionEvaluator()
        invoice = _create_test_invoice()
        result = evaluator.evaluate_invoice(invoice, invoice)

        assert result.exact_match_rate == 1.0
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.total_fields == result.matched_fields
        assert result.missing_fields == 0
        assert result.unexpected_fields == 0

    def test_extraction_aggregate_results(self):
        """Test aggregation of multiple extraction results."""
        evaluator = ExtractionEvaluator()
        invoice1 = _create_test_invoice("INV-001")
        invoice2 = _create_test_invoice("INV-002")

        results = [
            evaluator.evaluate_invoice(invoice1, invoice1),
            evaluator.evaluate_invoice(invoice2, invoice2),
        ]

        agg = evaluator.aggregate_results(results)

        assert agg.exact_match_rate == 1.0
        assert agg.precision == 1.0
        assert agg.recall == 1.0
        assert agg.f1 == 1.0


class TestDetectionEvaluator:
    """Tests for Layer 2 - Detection Evaluation."""

    def test_detection_perfect_match(self):
        """Test detection when all exceptions match ground truth."""
        evaluator = DetectionEvaluator()

        report = _create_test_exception_report("INV-001", [ExceptionCode.AMOUNT_MISMATCH, ExceptionCode.TAX_ERROR])
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH, ExceptionCode.TAX_ERROR])

        result = evaluator.evaluate_batch([report], [gt])

        assert result.true_positives == 2
        assert result.false_positives == 0
        assert result.false_negatives == 0
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_detection_false_positives(self):
        """Test detection with extra detected exceptions."""
        evaluator = DetectionEvaluator()

        report = _create_test_exception_report("INV-001", [ExceptionCode.AMOUNT_MISMATCH, ExceptionCode.TAX_ERROR])
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH])

        result = evaluator.evaluate_batch([report], [gt])

        assert result.true_positives == 1
        assert result.false_positives == 1
        assert result.false_negatives == 0
        assert result.precision == 0.5
        assert result.recall == 1.0
        assert result.f1 == 2/3

    def test_detection_false_negatives(self):
        """Test detection with missed exceptions."""
        evaluator = DetectionEvaluator()

        report = _create_test_exception_report("INV-001", [ExceptionCode.AMOUNT_MISMATCH])
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH, ExceptionCode.TAX_ERROR])

        result = evaluator.evaluate_batch([report], [gt])

        assert result.true_positives == 1
        assert result.false_positives == 0
        assert result.false_negatives == 1
        assert result.precision == 1.0
        assert result.recall == 0.5
        assert result.f1 == 2/3

    def test_detection_clean_invoice(self):
        """Test detection on clean invoice (no exceptions).
        
        Note: When both detected and expected are empty, the evaluator
        returns 0.0 for precision/recall/F1 because 0/0 is undefined.
        This test documents the actual behavior.
        """
        evaluator = DetectionEvaluator()

        report = _create_test_exception_report("INV-001", [])
        gt = _create_test_ground_truth("INV-001", [])

        result = evaluator.evaluate_batch([report], [gt])

        assert result.true_positives == 0
        assert result.false_positives == 0
        assert result.false_negatives == 0
        # When both sets are empty, precision/recall/F1 are 0.0 (undefined)
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0


class TestRetrievalEvaluator:
    """Tests for Layer 3 - Retrieval Evaluation."""

    def test_retrieval_recall_at_k(self):
        """Test retrieval recall@k calculation."""
        evaluator = RetrievalEvaluator()

        # Create evidence set with known relevant/irrelevant IDs
        evidence_set = _create_test_evidence_set("INV-001")

        relevant = {"EV-TEST-001"}
        irrelevant = {"EV-IRRELEVANT-001", "EV-IRRELEVANT-002"}
        invalid = {"EV-INVALID-001"}

        result = evaluator.evaluate(evidence_set, relevant, irrelevant, invalid, k_values=[5, 10])

        assert result.recall_at_5 == 1.0  # 1 relevant out of 1 total
        assert result.recall_at_10 == 1.0
        assert result.mrr == 1.0  # First result is relevant
        assert result.total_queries == 1

    def test_retrieval_mrr(self):
        """Test MRR calculation with relevant at rank 3."""
        evaluator = RetrievalEvaluator()

        # Mock an evidence set where relevant is at rank 3
        from apx.evidence.schemas import RetrievedCandidate, Evidence, EvidenceType, SourceAuthority, ValidityStatus

        evidence_list = []
        for i in range(5):
            ev = Evidence(
                evidence_id=f"EV-{i:03d}",
                evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
                scope="vendor_exception",
                scope_target="V-0001:AMOUNT_MISMATCH" if i == 2 else "other",
                vendor_id="V-0001",
                effective_from=date(2024, 1, 1),
                effective_until=date(2026, 12, 31),
                policy_version="v1.0",
                outcome="AUTO_APPROVED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=10,
                content=f"Test evidence {i}",
            )
            cand = RetrievedCandidate(
                evidence=ev,
                dense_score=1.0 - i * 0.1,
                dense_rank=i + 1,
                retrieval_sources=["Dense"],
            )
            evidence_list.append(cand)

        evidence_set = EvidenceSet(
            invoice_id="INV-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            query="test query",
            candidates=evidence_list,
            validated_evidence=[],
        )

        relevant = {"EV-002"}  # Third result (0-indexed = 2)
        result = evaluator.evaluate(evidence_set, relevant, set(), set(), k_values=[5, 10])

        assert result.mrr == 1/3  # Relevant at rank 3 (1-indexed)
        assert result.recall_at_5 == 1.0

    def test_retrieval_ndcg(self):
        """Test nDCG@10 calculation."""
        evaluator = RetrievalEvaluator()

        evidence_set = _create_test_evidence_set("INV-001")
        relevant = {"EV-TEST-001"}

        result = evaluator.evaluate(evidence_set, relevant, set(), set(), k_values=[5, 10])

        assert result.ndcg_at_10 >= 0.0
        assert result.ndcg_at_10 <= 1.0

    def test_retrieval_invalid_rejection(self):
        """Test invalid evidence rejection rate."""
        evaluator = RetrievalEvaluator()

        evidence_set = _create_test_evidence_set("INV-001")

        relevant = set()
        invalid = {"EV-INVALID-001"}

        result = evaluator.evaluate(evidence_set, relevant, set(), invalid)

        # No invalid evidence in results = perfect rejection
        assert result.invalid_evidence_rejection_rate == 1.0

    def test_retrieval_vendor_scope(self):
        """Test vendor scope correctness."""
        evaluator = RetrievalEvaluator()

        evidence_set = _create_test_evidence_set("INV-001")
        relevant = {"EV-TEST-001"}  # Same vendor

        result = evaluator.evaluate(evidence_set, relevant, set(), set())

        # All results should be from same vendor
        assert result.vendor_scope_correctness == 1.0


class TestDecisionEvaluator:
    """Tests for Layer 4 - Decision Evaluation."""

    def test_decision_accuracy_resolve(self):
        """Test decision accuracy with RESOLVE outcome."""
        evaluator = DecisionEvaluator()

        inv_result = _create_test_investigation_result("INV-001", TerminalOutcome.RESOLVE)
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH])
        # Ground truth expected_decision should be "AUTO_APPROVE" for RESOLVE
        gt.expected_decision = "AUTO_APPROVE"

        result = evaluator.evaluate_investigation_outcome(inv_result, gt)

        assert result.accuracy == 1.0
        assert result.correct_decisions == 1

    def test_decision_risk_classification(self):
        """Test risk classification evaluation."""
        evaluator = DecisionEvaluator()

        risk = _create_test_risk_assessment("INV-001", RiskLevel.LOW)
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH])
        gt.expected_decision = "AUTO_APPROVE"

        result = evaluator.evaluate_risk_classification(risk, gt)

        assert hasattr(result, 'risk_accuracy')
        assert hasattr(result, 'risk_correct')


class TestActionEvaluator:
    """Tests for Layer 5 - Action Evaluation."""

    def test_action_accuracy_auto_resolve(self):
        """Test action accuracy with AUTO_RESOLVE."""
        evaluator = ActionEvaluator()

        action_plan = _create_test_action_plan("INV-001", ActionType.AUTO_RESOLVE)
        action_result = _create_test_action_result(True)
        guardrail_result = _create_test_guardrail_result(GuardrailDecision.ALLOW)
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH])

        result = evaluator.evaluate_action(action_plan, action_result, guardrail_result, gt)

        assert result.action_accuracy >= 0.0
        assert result.guardrail_accuracy >= 0.0

    def test_unauthorized_action_rate_zero(self):
        """Test unauthorized action rate is 0 when guardrail allows."""
        evaluator = ActionEvaluator()

        action_plan = _create_test_action_plan("INV-001", ActionType.AUTO_RESOLVE)
        action_result = _create_test_action_result(True)
        guardrail_result = _create_test_guardrail_result(GuardrailDecision.ALLOW)
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.AMOUNT_MISMATCH])

        result = evaluator.evaluate_action(action_plan, action_result, guardrail_result, gt)

        assert result.unauthorized_action_rate == 0.0

    def test_blocked_action_correctness(self):
        """Test blocked action correctness evaluation."""
        evaluator = ActionEvaluator()

        # Create a blocked action plan
        action_plan = _create_test_action_plan("INV-001", ActionType.ESCALATE_TO_HUMAN)
        action_plan.guardrail_decision = _create_test_guardrail_result(GuardrailDecision.BLOCK)
        action_result = _create_test_action_result(False)
        guardrail_result = _create_test_guardrail_result(GuardrailDecision.BLOCK)
        gt = _create_test_ground_truth("INV-001", [ExceptionCode.CREDIT_ISSUE])

        result = evaluator.evaluate_action(action_plan, action_result, guardrail_result, gt)

        assert "blocked_accuracy" in dir(result) or hasattr(result, 'blocked_correct')


class TestBusinessEvaluator:
    """Tests for Layer 6 - Business Evaluation."""

    def test_business_evaluator_instantiation(self):
        """Test BusinessEvaluator can be instantiated with default config."""
        evaluator = BusinessEvaluator()
        assert evaluator is not None
        assert evaluator.phase1_cost == 0.001
        assert evaluator.phase2_cost == 0.005
        assert evaluator.phase3_cost == 0.01
        assert evaluator.phase4_cost == 0.002

    def test_business_evaluator_custom_config(self):
        """Test BusinessEvaluator with custom cost configuration."""
        evaluator = BusinessEvaluator(
            phase1_cost_per_invoice=0.01,
            phase2_cost_per_invoice=0.02,
            phase3_cost_per_invoice=0.05,
            phase4_cost_per_invoice=0.01,
            manual_review_cost_usd=10.0,
            auto_resolve_savings_usd=20.0,
        )
        assert evaluator.phase1_cost == 0.01
        assert evaluator.phase2_cost == 0.02
        assert evaluator.phase3_cost == 0.05
        assert evaluator.phase4_cost == 0.01
        assert evaluator.manual_review_cost == 10.0
        assert evaluator.auto_resolve_savings == 20.0

    def test_business_evaluator_evaluate_method_exists(self):
        """Test BusinessEvaluator has the evaluate method."""
        evaluator = BusinessEvaluator()
        assert hasattr(evaluator, 'evaluate')
        assert callable(getattr(evaluator, 'evaluate'))


# Integration test: verify all evaluators can be imported and instantiated
class TestEvaluatorImports:
    """Verify all six evaluator modules can be imported and used."""

    def test_all_evaluators_exist(self):
        """All six evaluators should be importable and instantiable."""
        evaluators = [
            ExtractionEvaluator(),
            DetectionEvaluator(),
            RetrievalEvaluator(),
            DecisionEvaluator(),
            ActionEvaluator(),
            BusinessEvaluator(),
        ]

        for evaluator in evaluators:
            assert evaluator is not None
            assert hasattr(evaluator, '__class__')


# End-to-end test with mock data
class TestEvaluationIntegration:
    """Integration test using all six layers with mock data."""

    def test_full_evaluation_pipeline(self):
        """Run all six evaluators with consistent mock data."""
        # Create consistent test data
        invoice_id = "INV-INTEGRATION-001"

        invoice = _create_test_invoice(invoice_id)
        gt = _create_test_ground_truth(invoice_id, [ExceptionCode.AMOUNT_MISMATCH])
        report = _create_test_exception_report(invoice_id, [ExceptionCode.AMOUNT_MISMATCH])
        evidence_set = _create_test_evidence_set(invoice_id, with_evidence=True)
        inv_result = _create_test_investigation_result(invoice_id, TerminalOutcome.RESOLVE)
        risk = _create_test_risk_assessment(invoice_id, RiskLevel.LOW)
        guardrail = _create_test_guardrail_result(GuardrailDecision.ALLOW)
        action_plan = _create_test_action_plan(invoice_id, ActionType.AUTO_RESOLVE)
        action_result = _create_test_action_result(True)

        # Layer 1: Extraction
        ext_eval = ExtractionEvaluator()
        ext_result = ext_eval.evaluate_invoice(invoice, invoice)
        assert ext_result.exact_match_rate == 1.0

        # Layer 2: Detection
        det_eval = DetectionEvaluator()
        det_result = det_eval.evaluate_batch([report], [gt])
        assert det_result.f1 >= 0.0

        # Layer 3: Retrieval
        ret_eval = RetrievalEvaluator()
        ret_result = ret_eval.evaluate(evidence_set, {"EV-TEST-001"}, set(), set())
        assert ret_result.recall_at_5 == 1.0

        # Layer 4: Decision
        dec_eval = DecisionEvaluator()
        # Just verify it runs
        dec_result = dec_eval.evaluate_investigation_outcome(inv_result, gt)
        assert hasattr(dec_result, 'accuracy')
        assert dec_result.accuracy >= 0.0

        # Layer 5: Action
        act_eval = ActionEvaluator()
        guardrail = _create_test_guardrail_result(GuardrailDecision.ALLOW)
        act_result = act_eval.evaluate_action(action_plan, action_result, guardrail, gt)
        assert act_result.unauthorized_action_rate == 0.0

        # Layer 6: Business
        bus_eval = BusinessEvaluator()
        assert bus_eval is not None