from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from apx.action.models import ActionPlan, ActionResult, ActionType, ActionStatus
from apx.agent.models import InvestigationResult, TerminalOutcome
from apx.guardrail.models import GuardrailDecisionResult, GuardrailDecision
from apx.risk.models import RiskAssessment


@dataclass
class BusinessMetrics:
    """Business-level metrics."""
    total_cases: int = 0

    # Automation metrics
    automated_cases: int = 0
    automation_rate: float = 0.0
    escalated_cases: int = 0
    escalation_rate: float = 0.0
    requested_info_cases: int = 0
    request_info_rate: float = 0.0

    # Time metrics (in milliseconds)
    avg_total_latency_ms: float = 0.0
    avg_phase1_latency_ms: float = 0.0
    avg_phase2_latency_ms: float = 0.0
    avg_phase3_latency_ms: float = 0.0
    avg_phase4_latency_ms: float = 0.0

    # Cost metrics
    estimated_cost_usd: float = 0.0
    cost_per_case_usd: float = 0.0

    # Resolution metrics
    resolved_cases: int = 0
    resolution_rate: float = 0.0

    # Quality metrics
    correct_decisions: int = 0
    decision_accuracy: float = 0.0

    # Guardrail safety
    unauthorized_actions: int = 0
    unauthorized_action_rate: float = 0.0

    # Per-outcome breakdown
    outcome_breakdown: Dict[str, int] = field(default_factory=dict)


@dataclass
class BusinessResult:
    """Result of business evaluation."""
    metrics: BusinessMetrics = field(default_factory=BusinessMetrics)
    per_case: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""


