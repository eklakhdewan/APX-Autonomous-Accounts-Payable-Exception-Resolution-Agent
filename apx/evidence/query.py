from __future__ import annotations

from typing import Any

from apx.data.schemas import ExceptionReport, ExceptionCode
from apx.evidence.schemas import EvidenceType


class QueryBuilder:
    def __init__(self):
        self.exception_keywords = {
            ExceptionCode.VENDOR_MISMATCH: [
                "vendor mismatch", "vendor validation", "vendor verification",
                "supplier mismatch", "vendor master data"
            ],
            ExceptionCode.PO_MISMATCH: [
                "purchase order mismatch", "PO validation", "PO reference",
                "purchase order number", "PO matching"
            ],
            ExceptionCode.AMOUNT_MISMATCH: [
                "amount mismatch", "price variance", "total variance",
                "invoice amount", "price tolerance", "amount tolerance"
            ],
            ExceptionCode.GRN_MISMATCH: [
                "goods receipt mismatch", "quantity variance", "receipt quantity",
                "GRN quantity", "received quantity", "three-way match"
            ],
            ExceptionCode.DUPLICATE_INVOICE: [
                "duplicate invoice", "duplicate detection", "invoice duplication",
                "duplicate prevention", "invoice matching"
            ],
            ExceptionCode.TAX_ERROR: [
                "tax error", "tax calculation", "tax validation", "tax variance",
                "tax rate", "tax calculation error"
            ],
            ExceptionCode.CURRENCY_MISMATCH: [
                "currency mismatch", "currency validation", "foreign currency",
                "exchange rate", "currency conversion"
            ],
            ExceptionCode.LINE_ITEM_MISMATCH: [
                "line item mismatch", "line item variance", "item price",
                "item quantity", "PO line matching", "three-way match line"
            ],
            ExceptionCode.DISCOUNT_ERROR: [
                "discount error", "discount validation", "early payment discount",
                "discount terms", "discount variance"
            ],
            ExceptionCode.CREDIT_ISSUE: [
                "credit issue", "credit hold", "credit status", "vendor credit",
                "credit limit", "credit check"
            ],
        }

    def build_query(self, exception_report: ExceptionReport) -> str:
        parts = []

        # Add exception type keywords
        for exc in exception_report.exceptions:
            keywords = self.exception_keywords.get(exc.exception_code, [])
            parts.extend(keywords[:3])

        # Add vendor context
        parts.append(f"vendor {exception_report.vendor_id}")

        # Add invoice context
        parts.append(f"invoice {exception_report.invoice_id}")

        # Add general AP terms
        parts.extend(["accounts payable", "invoice validation", "exception resolution"])

        # Deduplicate while preserving order
        seen = set()
        unique_parts = []
        for part in parts:
            if part not in seen:
                seen.add(part)
                unique_parts.append(part)

        return " ".join(unique_parts)

    def build_structured_query(self, exception_report: ExceptionReport) -> dict[str, Any]:
        return {
            "exception_codes": [e.exception_code.value for e in exception_report.exceptions],
            "vendor_id": exception_report.vendor_id,
            "invoice_id": exception_report.invoice_id,
            "exception_types": [e.exception_code.value for e in exception_report.exceptions],
            "keywords": self.build_query(exception_report),
        }


def create_query_from_exception_report(exception_report: ExceptionReport) -> str:
    builder = QueryBuilder()
    return builder.build_query(exception_report)