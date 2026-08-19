from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from decimal import Decimal

from apx.data.schemas import Invoice, PurchaseOrder, Vendor, GoodsReceipt


@dataclass
class FieldComparison:
    """Result of comparing a single field."""
    field_name: str
    expected: Any
    actual: Any
    match: bool
    match_type: str  # "exact", "numeric_close", "missing", "unexpected"


@dataclass
class ExtractionResult:
    """Result of extraction evaluation."""
    invoice_id: str
    total_fields: int
    matched_fields: int
    missing_fields: int
    unexpected_fields: int
    exact_match_rate: float
    field_comparisons: List[FieldComparison] = field(default_factory=list)
    field_accuracy: Dict[str, float] = field(default_factory=dict)
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0


class ExtractionEvaluator:
    """
    Evaluates extracted invoice/business fields against ground truth.

    Reports field-level accuracy, precision, recall, F1, and exact-match rate.
    """

    # Fields to evaluate for each entity type
    INVOICE_FIELDS = [
        "invoice_id", "vendor_id", "invoice_number", "po_number",
        "invoice_date", "due_date", "currency", "subtotal", "tax", "total", "discount"
    ]
    PO_FIELDS = [
        "po_id", "vendor_id", "po_number", "po_date", "currency",
        "subtotal", "tax", "total"
    ]
    VENDOR_FIELDS = [
        "vendor_id", "vendor_name", "tax_id", "currency",
        "payment_terms_days", "credit_status", "status"
    ]
    GRN_FIELDS = [
        "grn_id", "po_id", "vendor_id", "receipt_date", "status"
    ]

    def __init__(self, numeric_tolerance: Decimal = Decimal("0.01")):
        self.numeric_tolerance = numeric_tolerance

    def evaluate_invoice(
        self,
        extracted: Invoice,
        ground_truth: Invoice,
    ) -> ExtractionResult:
        """Evaluate extracted invoice against ground truth."""
        return self._evaluate_entity(
            extracted=extracted,
            ground_truth=ground_truth,
            fields=self.INVOICE_FIELDS,
            entity_type="invoice",
        )

    def evaluate_po(
        self,
        extracted: PurchaseOrder,
        ground_truth: PurchaseOrder,
    ) -> ExtractionResult:
        """Evaluate extracted PO against ground truth."""
        return self._evaluate_entity(
            extracted=extracted,
            ground_truth=ground_truth,
            fields=self.PO_FIELDS,
            entity_type="po",
        )

    def evaluate_vendor(
        self,
        extracted: Vendor,
        ground_truth: Vendor,
    ) -> ExtractionResult:
        """Evaluate extracted vendor against ground truth."""
        return self._evaluate_entity(
            extracted=extracted,
            ground_truth=ground_truth,
            fields=self.VENDOR_FIELDS,
            entity_type="vendor",
        )

    def evaluate_grn(
        self,
        extracted: GoodsReceipt,
        ground_truth: GoodsReceipt,
    ) -> ExtractionResult:
        """Evaluate extracted GRN against ground truth."""
        return self._evaluate_entity(
            extracted=extracted,
            ground_truth=ground_truth,
            fields=self.GRN_FIELDS,
            entity_type="grn",
        )

    def _evaluate_entity(
        self,
        extracted: Any,
        ground_truth: Any,
        fields: List[str],
        entity_type: str,
    ) -> ExtractionResult:
        """Generic entity evaluation."""
        comparisons = []
        matched = 0
        missing = 0
        unexpected = 0

        # Get all fields from both objects
        extracted_dict = extracted.model_dump() if hasattr(extracted, "model_dump") else extracted.__dict__
        truth_dict = ground_truth.model_dump() if hasattr(ground_truth, "model_dump") else ground_truth.__dict__

        # Compare expected fields
        for field in fields:
            expected = truth_dict.get(field)
            actual = extracted_dict.get(field)

            if expected is None and actual is None:
                match = True
                match_type = "exact"
            elif expected is None:
                match = False
                match_type = "unexpected"
                unexpected += 1
            elif actual is None:
                match = False
                match_type = "missing"
                missing += 1
            else:
                match, match_type = self._compare_values(expected, actual)
                if match:
                    matched += 1
                else:
                    missing += 1  # Treat mismatch as missing for recall

            comparisons.append(FieldComparison(
                field_name=field,
                expected=expected,
                actual=actual,
                match=match,
                match_type=match_type,
            ))

        # Check for unexpected fields in extracted
        extracted_fields = set(extracted_dict.keys())
        expected_fields = set(truth_dict.keys())
        for field in extracted_fields - expected_fields:
            unexpected += 1
            comparisons.append(FieldComparison(
                field_name=field,
                expected=None,
                actual=extracted_dict.get(field),
                match=False,
                match_type="unexpected",
            ))

        total_fields = len(fields) + unexpected
        exact_match_rate = matched / total_fields if total_fields > 0 else 0.0

        # Per-field accuracy
        field_accuracy = {}
        for comp in comparisons:
            if comp.field_name in fields:
                field_accuracy[comp.field_name] = 1.0 if comp.match else 0.0

        # Precision, Recall, F1
        precision = matched / (matched + unexpected) if (matched + unexpected) > 0 else 0.0
        recall = matched / (matched + missing) if (matched + missing) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return ExtractionResult(
            invoice_id=getattr(extracted, "invoice_id", getattr(extracted, "po_id", getattr(extracted, "vendor_id", getattr(extracted, "grn_id", "unknown")))),
            total_fields=total_fields,
            matched_fields=matched,
            missing_fields=missing,
            unexpected_fields=unexpected,
            exact_match_rate=exact_match_rate,
            field_comparisons=comparisons,
            field_accuracy=field_accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
        )

    def _compare_values(self, expected: Any, actual: Any) -> tuple[bool, str]:
        """Compare two values with appropriate tolerance."""
        # Handle Decimal comparison
        if isinstance(expected, Decimal) and isinstance(actual, Decimal):
            if abs(expected - actual) <= self.numeric_tolerance:
                return True, "numeric_close"
            return False, "mismatch"

        # Handle numeric types
        if isinstance(expected, (int, float, Decimal)) and isinstance(actual, (int, float, Decimal)):
            try:
                exp_dec = Decimal(str(expected))
                act_dec = Decimal(str(actual))
                if abs(exp_dec - act_dec) <= self.numeric_tolerance:
                    return True, "numeric_close"
            except:
                pass
            return False, "mismatch"

        # Handle date comparison
        if hasattr(expected, "year") and hasattr(actual, "year"):
            return expected == actual, "exact" if expected == actual else "mismatch"

        # Default string/exact comparison
        return str(expected) == str(actual), "exact" if str(expected) == str(actual) else "mismatch"

    def evaluate_batch(
        self,
        extracted_invoices: List[Invoice],
        ground_truth_invoices: List[Invoice],
    ) -> List[ExtractionResult]:
        """Evaluate a batch of invoices."""
        results = []
        truth_map = {inv.invoice_id: inv for inv in ground_truth_invoices}
        for extracted in extracted_invoices:
            if extracted.invoice_id in truth_map:
                results.append(self.evaluate_invoice(extracted, truth_map[extracted.invoice_id]))
        return results

    def aggregate_results(self, results: List[ExtractionResult]) -> ExtractionResult:
        """Aggregate multiple extraction results."""
        if not results:
            return ExtractionResult(
                invoice_id="aggregate",
                total_fields=0, matched_fields=0, missing_fields=0,
                unexpected_fields=0, exact_match_rate=0.0,
            )

        total_fields = sum(r.total_fields for r in results)
        matched_fields = sum(r.matched_fields for r in results)
        missing_fields = sum(r.missing_fields for r in results)
        unexpected_fields = sum(r.unexpected_fields for r in results)
        exact_match_rate = matched_fields / total_fields if total_fields > 0 else 0.0

        # Aggregate field accuracy
        field_accuracy: Dict[str, List[float]] = {}
        for r in results:
            for field, acc in r.field_accuracy.items():
                if field not in field_accuracy:
                    field_accuracy[field] = []
                field_accuracy[field].append(acc)

        avg_field_accuracy = {
            field: sum(vals) / len(vals) for field, vals in field_accuracy.items()
        }

        precision = matched_fields / (matched_fields + unexpected_fields) if (matched_fields + unexpected_fields) > 0 else 0.0
        recall = matched_fields / (matched_fields + missing_fields) if (matched_fields + missing_fields) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return ExtractionResult(
            invoice_id="aggregate",
            total_fields=total_fields,
            matched_fields=matched_fields,
            missing_fields=missing_fields,
            unexpected_fields=unexpected_fields,
            exact_match_rate=exact_match_rate,
            field_accuracy=avg_field_accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
        )