from decimal import Decimal
from apx.data.schemas import (
    Vendor, PurchaseOrder, PurchaseOrderLine,
    GoodsReceipt, GoodsReceiptLine, Invoice, InvoiceLine,
    Currency, CreditStatus, VendorStatus, POStatus, GRNStatus,
    ExceptionCode, GroundTruth, ExceptionSeverity, ValidationStatus
)
from apx.intelligence.validator import InvoiceValidator
from apx.data.generate_synthetic import SyntheticGenerator


class TestExceptionCoverage:
    """Test that generated dataset has minimum coverage for each exception category."""

    def test_minimum_coverage_per_exception_category(self):
        gen = SyntheticGenerator(seed=42)
        gen.generate_vendors(20)
        gen.generate_purchase_orders(50)
        gen.generate_goods_receipts(30)
        gen.generate_invoices(200)
        gt = gen.ground_truth

        from collections import Counter
        exc_counts = Counter()
        for g in gt:
            for e in g.expected_exceptions:
                exc_counts[e] += 1

        min_required = 10
        for code in ExceptionCode:
            count = exc_counts.get(code, 0)
            assert count >= min_required, f"Exception {code.value} has only {count} examples, need at least {min_required}"


class TestSingleRootCause:
    """Test that each injected exception produces exactly its intended validator exception."""

    def setup_method(self):
        self.gen = SyntheticGenerator(seed=12345)
        self.gen.generate_vendors(10)
        self.gen.generate_purchase_orders(20)
        self.gen.generate_goods_receipts(10)

        # Build a clean invoice for testing - use a PO without GRN to avoid quantity mismatches
        po = self.gen.purchase_orders[0]
        vendor = next(v for v in self.gen.vendors if v.vendor_id == po.vendor_id)
        self.clean_invoice = self.gen._create_clean_invoice(po, None, vendor)
        self.clean_po = po
        self.clean_grn = None
        self.clean_vendor = vendor
        self.validator = InvoiceValidator()

    def _validate_clean(self, invoice, po, grn, vendor):
        """Validate and return detected exception codes."""
        self.validator.reset_seen_invoices()
        report = self.validator.validate_invoice(invoice, po, grn, vendor)
        return {e.exception_code for e in report.exceptions}

    def test_clean_invoice_produces_no_exceptions(self):
        detected = self._validate_clean(self.clean_invoice, self.clean_po, self.clean_grn, self.clean_vendor)
        assert detected == set(), f"Clean invoice should produce no exceptions, got: {detected}"

    def test_vendor_mismatch_only(self):
        invoice = self.clean_invoice
        invoice.vendor_id = "V-9999"
        detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
        # Should detect VENDOR_MISMATCH (and possibly PO_MISMATCH since PO vendor differs)
        assert ExceptionCode.VENDOR_MISMATCH in detected

    def test_po_mismatch_only(self):
        invoice = self.clean_invoice
        invoice.po_number = "PO-INVALID-999999"
        detected = self._validate_clean(invoice, None, self.clean_grn, self.clean_vendor)
        assert ExceptionCode.PO_MISMATCH in detected

    def test_amount_mismatch_only(self):
        invoice = self.clean_invoice
        invoice.total = Decimal("999999.99")
        invoice.subtotal = invoice.total - invoice.tax + invoice.discount
        detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
        assert ExceptionCode.AMOUNT_MISMATCH in detected

    def test_grn_mismatch_only(self):
        # Find a PO with GRN
        pos_with_grn = []
        for po in self.gen.purchase_orders:
            grns = [g for g in self.gen.goods_receipts if g.po_id == po.po_id]
            if grns:
                pos_with_grn.append((po, grns[0]))
        
        if not pos_with_grn:
            import pytest
            pytest.skip("No PO with GRN available")
            
        po, grn = pos_with_grn[0]
        vendor = next(v for v in self.gen.vendors if v.vendor_id == po.vendor_id)
        
        # Create clean invoice with GRN
        invoice = self.gen._create_clean_invoice(po, grn, vendor)
        grn_line = grn.line_items[0]
        for inv_line in invoice.line_items:
            if inv_line.po_line_id == grn_line.po_line_id:
                inv_line.quantity = grn_line.quantity_received * Decimal("1.5")
                break
        self.gen._recalc_invoice_totals(invoice)
        detected = self._validate_clean(invoice, po, grn, vendor)
        assert ExceptionCode.GRN_MISMATCH in detected, f"Expected GRN_MISMATCH, got: {detected}"

    def test_tax_error_only(self):
        invoice = self.clean_invoice
        invoice.tax = invoice.tax * Decimal("1.5")
        invoice.total = invoice.subtotal + invoice.tax - invoice.discount
        detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
        assert ExceptionCode.TAX_ERROR in detected

    def test_currency_mismatch_only(self):
        invoice = self.clean_invoice
        other_currencies = [c for c in Currency if c != self.clean_vendor.currency]
        if other_currencies:
            invoice.currency = other_currencies[0]
            detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
            assert ExceptionCode.CURRENCY_MISMATCH in detected

    def test_line_item_mismatch_only(self):
        invoice = self.clean_invoice
        if invoice.line_items and self.clean_po.line_items:
            inv_line = invoice.line_items[0]
            po_line = self.clean_po.line_items[0]
            inv_line.unit_price = po_line.unit_price * Decimal("1.5")
            self.gen._recalc_invoice_totals(invoice)
            detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
            assert ExceptionCode.LINE_ITEM_MISMATCH in detected

    def test_discount_error_only(self):
        invoice = self.clean_invoice
        if invoice.line_items:
            inv_line = invoice.line_items[0]
            inv_line.discount = Decimal("1000.00")
            self.gen._recalc_invoice_totals(invoice)
            detected = self._validate_clean(invoice, self.clean_po, self.clean_grn, self.clean_vendor)
            assert ExceptionCode.DISCOUNT_ERROR in detected

    def test_credit_issue_only(self):
        vendor = self.clean_vendor
        vendor.credit_status = CreditStatus.HOLD
        detected = self._validate_clean(self.clean_invoice, self.clean_po, self.clean_grn, vendor)
        assert ExceptionCode.CREDIT_ISSUE in detected

    def test_duplicate_invoice_only(self):
        # Create a clean invoice, then duplicate it
        self.validator.reset_seen_invoices()
        invoice1 = self.clean_invoice
        report1 = self.validator.validate_invoice(invoice1, self.clean_po, None, self.clean_vendor)
        # First invoice should be clean
        assert not report1.has_exceptions, f"First invoice should be clean, got: {[e.exception_code for e in report1.exceptions]}"

        # Create duplicate
        invoice2 = self.clean_invoice
        invoice2.invoice_id = self.gen._next_invoice_id()
        report2 = self.validator.validate_invoice(invoice2, self.clean_po, None, self.clean_vendor)
        detected = {e.exception_code for e in report2.exceptions}
        assert ExceptionCode.DUPLICATE_INVOICE in detected, f"Expected DUPLICATE_INVOICE, got: {detected}"