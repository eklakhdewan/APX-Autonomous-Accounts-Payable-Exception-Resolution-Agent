from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class CreditStatus(str, Enum):
    ACTIVE = "ACTIVE"
    HOLD = "HOLD"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"


class VendorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class POStatus(str, Enum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class GRNStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PARTIAL = "PARTIAL"
    RETURNED = "RETURNED"


class ValidationStatus(str, Enum):
    CLEAN = "CLEAN"
    EXCEPTIONS = "EXCEPTIONS"
    ERROR = "ERROR"


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"


class PurchaseOrderLine(BaseModel):
    line_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    @field_validator("quantity", "unit_price", "discount", "tax_rate", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price) - self.discount

    def line_tax(self) -> Decimal:
        return self.line_total() * self.tax_rate


class PurchaseOrder(BaseModel):
    po_id: str = Field(..., min_length=1)
    vendor_id: str = Field(..., min_length=1)
    po_number: str = Field(..., min_length=1)
    po_date: date
    currency: Currency
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(..., ge=0)
    line_items: list[PurchaseOrderLine] = Field(default_factory=list)
    status: POStatus = POStatus.OPEN

    @field_validator("subtotal", "tax", "total", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def _validate_totals(self):
        calc_subtotal = sum(line.line_total() for line in self.line_items)
        calc_tax = sum(line.line_tax() for line in self.line_items)
        calc_total = calc_subtotal + calc_tax
        if self.line_items:
            tolerance = Decimal("0.01")
            if abs(self.subtotal - calc_subtotal) > tolerance:
                raise ValueError(f"PO subtotal mismatch: declared {self.subtotal}, calculated {calc_subtotal}")
            if abs(self.tax - calc_tax) > tolerance:
                raise ValueError(f"PO tax mismatch: declared {self.tax}, calculated {calc_tax}")
            if abs(self.total - calc_total) > tolerance:
                raise ValueError(f"PO total mismatch: declared {self.total}, calculated {calc_total}")
        return self


class GoodsReceiptLine(BaseModel):
    line_id: str = Field(..., min_length=1)
    po_line_id: str = Field(..., min_length=1)
    quantity_received: Decimal = Field(..., ge=0)

    @field_validator("quantity_received", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class GoodsReceipt(BaseModel):
    grn_id: str = Field(..., min_length=1)
    po_id: str = Field(..., min_length=1)
    vendor_id: str = Field(..., min_length=1)
    receipt_date: date
    line_items: list[GoodsReceiptLine] = Field(default_factory=list)
    status: GRNStatus = GRNStatus.RECEIVED


class InvoiceLine(BaseModel):
    line_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    po_line_id: Optional[str] = None
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    @field_validator("quantity", "unit_price", "discount", "tax_rate", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    def line_total(self) -> Decimal:
        return (self.quantity * self.unit_price) - self.discount

    def line_tax(self) -> Decimal:
        return self.line_total() * self.tax_rate


class Invoice(BaseModel):
    invoice_id: str = Field(..., min_length=1)
    vendor_id: str = Field(..., min_length=1)
    invoice_number: str = Field(..., min_length=1)
    po_number: Optional[str] = None
    invoice_date: date
    due_date: date
    currency: Currency
    subtotal: Decimal = Field(..., ge=0)
    tax: Decimal = Field(default=Decimal("0"), ge=0)
    total: Decimal = Field(..., ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    line_items: list[InvoiceLine] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("subtotal", "tax", "total", "discount", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @model_validator(mode="after")
    def _validate_totals(self):
        calc_subtotal = sum(line.line_total() for line in self.line_items)
        calc_tax = sum(line.line_tax() for line in self.line_items)
        calc_total = calc_subtotal + calc_tax - self.discount
        if self.line_items:
            tolerance = Decimal("0.01")
            if abs(self.subtotal - calc_subtotal) > tolerance:
                raise ValueError(f"Invoice subtotal mismatch: declared {self.subtotal}, calculated {calc_subtotal}")
            if abs(self.tax - calc_tax) > tolerance:
                raise ValueError(f"Invoice tax mismatch: declared {self.tax}, calculated {calc_tax}")
            if abs(self.total - calc_total) > tolerance:
                raise ValueError(f"Invoice total mismatch: declared {self.total}, calculated {calc_total}")
        return self


class Vendor(BaseModel):
    vendor_id: str = Field(..., min_length=1)
    vendor_name: str = Field(..., min_length=1)
    tax_id: Optional[str] = None
    currency: Currency = Currency.USD
    payment_terms_days: int = Field(default=30, ge=0)
    credit_status: CreditStatus = CreditStatus.ACTIVE
    status: VendorStatus = VendorStatus.ACTIVE


class ExceptionSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExceptionCode(str, Enum):
    VENDOR_MISMATCH = "VENDOR_MISMATCH"
    PO_MISMATCH = "PO_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    GRN_MISMATCH = "GRN_MISMATCH"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    TAX_ERROR = "TAX_ERROR"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    LINE_ITEM_MISMATCH = "LINE_ITEM_MISMATCH"
    DISCOUNT_ERROR = "DISCOUNT_ERROR"
    CREDIT_ISSUE = "CREDIT_ISSUE"


class APException(BaseModel):
    exception_code: ExceptionCode
    severity: ExceptionSeverity
    message: str
    details: dict = Field(default_factory=dict)


class ExceptionReport(BaseModel):
    invoice_id: str
    vendor_id: str
    exceptions: list[APException] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.CLEAN

    @property
    def exception_codes(self) -> list[ExceptionCode]:
        return [e.exception_code for e in self.exceptions]

    @property
    def has_exceptions(self) -> bool:
        return len(self.exceptions) > 0

    def add_exception(self, code: ExceptionCode, severity: ExceptionSeverity, message: str, details: dict | None = None):
        self.exceptions.append(APException(
            exception_code=code,
            severity=severity,
            message=message,
            details=details or {}
        ))
        if self.validation_status == ValidationStatus.CLEAN:
            self.validation_status = ValidationStatus.EXCEPTIONS


class GroundTruth(BaseModel):
    invoice_id: str
    expected_exceptions: list[ExceptionCode] = Field(default_factory=list)
    expected_decision: Optional[str] = None
    injected_exceptions: dict = Field(default_factory=dict)