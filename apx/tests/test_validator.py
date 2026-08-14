from decimal import Decimal
from datetime import date
import pytest

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
    POStatus,
    GRNStatus,
    ExceptionCode,
    ExceptionSeverity,
    ValidationStatus,
)
from apx.intelligence.validator import InvoiceValidator
from apx.config.settings import get_settings


@pytest.fixture
def validator():
    return InvoiceValidator()


@pytest.fixture
def sample_vendor():
    return Vendor(
        vendor_id="V-0001",
        vendor_name="Test Vendor",
        tax_id="TAX12345678",
        currency=Currency.USD,
        payment_terms_days=30,
        credit_status=CreditStatus.ACTIVE,
    )


@pytest.fixture
def sample_po(sample_vendor):
    line = PurchaseOrderLine(
        line_id="L-0001",
        description="Test Item",
        quantity=Decimal("100"),
        unit_price=Decimal("50.00"),
        discount=Decimal("0"),
        tax_rate=Decimal("0.10"),
    )
    return PurchaseOrder(
        po_id="PO-0001",
        vendor_id=sample_vendor.vendor_id,
        po_number="PO-0001",
        po_date=date(2026, 1, 15),
        currency=Currency.USD,
        subtotal=Decimal("5000.00"),
        tax=Decimal("500.00"),
        total=Decimal("5500.00"),
        line_items=[line],
        status=POStatus.OPEN,
    )


@pytest.fixture
def sample_grn(sample_po):
    line = GoodsReceiptLine(
        line_id="GRN-L-0001",
        po_line_id="L-0001",
        quantity_received=Decimal("100"),
    )
    return GoodsReceipt(
        grn_id="GRN-0001",
        po_id=sample_po.po_id,
        vendor_id=sample_po.vendor_id,
        receipt_date=date(2026, 2, 1),
        line_items=[line],
        status=GRNStatus.RECEIVED,
    )


@pytest.fixture
def valid_invoice(sample_po, sample_vendor):
    line = InvoiceLine(
        line_id="INV-L-0001",
        description="Test Item",
        po_line_id="L-0001",
        quantity=Decimal("100"),
        unit_price=Decimal("50.00"),
        discount=Decimal("0"),
        tax_rate=Decimal("0.10"),
    )
    return Invoice(
        invoice_id="INV-0001",
        vendor_id=sample_vendor.vendor_id,
        invoice_number="INV-0001",
        po_number=sample_po.po_number,
        invoice_date=date(2026, 2, 15),
        due_date=date(2026, 3, 15),
        currency=Currency.USD,
        subtotal=Decimal("5000.00"),
        tax=Decimal("500.00"),
        total=Decimal("5500.00"),
        discount=Decimal("0"),
        line_items=[line],
    )


