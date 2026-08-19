from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from apx.agent.models import InvestigationResult, TerminalOutcome
from apx.risk.models import RiskAssessment, RiskLevel
from apx.guardrail.models import GuardrailDecisionResult
from apx.action.models import ActionPlan, ActionType, ActionStatus
from apx.data.schemas import GroundTruth


@dataclass
class DecisionMetrics:
    """Metrics for decision evaluation."""
    total_cases: int = 0
    correct_decisions: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    # Per-outcome metrics
    resolve_tp: int = 0
    resolve_fp: int = 0
    resolve_fn: int = 0
    escalate_tp: int = 0
    escalate_fp: int = 0
    escalate_fn: int = 0
    request_info_tp: int = 0
    request_info_fp: int = 0
    request_info_fn: int = 0

    # Risk classification
    risk_correct: int = 0
    risk_accuracy: float = 0.0

    # Escalation correctness
    escalation_correct: int = 0
    escalation_accuracy: float = 0.0


@dataclass
class DecisionResult:
    """Result of decision evaluation."""
    investigation_outcome_metrics: DecisionMetrics = field(default_factory=DecisionMetrics)
    risk_classification_metrics: DecisionMetrics = field(default_factory=DecisionMetrics)
    escalation_metrics: DecisionMetrics = field(default_factory=DecisionMetrics)
    per_case: List[Dict[str, Any]] = field(default_factory=list)


