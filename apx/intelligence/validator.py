from __future__ import annotations

from decimal import Decimal
from typing import Optional

from apx.config.settings import get_settings
from apx.data.schemas import (
    Invoice,
    PurchaseOrder,
    GoodsReceipt,
    Vendor,
    ExceptionReport,
    ExceptionCode,
    ExceptionSeverity,
    ValidationStatus,
)
from apx.exceptions.taxonomy import create_exception


class InvoiceValidator:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self.tolerance = self.settings.get_tolerance()
        self._seen_invoices: set[tuple[str, str]] = set()

    def reset_seen_invoices(self):
        self._seen_invoices.clear()

    def validate_invoice(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        grn: Optional[GoodsReceipt],
        vendor: Vendor,
    ) -> ExceptionReport:
        report = ExceptionReport(
            invoice_id=invoice.invoice_id,
            vendor_id=invoice.vendor_id,
            validation_status=ValidationStatus.CLEAN,
        )

        self._check_vendor_match(invoice, po, vendor, report)
        self._check_po_match(invoice, po, vendor, report)
        self._check_amount_match(invoice, po, report)
        self._check_grn_match(invoice, grn, report)
        self._check_duplicate_invoice(invoice, report)
        self._check_tax_calculation(invoice, report)
        self._check_currency_match(invoice, po, vendor, report)
        self._check_line_item_match(invoice, po, report)
        self._check_discount(invoice, po, report)
        self._check_credit_status(vendor, report)

        return report

    def _check_vendor_match(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        vendor: Vendor,
        report: ExceptionReport,
    ):
        if po and invoice.vendor_id != po.vendor_id:
            report.add_exception(
                ExceptionCode.VENDOR_MISMATCH,
                ExceptionSeverity.HIGH,
                f"Invoice vendor {invoice.vendor_id} does not match PO vendor {po.vendor_id}",
                {"invoice_vendor": invoice.vendor_id, "po_vendor": po.vendor_id},
            )
        elif invoice.vendor_id != vendor.vendor_id:
            report.add_exception(
                ExceptionCode.VENDOR_MISMATCH,
                ExceptionSeverity.HIGH,
                f"Invoice vendor {invoice.vendor_id} does not match vendor record {vendor.vendor_id}",
                {"invoice_vendor": invoice.vendor_id, "vendor_record": vendor.vendor_id},
            )

    def _check_po_match(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        vendor: Vendor,
        report: ExceptionReport,
    ):
        if not invoice.po_number:
            report.add_exception(
                ExceptionCode.PO_MISMATCH,
                ExceptionSeverity.HIGH,
                "Invoice missing PO reference",
                {"invoice_id": invoice.invoice_id},
            )
            return

        if not po:
            report.add_exception(
                ExceptionCode.PO_MISMATCH,
                ExceptionSeverity.HIGH,
                f"Referenced PO {invoice.po_number} not found",
                {"po_number": invoice.po_number},
            )
            return

        if po.vendor_id != vendor.vendor_id:
            report.add_exception(
                ExceptionCode.PO_MISMATCH,
                ExceptionSeverity.HIGH,
                f"PO {po.po_id} belongs to vendor {po.vendor_id}, not invoice vendor {vendor.vendor_id}",
                {"po_id": po.po_id, "po_vendor": po.vendor_id, "invoice_vendor": vendor.vendor_id},
            )

    def _check_amount_match(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        report: ExceptionReport,
    ):
        if not po:
            return

        pct_tol = Decimal(str(self.tolerance.amount_percentage))
        abs_tol = Decimal(str(self.tolerance.amount_absolute))

        expected_total = po.total
        actual_total = invoice.total

        diff = abs(actual_total - expected_total)
        allowed_diff = max(abs_tol, expected_total * pct_tol)

        if diff > allowed_diff:
            report.add_exception(
                ExceptionCode.AMOUNT_MISMATCH,
                ExceptionSeverity.MEDIUM,
                f"Invoice total {actual_total} differs from PO total {expected_total} by {diff} (allowed: {allowed_diff})",
                {
                    "invoice_total": str(actual_total),
                    "po_total": str(expected_total),
                    "difference": str(diff),
                    "allowed_tolerance": str(allowed_diff),
                },
            )

    def _check_grn_match(
        self,
        invoice: Invoice,
        grn: Optional[GoodsReceipt],
        report: ExceptionReport,
    ):
        if not grn or not grn.line_items:
            return

        grn_quantities = {}
        for line in grn.line_items:
            grn_quantities[line.po_line_id] = line.quantity_received

        for inv_line in invoice.line_items:
            if inv_line.po_line_id and inv_line.po_line_id in grn_quantities:
                grn_qty = grn_quantities[inv_line.po_line_id]
                inv_qty = inv_line.quantity

                pct_tol = Decimal(str(self.tolerance.quantity_percentage))
                allowed_diff = max(Decimal("0"), grn_qty * pct_tol)

                if inv_qty > grn_qty + allowed_diff:
                    report.add_exception(
                        ExceptionCode.GRN_MISMATCH,
                        ExceptionSeverity.MEDIUM,
                        f"Invoiced quantity {inv_qty} exceeds received quantity {grn_qty} for line {inv_line.po_line_id}",
                        {
                            "po_line_id": inv_line.po_line_id,
                            "invoiced_quantity": str(inv_qty),
                            "received_quantity": str(grn_qty),
                            "difference": str(inv_qty - grn_qty),
                        },
                    )

    def _check_duplicate_invoice(
        self,
        invoice: Invoice,
        report: ExceptionReport,
    ):
        key = (invoice.vendor_id, invoice.invoice_number)
        if key in self._seen_invoices:
            report.add_exception(
                ExceptionCode.DUPLICATE_INVOICE,
                ExceptionSeverity.HIGH,
                f"Duplicate invoice detected: vendor {invoice.vendor_id}, invoice number {invoice.invoice_number}",
                {"vendor_id": invoice.vendor_id, "invoice_number": invoice.invoice_number},
            )
        else:
            self._seen_invoices.add(key)

    def _check_tax_calculation(
        self,
        invoice: Invoice,
        report: ExceptionReport,
    ):
        calc_tax = sum(line.line_tax() for line in invoice.line_items)
        declared_tax = invoice.tax

        pct_tol = Decimal(str(self.tolerance.tax_percentage))
        allowed_diff = max(Decimal("0.01"), declared_tax * pct_tol)

        if abs(calc_tax - declared_tax) > allowed_diff:
            report.add_exception(
                ExceptionCode.TAX_ERROR,
                ExceptionSeverity.MEDIUM,
                f"Tax calculation mismatch: declared {declared_tax}, calculated {calc_tax}",
                {
                    "declared_tax": str(declared_tax),
                    "calculated_tax": str(calc_tax),
                    "difference": str(abs(calc_tax - declared_tax)),
                },
            )

    def _check_currency_match(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        vendor: Vendor,
        report: ExceptionReport,
    ):
        mismatches = []

        if po and invoice.currency != po.currency:
            mismatches.append(f"Invoice currency {invoice.currency} != PO currency {po.currency}")

        if invoice.currency != vendor.currency:
            mismatches.append(f"Invoice currency {invoice.currency} != Vendor currency {vendor.currency}")

        if mismatches:
            report.add_exception(
                ExceptionCode.CURRENCY_MISMATCH,
                ExceptionSeverity.HIGH,
                "; ".join(mismatches),
                {
                    "invoice_currency": invoice.currency.value,
                    "po_currency": po.currency.value if po else None,
                    "vendor_currency": vendor.currency.value,
                },
            )

    def _check_line_item_match(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        report: ExceptionReport,
    ):
        if not po or not po.line_items:
            return

        po_lines = {line.line_id: line for line in po.line_items}

        for inv_line in invoice.line_items:
            if inv_line.po_line_id and inv_line.po_line_id in po_lines:
                po_line = po_lines[inv_line.po_line_id]

                if inv_line.unit_price != po_line.unit_price:
                    report.add_exception(
                        ExceptionCode.LINE_ITEM_MISMATCH,
                        ExceptionSeverity.MEDIUM,
                        f"Unit price mismatch for line {inv_line.po_line_id}: invoice {inv_line.unit_price} != PO {po_line.unit_price}",
                        {
                            "po_line_id": inv_line.po_line_id,
                            "invoice_unit_price": str(inv_line.unit_price),
                            "po_unit_price": str(po_line.unit_price),
                        },
                    )

                if inv_line.quantity != po_line.quantity:
                    report.add_exception(
                        ExceptionCode.LINE_ITEM_MISMATCH,
                        ExceptionSeverity.MEDIUM,
                        f"Quantity mismatch for line {inv_line.po_line_id}: invoice {inv_line.quantity} != PO {po_line.quantity}",
                        {
                            "po_line_id": inv_line.po_line_id,
                            "invoice_quantity": str(inv_line.quantity),
                            "po_quantity": str(po_line.quantity),
                        },
                    )

    def _check_discount(
        self,
        invoice: Invoice,
        po: Optional[PurchaseOrder],
        report: ExceptionReport,
    ):
        if not po or not po.line_items:
            return

        po_lines = {line.line_id: line for line in po.line_items}

        for inv_line in invoice.line_items:
            if inv_line.po_line_id and inv_line.po_line_id in po_lines:
                po_line = po_lines[inv_line.po_line_id]

                if inv_line.discount != po_line.discount:
                    pct_tol = Decimal(str(self.tolerance.discount_percentage))
                    allowed_diff = max(Decimal("0.01"), po_line.discount * pct_tol)

                    if abs(inv_line.discount - po_line.discount) > allowed_diff:
                        report.add_exception(
                            ExceptionCode.DISCOUNT_ERROR,
                            ExceptionSeverity.LOW,
                            f"Discount mismatch for line {inv_line.po_line_id}: invoice {inv_line.discount} != PO {po_line.discount}",
                            {
                                "po_line_id": inv_line.po_line_id,
                                "invoice_discount": str(inv_line.discount),
                                "po_discount": str(po_line.discount),
                                "difference": str(abs(inv_line.discount - po_line.discount)),
                            },
                        )

    def _check_credit_status(
        self,
        vendor: Vendor,
        report: ExceptionReport,
    ):
        if vendor.credit_status in (CreditStatus.HOLD, CreditStatus.SUSPENDED, CreditStatus.BLOCKED):
            report.add_exception(
                ExceptionCode.CREDIT_ISSUE,
                ExceptionSeverity.HIGH,
                f"Vendor credit status is {vendor.credit_status.value}",
                {"vendor_id": vendor.vendor_id, "credit_status": vendor.credit_status.value},
            )


from apx.data.schemas import CreditStatus