class TestR1VendorMismatch:
    def test_vendor_match_clean(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.VENDOR_MISMATCH not in report.exception_codes

    def test_vendor_mismatch_invoice_vs_po(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.vendor_id = "V-9999"
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.VENDOR_MISMATCH in report.exception_codes
        exc = next(e for e in report.exceptions if e.exception_code == ExceptionCode.VENDOR_MISMATCH)
        assert exc.severity == ExceptionSeverity.HIGH

    def test_vendor_mismatch_invoice_vs_vendor_record(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        sample_vendor.vendor_id = "V-9999"
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.VENDOR_MISMATCH in report.exception_codes


class TestR2POMismatch:
    def test_po_match_clean(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.PO_MISMATCH not in report.exception_codes

    def test_po_missing(self, validator, valid_invoice, sample_grn, sample_vendor):
        valid_invoice.po_number = "PO-9999"
        report = validator.validate_invoice(valid_invoice, None, sample_grn, sample_vendor)
        assert ExceptionCode.PO_MISMATCH in report.exception_codes

    def test_po_invalid_reference(self, validator, valid_invoice, sample_grn, sample_vendor):
        valid_invoice.po_number = "PO-INVALID"
        report = validator.validate_invoice(valid_invoice, None, sample_grn, sample_vendor)
        assert ExceptionCode.PO_MISMATCH in report.exception_codes

    def test_po_wrong_vendor(self, validator, valid_invoice, sample_po, sample_grn):
        other_vendor = Vendor(
            vendor_id="V-9999",
            vendor_name="Other Vendor",
            currency=Currency.USD,
            credit_status=CreditStatus.ACTIVE,
        )
        sample_po.vendor_id = other_vendor.vendor_id
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, other_vendor)
        assert ExceptionCode.VENDOR_MISMATCH in report.exception_codes


class TestR3AmountMismatch:
    def test_amount_match_clean(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.AMOUNT_MISMATCH not in report.exception_codes

    def test_amount_mismatch_exceeds_tolerance(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.total = Decimal("6000.00")
        valid_invoice.subtotal = Decimal("5500.00")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.AMOUNT_MISMATCH in report.exception_codes

    def test_amount_tolerance_boundary(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        tolerance = validator.tolerance
        max_allowed = sample_po.total * (Decimal("1") + Decimal(str(tolerance.amount_percentage)))
        valid_invoice.total = max_allowed
        valid_invoice.subtotal = max_allowed
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.AMOUNT_MISMATCH not in report.exception_codes

        valid_invoice.total = max_allowed + Decimal("0.01")
        valid_invoice.subtotal = max_allowed + Decimal("0.01")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.AMOUNT_MISMATCH in report.exception_codes


class TestR4GRNMismatch:
    def test_grn_match_clean(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.GRN_MISMATCH not in report.exception_codes

    def test_grn_quantity_mismatch(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        sample_grn.line_items[0].quantity_received = Decimal("90")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.GRN_MISMATCH in report.exception_codes

    def test_grn_no_receipt(self, validator, valid_invoice, sample_po, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, None, sample_vendor)
        assert ExceptionCode.GRN_MISMATCH not in report.exception_codes


class TestR5DuplicateInvoice:
    def test_unique_invoice(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.DUPLICATE_INVOICE not in report.exception_codes


class TestR6TaxError:
    def test_tax_valid(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.TAX_ERROR not in report.exception_codes

    def test_tax_error(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.tax = Decimal("600.00")
        valid_invoice.total = Decimal("5600.00")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.TAX_ERROR in report.exception_codes


class TestR7CurrencyMismatch:
    def test_currency_valid(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.CURRENCY_MISMATCH not in report.exception_codes

    def test_currency_mismatch_invoice_po(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.currency = Currency.EUR
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.CURRENCY_MISMATCH in report.exception_codes

    def test_currency_mismatch_invoice_vendor(self, validator, valid_invoice, sample_po, sample_grn):
        vendor_eur = Vendor(
            vendor_id="V-0001",
            vendor_name="Test Vendor",
            currency=Currency.EUR,
            credit_status=CreditStatus.ACTIVE,
        )
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, vendor_eur)
        assert ExceptionCode.CURRENCY_MISMATCH in report.exception_codes


class TestR8LineItemMismatch:
    def test_line_items_match(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.LINE_ITEM_MISMATCH not in report.exception_codes

    def test_line_item_price_mismatch(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.line_items[0].unit_price = Decimal("60.00")
        valid_invoice.subtotal = Decimal("6000.00")
        valid_invoice.total = Decimal("6600.00")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.LINE_ITEM_MISMATCH in report.exception_codes

    def test_line_item_quantity_mismatch(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.line_items[0].quantity = Decimal("120")
        valid_invoice.subtotal = Decimal("6000.00")
        valid_invoice.total = Decimal("6600.00")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.LINE_ITEM_MISMATCH in report.exception_codes


class TestR9DiscountError:
    def test_discount_valid(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.DISCOUNT_ERROR not in report.exception_codes

    def test_discount_error(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        sample_po.line_items[0].discount = Decimal("100.00")
        sample_po.subtotal = Decimal("4900.00")
        sample_po.total = Decimal("5390.00")

        valid_invoice.line_items[0].discount = Decimal("200.00")
        valid_invoice.subtotal = Decimal("4800.00")
        valid_invoice.total = Decimal("5280.00")
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.DISCOUNT_ERROR in report.exception_codes


class TestR10CreditIssue:
    def test_credit_clear(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.CREDIT_ISSUE not in report.exception_codes

    def test_credit_hold(self, validator, valid_invoice, sample_po, sample_grn):
        vendor_hold = Vendor(
            vendor_id="V-0001",
            vendor_name="Test Vendor",
            currency=Currency.USD,
            credit_status=CreditStatus.HOLD,
        )
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, vendor_hold)
        assert ExceptionCode.CREDIT_ISSUE in report.exception_codes
        exc = next(e for e in report.exceptions if e.exception_code == ExceptionCode.CREDIT_ISSUE)
        assert exc.severity == ExceptionSeverity.HIGH


class TestMultipleExceptions:
    def test_multiple_simultaneous_exceptions(self, validator, valid_invoice, sample_po, sample_grn):
        vendor_hold = Vendor(
            vendor_id="V-0001",
            vendor_name="Test Vendor",
            currency=Currency.EUR,
            credit_status=CreditStatus.HOLD,
        )
        valid_invoice.currency = Currency.USD
        valid_invoice.vendor_id = "V-9999"
        valid_invoice.total = Decimal("9999.00")

        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, vendor_hold)

        assert ExceptionCode.VENDOR_MISMATCH in report.exception_codes
        assert ExceptionCode.CURRENCY_MISMATCH in report.exception_codes
        assert ExceptionCode.AMOUNT_MISMATCH in report.exception_codes
        assert ExceptionCode.CREDIT_ISSUE in report.exception_codes
        assert len(report.exceptions) >= 4


class TestNoExceptions:
    def test_no_exceptions_clean_invoice(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert not report.has_exceptions
        assert report.validation_status == ValidationStatus.CLEAN


class TestMissingOptionalFields:
    def test_invoice_without_po_number(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.po_number = None
        report = validator.validate_invoice(valid_invoice, None, sample_grn, sample_vendor)
        assert ExceptionCode.PO_MISMATCH in report.exception_codes

    def test_invoice_without_grn(self, validator, valid_invoice, sample_po, sample_vendor):
        report = validator.validate_invoice(valid_invoice, sample_po, None, sample_vendor)
        assert ExceptionCode.GRN_MISMATCH not in report.exception_codes


class TestInvalidReferences:
    def test_invoice_line_with_invalid_po_line_id(self, validator, valid_invoice, sample_po, sample_grn, sample_vendor):
        valid_invoice.line_items[0].po_line_id = "L-INVALID"
        report = validator.validate_invoice(valid_invoice, sample_po, sample_grn, sample_vendor)
        assert ExceptionCode.LINE_ITEM_MISMATCH not in report.exception_codes