class DecisionEvaluator:
    """
    Evaluates the Phase 3/4 decision output.

    Supports decision accuracy, expected vs actual terminal outcome,
    risk classification correctness, and escalation correctness.
    """

    def __init__(self):
        pass

    # Mapping from GroundTruth expected_decision values to TerminalOutcome enum
    # GroundTruth uses: AUTO_APPROVE, REVIEW, ESCALATE
    # TerminalOutcome has: RESOLVE, REQUEST_INFO, ESCALATE
    _DECISION_MAP = {
        "AUTO_APPROVE": TerminalOutcome.RESOLVE,
        "REVIEW": TerminalOutcome.REQUEST_INFO,
        "ESCALATE": TerminalOutcome.ESCALATE,
    }

    # Risk level implied by the ground-truth expected decision.
    # Used to measure risk classification against an explicit expectation
    # instead of a hardcoded 100%.
    _EXPECTED_RISK_MAP = {
        "AUTO_APPROVE": RiskLevel.LOW,
        "REVIEW": RiskLevel.MEDIUM,
        "ESCALATE": RiskLevel.HIGH,
    }

    def _map_expected_decision(self, expected: str) -> Optional[TerminalOutcome]:
        """Map GroundTruth expected_decision to TerminalOutcome enum.
        
        Args:
            expected: String value from GroundTruth.expected_decision
            
        Returns:
            TerminalOutcome enum value, or None if unknown
            
        Raises:
            ValueError: If expected value is not recognized
        """
        if expected in self._DECISION_MAP:
            return self._DECISION_MAP[expected]
        
        # Try direct enum conversion as fallback
        try:
            return TerminalOutcome(expected)
        except ValueError:
            raise ValueError(
                f"Unknown expected_decision value: '{expected}'. "
                f"Supported values: {list(self._DECISION_MAP.keys())} "
                f"or TerminalOutcome enum values: {[e.value for e in TerminalOutcome]}"
            )

    def evaluate_investigation_outcome(
        self,
        investigation_result: InvestigationResult,
        ground_truth: GroundTruth,
    ) -> DecisionMetrics:
        """Evaluate investigation terminal outcome against ground truth."""
        metrics = DecisionMetrics()
        metrics.total_cases = 1

        predicted = investigation_result.outcome
        expected_raw = ground_truth.expected_decision

        # Map GroundTruth expected_decision to TerminalOutcome
        if isinstance(expected_raw, str):
            try:
                expected = self._map_expected_decision(expected_raw)
            except ValueError as e:
                # Unknown/unsupported value - produce explicit error result
                metrics.accuracy = 0.0
                metrics.total_cases = 1
                return metrics
        else:
            expected = expected_raw

        if predicted and expected:
            if predicted == expected:
                metrics.correct_decisions = 1
                metrics.accuracy = 1.0

                # Per-outcome TP
                if predicted == TerminalOutcome.RESOLVE:
                    metrics.resolve_tp = 1
                elif predicted == TerminalOutcome.ESCALATE:
                    metrics.escalate_tp = 1
                elif predicted == TerminalOutcome.REQUEST_INFO:
                    metrics.request_info_tp = 1
            else:
                metrics.accuracy = 0.0
                # FP for predicted
                if predicted == TerminalOutcome.RESOLVE:
                    metrics.resolve_fp = 1
                elif predicted == TerminalOutcome.ESCALATE:
                    metrics.escalate_fp = 1
                elif predicted == TerminalOutcome.REQUEST_INFO:
                    metrics.request_info_fp = 1
                # FN for expected
                if expected == TerminalOutcome.RESOLVE:
                    metrics.resolve_fn = 1
                elif expected == TerminalOutcome.ESCALATE:
                    metrics.escalate_fn = 1
                elif expected == TerminalOutcome.REQUEST_INFO:
                    metrics.request_info_fn = 1

        # Compute precision/recall/f1 for each outcome
        for outcome, tp, fp, fn in [
            ("resolve", metrics.resolve_tp, metrics.resolve_fp, metrics.resolve_fn),
            ("escalate", metrics.escalate_tp, metrics.escalate_fp, metrics.escalate_fn),
            ("request_info", metrics.request_info_tp, metrics.request_info_fp, metrics.request_info_fn),
        ]:
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0

            # Store in a dynamic way
            setattr(metrics, f"{outcome}_precision", prec)
            setattr(metrics, f"{outcome}_recall", rec)
            setattr(metrics, f"{outcome}_f1", f1)

        return metrics

    def evaluate_risk_classification(
        self,
        risk_assessment: RiskAssessment,
        ground_truth: GroundTruth,
    ) -> DecisionMetrics:
        """Evaluate risk level classification against the ground-truth decision."""
        metrics = DecisionMetrics()
        metrics.total_cases = 1

        expected_risk = self._EXPECTED_RISK_MAP.get(ground_truth.expected_decision)
        predicted_risk = risk_assessment.risk_level

        if expected_risk is not None and predicted_risk == expected_risk:
            metrics.risk_correct = 1
        metrics.risk_accuracy = 1.0 if metrics.risk_correct == 1 else 0.0

        return metrics

    def evaluate_escalation(
        self,
        guardrail_result: GuardrailDecisionResult,
        investigation_result: InvestigationResult,
        ground_truth: GroundTruth,
    ) -> DecisionMetrics:
        """Evaluate escalation against the ground-truth expected decision."""
        metrics = DecisionMetrics()
        metrics.total_cases = 1

        expected_escalation = ground_truth.expected_decision == "ESCALATE"
        actual_escalation = investigation_result.outcome == TerminalOutcome.ESCALATE

        if expected_escalation == actual_escalation:
            metrics.escalation_correct = 1
            metrics.escalation_accuracy = 1.0
        else:
            metrics.escalation_accuracy = 0.0

        return metrics

    def evaluate_full_decision(
        self,
        investigation_result: InvestigationResult,
        risk_assessment: RiskAssessment,
        guardrail_result: GuardrailDecisionResult,
        action_plan: ActionPlan,
        ground_truth: GroundTruth,
    ) -> DecisionResult:
        """Evaluate the complete decision pipeline."""
        outcome_metrics = self.evaluate_investigation_outcome(investigation_result, ground_truth)
        risk_metrics = self.evaluate_risk_classification(risk_assessment, ground_truth)
        escalation_metrics = self.evaluate_escalation(guardrail_result, investigation_result, ground_truth)

        per_case = [{
            "invoice_id": ground_truth.invoice_id,
            "investigation_outcome": investigation_result.outcome.value if investigation_result.outcome else None,
            "expected_decision": ground_truth.expected_decision,
            "risk_level": risk_assessment.risk_level.value,
            "guardrail_decision": guardrail_result.decision.value,
            "action_type": action_plan.action_type.value if action_plan.action_type else None,
            "outcome_correct": outcome_metrics.correct_decisions == 1,
            "risk_correct": risk_metrics.risk_correct == 1,
            "escalation_correct": escalation_metrics.escalation_correct == 1,
        }]

        return DecisionResult(
            investigation_outcome_metrics=outcome_metrics,
            risk_classification_metrics=risk_metrics,
            escalation_metrics=escalation_metrics,
            per_case=per_case,
        )

    def evaluate_batch(
        self,
        results: List[Dict[str, Any]],  # List of dicts with all evaluation inputs
        ground_truths: List[GroundTruth],
    ) -> DecisionResult:
        """Evaluate a batch of decisions."""
        gt_map = {gt.invoice_id: gt for gt in ground_truths}

        all_outcome = DecisionMetrics()
        all_risk = DecisionMetrics()
        all_escalation = DecisionMetrics()
        per_case = []

        for r in results:
            gt = gt_map.get(r.get("invoice_id"))
            if not gt:
                continue

            inv_result = r.get("investigation_result")
            risk_assess = r.get("risk_assessment")
            guardrail = r.get("guardrail_result")
            action_plan = r.get("action_plan")

            if inv_result:
                om = self.evaluate_investigation_outcome(inv_result, gt)
                all_outcome.total_cases += om.total_cases
                all_outcome.correct_decisions += om.correct_decisions
                all_outcome.resolve_tp += om.resolve_tp
                all_outcome.resolve_fp += om.resolve_fp
                all_outcome.resolve_fn += om.resolve_fn
                all_outcome.escalate_tp += om.escalate_tp
                all_outcome.escalate_fp += om.escalate_fp
                all_outcome.escalate_fn += om.escalate_fn
                all_outcome.request_info_tp += om.request_info_tp
                all_outcome.request_info_fp += om.request_info_fp
                all_outcome.request_info_fn += om.request_info_fn

            if risk_assess:
                rm = self.evaluate_risk_classification(risk_assess, gt)
                all_risk.total_cases += rm.total_cases
                all_risk.risk_correct += rm.risk_correct

            if guardrail and inv_result:
                em = self.evaluate_escalation(guardrail, inv_result, gt)
                all_escalation.total_cases += em.total_cases
                all_escalation.escalation_correct += em.escalation_correct

            per_case.append({
                "invoice_id": r.get("invoice_id"),
                "outcome_correct": om.correct_decisions == 1 if inv_result else None,
                "risk_correct": rm.risk_correct == 1 if risk_assess else None,
                "escalation_correct": em.escalation_correct == 1 if guardrail and inv_result else None,
            })

        # Compute aggregate metrics
        if all_outcome.total_cases > 0:
            all_outcome.accuracy = all_outcome.correct_decisions / all_outcome.total_cases
        if all_risk.total_cases > 0:
            all_risk.risk_accuracy = all_risk.risk_correct / all_risk.total_cases
        if all_escalation.total_cases > 0:
            all_escalation.escalation_accuracy = all_escalation.escalation_correct / all_escalation.total_cases

        return DecisionResult(
            investigation_outcome_metrics=all_outcome,
            risk_classification_metrics=all_risk,
            escalation_metrics=all_escalation,
            per_case=per_case,
        )