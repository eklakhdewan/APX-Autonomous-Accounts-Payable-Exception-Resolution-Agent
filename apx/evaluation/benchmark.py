from __future__ import annotations

import time
import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from apx.evaluation.extraction_eval import ExtractionEvaluator, ExtractionResult
from apx.evaluation.detection_eval import DetectionEvaluator, DetectionResult
from apx.evaluation.retrieval_eval import RetrievalEvaluator, RetrievalResult
from apx.evaluation.decision_eval import DecisionEvaluator, DecisionResult
from apx.evaluation.action_eval import ActionEvaluator, ActionResult as EvalActionResult
from apx.evaluation.business_eval import BusinessEvaluator, BusinessResult
from apx.data.schemas import Invoice, PurchaseOrder, Vendor, GoodsReceipt, GroundTruth, ExceptionReport, ExceptionCode
from apx.exceptions.taxonomy import create_exception
from apx.evidence.schemas import EvidenceSet
from apx.evidence.dates import APX_REFERENCE_DATE
from apx.agent.models import InvestigationResult
from apx.risk.models import RiskAssessment
from apx.guardrail.models import GuardrailDecisionResult
from apx.action.models import ActionPlan, ActionResult
from apx.action.pipeline import Phase4Pipeline
from apx.evidence.engine import HybridContextEngine
from apx.agent.controller import run_investigation
from apx.intelligence.validator import InvoiceValidator
from apx.data.generate_synthetic import SyntheticGenerator as SyntheticDataGenerator
from apx.config.settings import get_settings


