from decimal import Decimal
from datetime import date
import pytest
from pydantic import ValidationError

from apx.data.schemas import (
    Vendor,
    PurchaseOrder,
    PurchaseOrderLine,
    GoodsReceipt,
    GoodsReceiptLine,
    Invoice,
    InvoiceLine,
    Currency,
    CreditStatus,
    VendorStatus,
    POStatus,
    GRNStatus,
    ExceptionCode,
    APException,
    ExceptionReport,
    GroundTruth,
    ValidationStatus,
)


class TestVendorSchema:
    def test_valid_vendor(self):
        vendor = Vendor(
            vendor_id="V-0001",
            vendor_name="Test Vendor",
            tax_id="TAX12345678",
            currency=Currency.USD,
            payment_terms_days=30,
            credit_status=CreditStatus.ACTIVE,
        )
        assert vendor.vendor_id == "V-0001"
        assert vendor.currency == Currency.USD

    def test_vendor_defaults(self):
        vendor = Vendor(vendor_id="V-0001", vendor_name="Test")
        assert vendor.currency == Currency.USD
        assert vendor.payment_terms_days == 30
        assert vendor.credit_status == CreditStatus.ACTIVE
        assert vendor.status == VendorStatus.ACTIVE

    def test_invalid_vendor_id_empty(self):
        with pytest.raises(ValidationError):
            Vendor(vendor_id="", vendor_name="Test")


class TestPurchaseOrderLineSchema:
    def test_valid_line(self):
        line = PurchaseOrderLine(
            line_id="L-0001",
            description="Item",
            quantity=Decimal("10"),
            unit_price=Decimal("100"),
            discount=Decimal("5"),
            tax_rate=Decimal("0.1"),
        )
        assert line.line_total() == Decimal("995")
        assert line.line_tax() == Decimal("99.5")

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValidationError):
            PurchaseOrderLine(line_id="L-1", description="x", quantity=Decimal("0"), unit_price=Decimal("10"))

    def test_tax_rate_bounds(self):
        with pytest.raises(ValidationError):
            PurchaseOrderLine(line_id="L-1", description="x", quantity=Decimal("10"), unit_price=Decimal("10"), tax_rate=Decimal("1.5"))


class TestPurchaseOrderSchema:
    def test_valid_po(self):
        line = PurchaseOrderLine(line_id="L-1", description="Item", quantity=Decimal("10"), unit_price=Decimal("100"), tax_rate=Decimal("0.1"))
        po = PurchaseOrder(
            po_id="PO-1",
            vendor_id="V-1",
            po_number="PO-1",
            po_date=date(2026, 1, 1),
            currency=Currency.USD,
            subtotal=Decimal("1000"),
            tax=Decimal("100"),
            total=Decimal("1100"),
            line_items=[line],
        )
        assert po.total == Decimal("1100")

    def test_po_total_validation(self):
        line = PurchaseOrderLine(line_id="L-1", description="Item", quantity=Decimal("10"), unit_price=Decimal("100"))
        with pytest.raises(ValidationError):
            PurchaseOrder(
                po_id="PO-1",
                vendor_id="V-1",
                po_number="PO-1",
                po_date=date(2026, 1, 1),
                currency=Currency.USD,
                subtotal=Decimal("999"),
                tax=Decimal("100"),
                total=Decimal("1100"),
                line_items=[line],
            )


class TestInvoiceSchema:
    def test_valid_invoice(self):
        line = InvoiceLine(line_id="L-1", description="Item", quantity=Decimal("10"), unit_price=Decimal("100"), tax_rate=Decimal("0.1"))
        inv = Invoice(
            invoice_id="INV-1",
            vendor_id="V-1",
            invoice_number="INV-1",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            currency=Currency.USD,
            subtotal=Decimal("1000"),
            tax=Decimal("100"),
            total=Decimal("1100"),
            line_items=[line],
        )
        assert inv.total == Decimal("1100")

    def test_invoice_total_validation(self):
        line = InvoiceLine(line_id="L-1", description="Item", quantity=Decimal("10"), unit_price=Decimal("100"))
        with pytest.raises(ValidationError):
            Invoice(
                invoice_id="INV-1",
                vendor_id="V-1",
                invoice_number="INV-1",
                invoice_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                currency=Currency.USD,
                subtotal=Decimal("999"),
                tax=Decimal("100"),
                total=Decimal("1100"),
                line_items=[line],
            )


class TestExceptionSchemas:
    def test_ap_exception(self):
        exc = APException(
            exception_code=ExceptionCode.VENDOR_MISMATCH,
            severity="HIGH",
            message="Test",
            details={"key": "value"},
        )
        assert exc.exception_code == ExceptionCode.VENDOR_MISMATCH

    def test_exception_report_add_exception(self):
        report = ExceptionReport(invoice_id="INV-1", vendor_id="V-1")
        report.add_exception(ExceptionCode.VENDOR_MISMATCH, "HIGH", "Test message", {"detail": "x"})
        assert report.has_exceptions
        assert ExceptionCode.VENDOR_MISMATCH in report.exception_codes
        assert report.validation_status == ValidationStatus.EXCEPTIONS

    def test_ground_truth(self):
        gt = GroundTruth(
            invoice_id="INV-1",
            expected_exceptions=[ExceptionCode.VENDOR_MISMATCH],
            expected_decision="REVIEW",
        )
        assert ExceptionCode.VENDOR_MISMATCH in gt.expected_exceptions


class TestSerialization:
    def test_vendor_serialization(self):
        vendor = Vendor(vendor_id="V-1", vendor_name="Test")
        data = vendor.model_dump(mode="json")
        assert data["vendor_id"] == "V-1"
        assert data["currency"] == "USD"

    def test_invoice_serialization(self):
        line = InvoiceLine(line_id="L-1", description="Item", quantity=Decimal("10"), unit_price=Decimal("100"), tax_rate=Decimal("0.1"))
        inv = Invoice(
            invoice_id="INV-1",
            vendor_id="V-1",
            invoice_number="INV-1",
            invoice_date=date(2026, 1, 1),
            due_date=date(2026, 2, 1),
            currency=Currency.USD,
            subtotal=Decimal("1000"),
            tax=Decimal("100"),
            total=Decimal("1100"),
            line_items=[line],
        )
        data = inv.model_dump(mode="json")
        assert data["invoice_id"] == "INV-1"
        assert data["currency"] == "USD"
        assert isinstance(data["line_items"], list)