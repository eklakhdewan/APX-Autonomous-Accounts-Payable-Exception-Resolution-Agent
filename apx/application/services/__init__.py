from __future__ import annotations
from typing import Any

from apx.application.services.invoice_service import InvoiceService
from apx.application.services.case_service import CaseService
from apx.application.services.approval_service import ApprovalService
from apx.application.services.audit_service import AuditService
from apx.application.services.metrics_service import MetricsService

# Service getter functions (lazy initialization)
_invoice_service: Any = None
_case_service: Any = None
_approval_service: Any = None
_audit_service: Any = None
_metrics_service: Any = None


def get_invoice_service() -> InvoiceService:
    global _invoice_service
    if _invoice_service is None:
        raise RuntimeError("InvoiceService not initialized")
    return _invoice_service


def get_case_service() -> CaseService:
    global _case_service
    if _case_service is None:
        raise RuntimeError("CaseService not initialized")
    return _case_service


def get_approval_service() -> ApprovalService:
    global _approval_service
    if _approval_service is None:
        raise RuntimeError("ApprovalService not initialized")
    return _approval_service


def get_audit_service() -> AuditService:
    global _audit_service
    if _audit_service is None:
        raise RuntimeError("AuditService not initialized")
    return _audit_service


def get_metrics_service() -> MetricsService:
    global _metrics_service
    if _metrics_service is None:
        raise RuntimeError("MetricsService not initialized")
    return _metrics_service


__all__ = [
    "InvoiceService",
    "CaseService",
    "ApprovalService",
    "AuditService",
    "MetricsService",
    "get_invoice_service",
    "get_case_service",
    "get_approval_service",
    "get_audit_service",
    "get_metrics_service",
]