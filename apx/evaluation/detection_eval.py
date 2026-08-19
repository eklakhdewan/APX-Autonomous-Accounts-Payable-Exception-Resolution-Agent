from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from apx.data.schemas import ExceptionReport, ExceptionCode, GroundTruth


@dataclass
class ExceptionMetrics:
    """Metrics for a single exception type."""
    exception_code: ExceptionCode
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


@dataclass
class DetectionResult:
    """Result of detection evaluation."""
    total_exceptions: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    per_exception: Dict[ExceptionCode, ExceptionMetrics] = field(default_factory=dict)
    invoice_results: List[Dict[str, Any]] = field(default_factory=list)


class DetectionEvaluator:
    """
    Evaluates deterministic exception detection against ground truth.

    Reports exception precision, recall, F1, per-exception-type metrics,
    false positives, and false negatives.
    """

    def __init__(self):
        pass

    def evaluate(
        self,
        detected_report: ExceptionReport,
        ground_truth: GroundTruth,
    ) -> DetectionResult:
        """Evaluate a single invoice's exception detection."""
        detected_codes = set(detected_report.exception_codes)
        expected_codes = set(ground_truth.expected_exceptions)

        tp = len(detected_codes & expected_codes)
        fp = len(detected_codes - expected_codes)
        fn = len(expected_codes - detected_codes)

        # Per-exception metrics
        per_exception: Dict[ExceptionCode, ExceptionMetrics] = {}
        all_codes = detected_codes | expected_codes
        for code in all_codes:
            metrics = ExceptionMetrics(exception_code=code)
            in_detected = code in detected_codes
            in_expected = code in expected_codes
            if in_detected and in_expected:
                metrics.tp = 1
            elif in_detected:
                metrics.fp = 1
            elif in_expected:
                metrics.fn = 1

            metrics.precision = metrics.tp / (metrics.tp + metrics.fp) if (metrics.tp + metrics.fp) > 0 else 0.0
            metrics.recall = metrics.tp / (metrics.tp + metrics.fn) if (metrics.tp + metrics.fn) > 0 else 0.0
            metrics.f1 = 2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall) if (metrics.precision + metrics.recall) > 0 else 0.0

            per_exception[code] = metrics

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return DetectionResult(
            total_exceptions=len(expected_codes),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1=f1,
            per_exception=per_exception,
            invoice_results=[{
                "invoice_id": ground_truth.invoice_id,
                "detected": [c.value for c in detected_codes],
                "expected": [c.value for c in expected_codes],
                "tp": tp, "fp": fp, "fn": fn,
            }],
        )

    def evaluate_batch(
        self,
        detected_reports: List[ExceptionReport],
        ground_truths: List[GroundTruth],
    ) -> DetectionResult:
        """Evaluate a batch of exception reports."""
        if not detected_reports or not ground_truths:
            return DetectionResult()

        truth_map = {gt.invoice_id: gt for gt in ground_truths}

        all_tp = 0
        all_fp = 0
        all_fn = 0
        per_exception: Dict[ExceptionCode, ExceptionMetrics] = defaultdict(lambda: ExceptionMetrics(exception_code=ExceptionCode.VENDOR_MISMATCH))
        invoice_results = []

        for report in detected_reports:
            if report.invoice_id not in truth_map:
                continue

            gt = truth_map[report.invoice_id]
            detected_codes = set(report.exception_codes)
            expected_codes = set(gt.expected_exceptions)

            tp = len(detected_codes & expected_codes)
            fp = len(detected_codes - expected_codes)
            fn = len(expected_codes - detected_codes)

            all_tp += tp
            all_fp += fp
            all_fn += fn

            all_codes = detected_codes | expected_codes
            for code in all_codes:
                if code not in per_exception:
                    per_exception[code] = ExceptionMetrics(exception_code=code)
                m = per_exception[code]
                in_detected = code in detected_codes
                in_expected = code in expected_codes
                if in_detected and in_expected:
                    m.tp += 1
                elif in_detected:
                    m.fp += 1
                elif in_expected:
                    m.fn += 1

            # Update precision/recall/f1 for each exception
            for code, m in per_exception.items():
                m.precision = m.tp / (m.tp + m.fp) if (m.tp + m.fp) > 0 else 0.0
                m.recall = m.tp / (m.tp + m.fn) if (m.tp + m.fn) > 0 else 0.0
                m.f1 = 2 * m.precision * m.recall / (m.precision + m.recall) if (m.precision + m.recall) > 0 else 0.0

            invoice_results.append({
                "invoice_id": report.invoice_id,
                "detected": [c.value for c in detected_codes],
                "expected": [c.value for c in expected_codes],
                "tp": tp, "fp": fp, "fn": fn,
            })

        precision = all_tp / (all_tp + all_fp) if (all_tp + all_fp) > 0 else 0.0
        recall = all_tp / (all_tp + all_fn) if (all_tp + all_fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return DetectionResult(
            total_exceptions=sum(len(gt.expected_exceptions) for gt in ground_truths if gt.invoice_id in truth_map),
            true_positives=all_tp,
            false_positives=all_fp,
            false_negatives=all_fn,
            precision=precision,
            recall=recall,
            f1=f1,
            per_exception=dict(per_exception),
            invoice_results=invoice_results,
        )

    def evaluate_from_phase1_validator(
        self,
        validator_func,
        invoices: List,
        pos: List,
        grns: List,
        vendors: List,
        ground_truths: List[GroundTruth],
    ) -> DetectionResult:
        """Evaluate using the Phase 1 validator function."""
        from apx.intelligence.validator import InvoiceValidator

        if isinstance(validator_func, InvoiceValidator):
            validator = validator_func
        else:
            validator = InvoiceValidator()

        detected_reports = []
        for invoice in invoices:
            # Find matching PO, GRN, Vendor
            po = next((p for p in pos if p.po_number == invoice.po_number), None)
            grn = next((g for g in grns if g.po_id == po.po_id), None) if po else None
            vendor = next((v for v in vendors if v.vendor_id == invoice.vendor_id), None)

            if po and grn and vendor:
                report = validator.validate_invoice(invoice=invoice, po=po, grn=grn, vendor=vendor)
                detected_reports.append(report)

        return self.evaluate_batch(detected_reports, ground_truths)