class BusinessEvaluator:
    """
    Reports business-level outcomes supported by the existing data.

    At minimum: automation rate, escalation rate, estimated time saved, cost, latency.
    """

    def __init__(
        self,
        phase1_cost_per_invoice: float = 0.001,  # USD
        phase2_cost_per_invoice: float = 0.005,
        phase3_cost_per_invoice: float = 0.01,
        phase4_cost_per_invoice: float = 0.002,
        manual_review_cost_usd: float = 5.0,  # Cost of human review
        auto_resolve_savings_usd: float = 10.0,  # Savings from auto-resolution
    ):
        self.phase1_cost = phase1_cost_per_invoice
        self.phase2_cost = phase2_cost_per_invoice
        self.phase3_cost = phase3_cost_per_invoice
        self.phase4_cost = phase4_cost_per_invoice
        self.manual_review_cost = manual_review_cost_usd
        self.auto_resolve_savings = auto_resolve_savings_usd

    def evaluate(
        self,
        investigation_result: InvestigationResult,
        risk_assessment: RiskAssessment,
        guardrail_result: GuardrailDecisionResult,
        action_plan: ActionPlan,
        action_result: ActionResult,
        latencies: Dict[str, float],  # phase -> latency_ms
    ) -> BusinessMetrics:
        """Evaluate business metrics for a single case."""
        metrics = BusinessMetrics()
        metrics.total_cases = 1

        # Track outcome
        outcome = investigation_result.outcome
        if outcome:
            outcome_str = outcome.value
            metrics.outcome_breakdown[outcome_str] = metrics.outcome_breakdown.get(outcome_str, 0) + 1

        if outcome == TerminalOutcome.RESOLVE:
            metrics.automated_cases += 1
            metrics.resolved_cases += 1
        elif outcome == TerminalOutcome.ESCALATE:
            metrics.escalated_cases += 1
        elif outcome == TerminalOutcome.REQUEST_INFO:
            metrics.requested_info_cases += 1

        # Latency metrics
        for phase, latency in latencies.items():
            setattr(metrics, f"avg_{phase}_latency_ms", latency)

        total_latency = sum(latencies.values())
        metrics.avg_total_latency_ms = total_latency

        # Cost metrics
        case_cost = (
            self.phase1_cost + self.phase2_cost + self.phase3_cost + self.phase4_cost
        )
        metrics.estimated_cost_usd = case_cost

        if action_result and action_result.success:
            if outcome == TerminalOutcome.RESOLVE:
                # Auto-resolved - savings from not doing manual review
                metrics.estimated_cost_usd -= self.auto_resolve_savings
            elif outcome == TerminalOutcome.ESCALATE:
                # Escalated - add manual review cost
                metrics.estimated_cost_usd += self.manual_review_cost

        # Quality metrics
        metrics.correct_decisions = 1 if action_result and action_result.success else 0
        metrics.decision_accuracy = metrics.correct_decisions / metrics.total_cases if metrics.total_cases > 0 else 0.0

        # Guardrail safety
        if guardrail_result and guardrail_result.decision == "BLOCK" and action_result and action_result.success:
            metrics.unauthorized_actions += 1
        metrics.unauthorized_action_rate = metrics.unauthorized_actions / metrics.total_cases if metrics.total_cases > 0 else 0.0

        # Compute rates
        metrics.automation_rate = metrics.automated_cases / metrics.total_cases if metrics.total_cases > 0 else 0.0
        metrics.escalation_rate = metrics.escalated_cases / metrics.total_cases if metrics.total_cases > 0 else 0.0
        metrics.request_info_rate = metrics.requested_info_cases / metrics.total_cases if metrics.total_cases > 0 else 0.0
        metrics.resolution_rate = metrics.resolved_cases / metrics.total_cases if metrics.total_cases > 0 else 0.0

        return metrics

    def evaluate_batch(
        self,
        results: List[Dict[str, Any]],  # Each dict has all evaluation inputs + latencies
    ) -> BusinessResult:
        """Evaluate a batch of cases."""
        aggregate = BusinessMetrics()
        per_case = []

        for r in results:
            inv_result = r.get("investigation_result")
            risk = r.get("risk_assessment")
            gr = r.get("guardrail_result")
            ap = r.get("action_plan")
            ar = r.get("action_result")
            latencies = r.get("latencies", {})

            m = self.evaluate(inv_result, risk, gr, ap, ar, latencies)

            # Aggregate
            aggregate.total_cases += m.total_cases
            aggregate.automated_cases += m.automated_cases
            aggregate.escalated_cases += m.escalated_cases
            aggregate.requested_info_cases += m.requested_info_cases
            aggregate.resolved_cases += m.resolved_cases
            aggregate.correct_decisions += m.correct_decisions
            aggregate.unauthorized_actions += m.unauthorized_actions
            aggregate.estimated_cost_usd += m.estimated_cost_usd

            # Sum latencies
            for phase in ["phase1", "phase2", "phase3", "phase4"]:
                key = f"avg_{phase}_latency_ms"
                val = getattr(m, key, 0.0)
                aggregate_latency = getattr(aggregate, key, 0.0)
                setattr(aggregate, key, aggregate_latency + val)

            # Merge outcome breakdown
            for outcome, count in m.outcome_breakdown.items():
                aggregate.outcome_breakdown[outcome] = aggregate.outcome_breakdown.get(outcome, 0) + count

            per_case.append({
                "invoice_id": r.get("invoice_id"),
                "outcome": m.outcome_breakdown,
                "total_latency_ms": m.avg_total_latency_ms,
                "cost_usd": m.estimated_cost_usd,
                "correct": m.correct_decisions == 1,
                "unauthorized": m.unauthorized_actions > 0,
            })

        # Compute aggregate rates
        if aggregate.total_cases > 0:
            aggregate.automation_rate = aggregate.automated_cases / aggregate.total_cases
            aggregate.escalation_rate = aggregate.escalated_cases / aggregate.total_cases
            aggregate.request_info_rate = aggregate.requested_info_cases / aggregate.total_cases
            aggregate.resolution_rate = aggregate.resolved_cases / aggregate.total_cases
            aggregate.decision_accuracy = aggregate.correct_decisions / aggregate.total_cases
            aggregate.unauthorized_action_rate = aggregate.unauthorized_actions / aggregate.total_cases
            aggregate.cost_per_case_usd = aggregate.estimated_cost_usd / aggregate.total_cases

            # Average latencies
            for phase in ["phase1", "phase2", "phase3", "phase4"]:
                key = f"avg_{phase}_latency_ms"
                val = getattr(aggregate, key, 0.0)
                setattr(aggregate, key, val / aggregate.total_cases)

            aggregate.avg_total_latency_ms = sum(
                getattr(aggregate, f"avg_{phase}_latency_ms", 0.0)
                for phase in ["phase1", "phase2", "phase3", "phase4"]
            )

        # Generate summary
        summary = self._generate_summary(aggregate)

        return BusinessResult(
            metrics=aggregate,
            per_case=per_case,
            summary=summary,
        )

    def _generate_summary(self, metrics: BusinessMetrics) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Business Evaluation Summary",
            f"============================",
            f"Total Cases: {metrics.total_cases}",
            f"",
            f"Automation Rate: {metrics.automation_rate:.1%} ({metrics.automated_cases}/{metrics.total_cases})",
            f"Escalation Rate: {metrics.escalation_rate:.1%} ({metrics.escalated_cases}/{metrics.total_cases})",
            f"Request Info Rate: {metrics.request_info_rate:.1%} ({metrics.requested_info_cases}/{metrics.total_cases})",
            f"Resolution Rate: {metrics.resolution_rate:.1%} ({metrics.resolved_cases}/{metrics.total_cases})",
            f"",
            f"Decision Accuracy: {metrics.decision_accuracy:.1%}",
            f"Unauthorized Action Rate: {metrics.unauthorized_action_rate:.1%}",
            f"",
            f"Average Total Latency: {metrics.avg_total_latency_ms:.1f} ms",
            f"  Phase 1 (Validation): {metrics.avg_phase1_latency_ms:.1f} ms",
            f"  Phase 2 (Retrieval): {metrics.avg_phase2_latency_ms:.1f} ms",
            f"  Phase 3 (Investigation): {metrics.avg_phase3_latency_ms:.1f} ms",
            f"  Phase 4 (Decision/Action): {metrics.avg_phase4_latency_ms:.1f} ms",
            f"",
            f"Total Estimated Cost: ${metrics.estimated_cost_usd:.4f}",
            f"Cost per Case: ${metrics.cost_per_case_usd:.4f}",
            f"",
            f"Outcome Breakdown: {metrics.outcome_breakdown}",
        ]
        return "\n".join(lines)