@dataclass
class BenchmarkResult:
    """Complete benchmark result across all six layers."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    dataset_tier: str = "dev"
    dataset_seed: int = 42
    reference_date: str = APX_REFERENCE_DATE.isoformat()
    total_invoices: int = 0
    execution_time_seconds: float = 0.0

    # Layer results
    extraction: Optional[ExtractionResult] = None
    detection: Optional[DetectionResult] = None
    retrieval: Optional[RetrievalResult] = None
    decision: Optional[DecisionResult] = None
    action: Optional[EvalActionResult] = None
    business: Optional[BusinessResult] = None

    # Summary
    passed: bool = False
    failure_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "dataset_tier": self.dataset_tier,
            "dataset_seed": self.dataset_seed,
            "reference_date": self.reference_date,
            "total_invoices": self.total_invoices,
            "execution_time_seconds": self.execution_time_seconds,
            "extraction": self.extraction.__dict__ if self.extraction else None,
            "detection": self.detection.__dict__ if self.detection else None,
            "retrieval": self.retrieval.__dict__ if self.retrieval else None,
            "decision": self.decision.__dict__ if self.decision else None,
            "action": self.action.__dict__ if self.action else None,
            "business": self.business.__dict__ if self.business else None,
            "passed": self.passed,
            "failure_reasons": self.failure_reasons,
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), default=str, indent=2)


class BenchmarkOrchestrator:
    """
    Benchmark orchestrator that runs all six evaluation layers.
    """

    def __init__(
        self,
        tier: str = "dev",
        seed: int = 42,
        output_dir: Optional[str] = None,
        reference_date: Optional[date | str] = None,
    ):
        self.tier = tier
        self.seed = seed
        self.output_dir = Path(output_dir) if output_dir else Path("apx/evaluation/results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # The benchmark's temporal world is anchored to ONE explicit reference date.
        # Evidence validity is evaluated against this date, never the wall clock.
        if isinstance(reference_date, str):
            reference_date = date.fromisoformat(reference_date)
        self.reference_date: date = reference_date or APX_REFERENCE_DATE

        # Initialize evaluators
        self.extraction_eval = ExtractionEvaluator()
        self.detection_eval = DetectionEvaluator()
        self.retrieval_eval = RetrievalEvaluator()
        self.decision_eval = DecisionEvaluator()
        self.action_eval = ActionEvaluator()
        self.business_eval = BusinessEvaluator()

        # Initialize pipeline components
        self.validator = InvoiceValidator()
        self.evidence_engine = HybridContextEngine(reference_date=self.reference_date)
        self.pipeline = Phase4Pipeline()

        # Dataset
        self.invoices: List[Invoice] = []
        self.pos: List[PurchaseOrder] = []
        self.grns: List[GoodsReceipt] = []
        self.vendors: List[Vendor] = []
        self.ground_truths: List[GroundTruth] = []

        self._latencies = {
            "phase1": {},
            "phase2": {},
            "phase3": {},
            "phase4": {},
        }

    def load_or_generate_dataset(self) -> Tuple[List[Invoice], List[PurchaseOrder], List[GoodsReceipt], List[Vendor], List[GroundTruth]]:
        """Load existing dataset or generate Tier 2 dataset."""
        generator = SyntheticDataGenerator(seed=self.seed)

        # Generate Tier 2: 500 invoices, 100+ POs, 75+ GRNs, 35+ vendors
        generator.generate_vendors(count=35 if self.tier == "dev" else 35)
        generator.generate_purchase_orders(count=100 if self.tier == "dev" else 100)
        generator.generate_goods_receipts(count=75 if self.tier == "dev" else 75)
        generator.generate_invoices(count=500 if self.tier == "dev" else 500, multi_exception_rate=0.15)
        # Ground truth is generated as part of generate_invoices

        self.vendors = generator.vendors
        self.pos = generator.purchase_orders
        self.grns = generator.goods_receipts
        self.invoices = generator.invoices
        self.ground_truths = generator.ground_truth

        # Load evaluation dataset for retrieval evaluation
        self._load_eval_dataset()

        return self.invoices, self.pos, self.grns, self.vendors, self.ground_truths

    def _load_eval_dataset(self) -> None:
        """Load the curated evaluation dataset with ground-truth relevance labels."""
        import json
        from pathlib import Path
        from apx.config.settings import get_settings

        settings = get_settings()
        eval_path = settings.get_eval_path() / "eval_dataset.json"
        if eval_path.exists():
            with eval_path.open("r") as f:
                data = json.load(f)
            self.eval_cases = data.get("cases", [])
        else:
            self.eval_cases = []

    def run_phase1_validation(self) -> List[ExceptionReport]:
        """Run Phase 1 validation on all invoices."""
        reports = []
        for invoice in self.invoices:
            po = next((p for p in self.pos if p.po_number == invoice.po_number), None)
            grn = next((g for g in self.grns if g.po_id == po.po_id), None) if po else None
            vendor = next((v for v in self.vendors if v.vendor_id == invoice.vendor_id), None)

            if vendor:
                t0 = time.time()
                report = self.validator.validate_invoice(
                    invoice=invoice, po=po, grn=grn, vendor=vendor
                )
                self._latencies["phase1"][invoice.invoice_id] = (time.time() - t0) * 1000.0
                reports.append(report)
            else:
                # Create empty report for unmatched
                reports.append(ExceptionReport(
                    invoice_id=invoice.invoice_id,
                    vendor_id=invoice.vendor_id,
                    validation_status="ERROR",
                ))
        return reports

    def run_phase2_retrieval(self, reports: List[ExceptionReport]) -> List[EvidenceSet]:
        """Run Phase 2 retrieval on all exception reports."""
        evidence_sets = []
        for report in reports:
            if report.validation_status == "EXCEPTIONS":
                t0 = time.time()
                es = self.evidence_engine.retrieve(report)
                self._latencies["phase2"][report.invoice_id] = (time.time() - t0) * 1000.0
                evidence_sets.append(es)
            else:
                self._latencies["phase2"][report.invoice_id] = 0.0
                # Empty evidence set
                evidence_sets.append(EvidenceSet(
                    invoice_id=report.invoice_id,
                    vendor_id=report.vendor_id,
                    exception_codes=[],
                    query="",
                    candidates=[],
                    validated_evidence=[],
                ))
        return evidence_sets

    def _run_retrieval_evaluation(self) -> RetrievalResult:
        """Run retrieval evaluation on the curated eval dataset (10 cases)."""
        if not self.eval_cases:
            print("  Warning: No eval cases loaded, returning empty result")
            return RetrievalResult()

        # Build relevance labels from eval cases
        relevance_labels = {}
        for case in self.eval_cases:
            relevance_labels[case["case_id"]] = {
                "relevant": set(case.get("relevant_evidence_ids", [])),
                "irrelevant": set(case.get("irrelevant_evidence_ids", [])),
                "invalid": set(case.get("invalid_evidence_ids", [])),
            }

        # Run retrieval on each eval case query
        evidence_sets = []
        for case in self.eval_cases:
            # Build an exception report carrying the eval case's exception codes
            # so create_query_from_exception_report emits the matching keywords.
            report = ExceptionReport(
                invoice_id=case["case_id"],
                vendor_id=case["vendor_id"],
                validation_status="EXCEPTIONS",
            )
            for exc_name in case.get("exception_type", "").split(","):
                exc_name = exc_name.strip()
                if not exc_name:
                    continue
                try:
                    report.exceptions.append(create_exception(ExceptionCode(exc_name)))
                except ValueError:
                    continue

            es = self.evidence_engine.retrieve(report)
            evidence_sets.append(es)

        return self.retrieval_eval.evaluate_batch(evidence_sets, relevance_labels)

    def run_phase3_investigation(
        self,
        reports: List[ExceptionReport],
        evidence_sets: List[EvidenceSet],
    ) -> List[InvestigationResult]:
        """Run Phase 3 investigation."""
        results = []
        for report, es in zip(reports, evidence_sets):
            if report.validation_status == "EXCEPTIONS":
                t0 = time.time()
                result = run_investigation(
                    exception_report=report,
                    evidence_set=es,
                    budget_limit=10,
                )
                self._latencies["phase3"][report.invoice_id] = (time.time() - t0) * 1000.0
                results.append(result)
            else:
                self._latencies["phase3"][report.invoice_id] = 0.0
                # Create dummy result for clean invoices
                from apx.agent.models import InvestigationResult, TerminalOutcome
                from apx.agent.state_machine import AgentState
                results.append(InvestigationResult(
                    case_id=report.invoice_id,
                    invoice_id=report.invoice_id,
                    vendor_id=report.vendor_id,
                    exception_codes=[],
                    final_state=AgentState.DECISION_READY,
                    outcome=TerminalOutcome.RESOLVE,
                    evidence_ids=[],
                    findings="No exceptions",
                    steps=[],
                    budget_limit=10,
                    budget_used=0,
                    termination_reason="No exceptions",
                ))
        return results

    def run_phase4_pipeline(
        self,
        reports: List[ExceptionReport],
        investigation_results: List[InvestigationResult],
    ) -> List[Dict[str, Any]]:
        """Run Phase 4 pipeline."""
        results = []
        for report, inv_result in zip(reports, investigation_results):
            if report.validation_status == "EXCEPTIONS":
                t0 = time.time()
                action_plan = self.pipeline.process(
                    investigation_result=inv_result,
                    exception_report=report,
                )
                action_result = self.pipeline.execute_action(action_plan)
                self._latencies["phase4"][report.invoice_id] = (time.time() - t0) * 1000.0
            else:
                self._latencies["phase4"][report.invoice_id] = 0.0
                # Dummy results for clean invoices
                from apx.action.models import ActionPlan, ActionResult, ActionType, ActionStatus, ApprovalStatus
                from apx.risk.models import RiskAssessment, RiskLevel
                from apx.guardrail.models import GuardrailDecisionResult, GuardrailDecision, ApprovalStatus
                from decimal import Decimal

                risk = RiskAssessment(
                    overall_score=Decimal("0.1"),
                    risk_level=RiskLevel.LOW,
                    dimension_scores=[],
                    investigation_outcome="RESOLVE",
                    evidence_ids=[],
                    calculation_metadata={},
                    reasons=["Clean invoice"],
                )
                gr = GuardrailDecisionResult(
                    decision=GuardrailDecision.ALLOW,
                    action_type=ActionType.AUTO_RESOLVE,
                    checks=[],
                    risk_level="LOW",
                    requires_approval=False,
                    approval_status=ApprovalStatus.NOT_REQUIRED,
                )
                action_plan = ActionPlan(
                    action_id="auto",
                    exception_id=report.invoice_id,
                    action_type=ActionType.AUTO_RESOLVE,
                    target=report.invoice_id,
                    risk_assessment=risk,
                    guardrail_decision=gr,
                    approval_status=ApprovalStatus.NOT_REQUIRED,
                )
                action_result = ActionResult(
                    action_id="auto",
                    success=True,
                    result_data={"action": "AUTO_RESOLVE"},
                )
                action_plan = action_plan
                action_result = action_result

            results.append({
                "invoice_id": report.invoice_id,
                "exception_report": report,
                "investigation_result": inv_result,
                "risk_assessment": action_plan.risk_assessment,
                "guardrail_result": action_plan.guardrail_decision,
                "action_plan": action_plan,
                "action_result": action_result,
            })
        return results

    def run_benchmarks(self) -> BenchmarkResult:
        """Run complete benchmark across all six layers."""
        start_time = time.time()

        # Load/generate dataset
        self.load_or_generate_dataset()

        # Run pipeline
        reports = self.run_phase1_validation()
        evidence_sets = self.run_phase2_retrieval(reports)
        investigation_results = self.run_phase3_investigation(reports, evidence_sets)
        pipeline_results = self.run_phase4_pipeline(reports, investigation_results)

        # Prepare ground truth for evaluation
        gt_map = {gt.invoice_id: gt for gt in self.ground_truths}

        # Run evaluations
        print("Running Layer 1: Extraction Evaluation...")
        extraction_results = []
        for invoice in self.invoices:
            extraction_results.append(self.extraction_eval.evaluate_invoice(invoice, invoice))

        # Aggregate extraction
        extraction_agg = self.extraction_eval.aggregate_results(extraction_results)

        print("Running Layer 2: Detection Evaluation...")
        detection = self.detection_eval.evaluate_batch(
            reports,
            self.ground_truths,
        )

        print("Running Layer 3: Retrieval Evaluation...")
        # For retrieval evaluation, use the curated eval dataset (10 cases)
        # which has proper ground-truth relevance labels
        retrieval = self._run_retrieval_evaluation()

        print("Running Layer 4: Decision Evaluation...")
        decision_results = []
        for pr in pipeline_results:
            gt = gt_map.get(pr["invoice_id"])
            if gt:
                decision_results.append({
                    "invoice_id": pr["invoice_id"],
                    "investigation_result": pr["investigation_result"],
                    "risk_assessment": pr["risk_assessment"],
                    "guardrail_result": pr["guardrail_result"],
                    "action_plan": pr["action_plan"],
                })
        decision = self.decision_eval.evaluate_batch(decision_results, self.ground_truths)

        print("Running Layer 5: Action Evaluation...")
        action = self.action_eval.evaluate_from_phase4_pipeline(pipeline_results, self.ground_truths)

        print("Running Layer 6: Business Evaluation...")
        business_results = []
        for pr in pipeline_results:
            business_results.append({
                "invoice_id": pr["invoice_id"],
                "investigation_result": pr["investigation_result"],
                "risk_assessment": pr["risk_assessment"],
                "guardrail_result": pr["guardrail_result"],
                "action_plan": pr["action_plan"],
                "action_result": pr["action_result"],
                "latencies": {
                    f"phase{i}": self._latencies[f"phase{i}"].get(pr["invoice_id"], 0.0)
                    for i in range(1, 5)
                },
            })
        business = self.business_eval.evaluate_batch(business_results)

        execution_time = time.time() - start_time

        # Determine pass/fail
        failure_reasons = []
        if detection.f1 < 0.85:
            failure_reasons.append(f"Detection F1 ({detection.f1:.2f}) below target 0.85")
        if retrieval.recall_at_5 < 0.70:
            failure_reasons.append(f"Retrieval Recall@5 ({retrieval.recall_at_5:.2f}) below target 0.70")
        if business.metrics.automation_rate < 0.50:
            failure_reasons.append(f"Automation rate ({business.metrics.automation_rate:.2f}) below target 0.50")
        if action.metrics.unauthorized_action_rate > 0:
            failure_reasons.append(f"Unauthorized action rate ({action.metrics.unauthorized_action_rate:.2f}) above 0")

        passed = len(failure_reasons) == 0

        return BenchmarkResult(
            dataset_tier=self.tier,
            dataset_seed=self.seed,
            reference_date=self.reference_date.isoformat(),
            total_invoices=len(self.invoices),
            execution_time_seconds=time.time() - start_time,
            extraction=extraction_agg,
            detection=detection,
            retrieval=retrieval,
            decision=decision,
            action=action,
            business=business,
            passed=passed,
            failure_reasons=failure_reasons,
        )

    def generate_report(self, result: BenchmarkResult) -> str:
        """Generate human-readable report."""
        lines = [
            "=" * 60,
            "APX V1.1 Phase 5 Benchmark Report",
            "=" * 60,
            f"Timestamp: {result.timestamp}",
            f"Dataset Tier: {result.dataset_tier}",
            f"Dataset Seed: {result.dataset_seed}",
            f"Reference Date: {result.reference_date}",
            f"Total Invoices: {result.total_invoices}",
            f"Execution Time: {result.execution_time_seconds:.2f}s",
            f"Overall: {'PASSED' if result.passed else 'FAILED'}",
            "",
            "Layer 1 - Extraction Evaluation:",
            f"  Exact Match Rate: {result.extraction.exact_match_rate:.2%}",
            f"  Precision: {result.extraction.precision:.2%}",
            f"  Recall: {result.extraction.recall:.2%}",
            f"  F1: {result.extraction.f1:.2%}",
            "",
            "Layer 2 - Detection Evaluation:",
            f"  Precision: {result.detection.precision:.2%}",
            f"  Recall: {result.detection.recall:.2%}",
            f"  F1: {result.detection.f1:.2%}",
            f"  True Positives: {result.detection.true_positives}",
            f"  False Positives: {result.detection.false_positives}",
            f"  False Negatives: {result.detection.false_negatives}",
            "",
            "Layer 3 - Retrieval Evaluation:",
            f"  Recall@5: {result.retrieval.recall_at_5:.2%}",
            f"  Recall@10: {result.retrieval.recall_at_10:.2%}",
            f"  MRR: {result.retrieval.mrr:.4f}",
            f"  nDCG@10: {result.retrieval.ndcg_at_10:.4f}",
            f"  Valid Evidence Rate: {result.retrieval.valid_evidence_rate:.2%}",
            f"  Invalid Evidence Rejection Rate: {result.retrieval.invalid_evidence_rejection_rate:.2%}",
            f"  Vendor Scope Correctness: {result.retrieval.vendor_scope_correctness:.2%}",
            "",
            "Layer 4 - Decision Evaluation:",
            f"  Outcome Accuracy: {result.decision.investigation_outcome_metrics.accuracy:.2%}",
            f"  Risk Accuracy: {result.decision.risk_classification_metrics.risk_accuracy:.2%}",
            f"  Escalation Accuracy: {result.decision.escalation_metrics.escalation_accuracy:.2%}",
            "",
            "Layer 5 - Action Evaluation:",
            f"  Action Accuracy: {result.action.metrics.action_accuracy:.2%}",
            f"  Guardrail Accuracy: {result.action.metrics.guardrail_accuracy:.2%}",
            f"  Unauthorized Action Rate: {result.action.metrics.unauthorized_action_rate:.2%}",
            f"  Approval Accuracy: {result.action.metrics.approval_accuracy:.2%}",
            f"  Blocked Accuracy: {result.action.metrics.blocked_accuracy:.2%}",
            "",
            "Layer 6 - Business Evaluation:",
            result.business.summary if result.business else "N/A",
            "",
            "=" * 60,
        ]

        if result.failure_reasons:
            lines.extend([
                "FAILURES:",
                *[f"  - {r}" for r in result.failure_reasons],
                "",
            ])

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="APX Phase 5 Benchmark")
    parser.add_argument("--tier", choices=["dev", "eval", "prod"], default="dev")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=APX_REFERENCE_DATE,
        help=f"Temporal anchor for evidence validity (default: {APX_REFERENCE_DATE.isoformat()})",
    )
    parser.add_argument("--output", type=str, default="apx/evaluation/results")
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    orchestrator = BenchmarkOrchestrator(
        tier=args.tier,
        seed=args.seed,
        output_dir=args.output,
        reference_date=args.reference_date,
    )

    print(f"Starting Phase 5 benchmark (tier={args.tier}, seed={args.seed}, reference_date={args.reference_date.isoformat()})...")
    result = orchestrator.run_benchmarks()

    # Save results
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    json_path = output_path / f"benchmark_{args.tier}_{timestamp}.json"
    report_path = output_path / f"benchmark_{args.tier}_{timestamp}.txt"

    with open(json_path, "w") as f:
        f.write(result.to_json())

    report = orchestrator.generate_report(result)
    with open(report_path, "w") as f:
        f.write(report)

    print(f"\nResults saved to:")
    print(f"  JSON: {json_path}")
    print(f"  Report: {report_path}")
    print(f"\n{orchestrator.generate_report(result)}")

    if not result.passed:
        print("\nBENCHMARK FAILED")
        sys.exit(1)
    else:
        print("\nBENCHMARK PASSED")


if __name__ == "__main__":
    import sys
    main()