from apx.data.schemas import ExceptionCode, ExceptionSeverity, APException


EXCEPTION_SEVERITY_MAP: dict[ExceptionCode, ExceptionSeverity] = {
    ExceptionCode.VENDOR_MISMATCH: ExceptionSeverity.HIGH,
    ExceptionCode.PO_MISMATCH: ExceptionSeverity.HIGH,
    ExceptionCode.AMOUNT_MISMATCH: ExceptionSeverity.MEDIUM,
    ExceptionCode.GRN_MISMATCH: ExceptionSeverity.MEDIUM,
    ExceptionCode.DUPLICATE_INVOICE: ExceptionSeverity.HIGH,
    ExceptionCode.TAX_ERROR: ExceptionSeverity.MEDIUM,
    ExceptionCode.CURRENCY_MISMATCH: ExceptionSeverity.HIGH,
    ExceptionCode.LINE_ITEM_MISMATCH: ExceptionSeverity.MEDIUM,
    ExceptionCode.DISCOUNT_ERROR: ExceptionSeverity.LOW,
    ExceptionCode.CREDIT_ISSUE: ExceptionSeverity.HIGH,
}


EXCEPTION_MESSAGES: dict[ExceptionCode, str] = {
    ExceptionCode.VENDOR_MISMATCH: "Invoice vendor does not match PO vendor",
    ExceptionCode.PO_MISMATCH: "Referenced PO is missing, invalid, or belongs to different vendor",
    ExceptionCode.AMOUNT_MISMATCH: "Invoice amount exceeds PO tolerance",
    ExceptionCode.GRN_MISMATCH: "Invoiced quantity exceeds received quantity",
    ExceptionCode.DUPLICATE_INVOICE: "Duplicate invoice detected",
    ExceptionCode.TAX_ERROR: "Tax calculation does not match expected value",
    ExceptionCode.CURRENCY_MISMATCH: "Currency mismatch between invoice, PO, and vendor",
    ExceptionCode.LINE_ITEM_MISMATCH: "Invoice line items do not match PO line items",
    ExceptionCode.DISCOUNT_ERROR: "Discount value is incorrect or exceeds allowed amount",
    ExceptionCode.CREDIT_ISSUE: "Vendor credit status prevents processing",
}


def create_exception(code: ExceptionCode, details: dict | None = None) -> APException:
    return APException(
        exception_code=code,
        severity=EXCEPTION_SEVERITY_MAP[code],
        message=EXCEPTION_MESSAGES[code],
        details=details or {}
    )


ALL_EXCEPTION_CODES: list[ExceptionCode] = list(ExceptionCode)