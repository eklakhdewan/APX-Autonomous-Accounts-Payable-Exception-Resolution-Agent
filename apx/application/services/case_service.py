from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from apx.persistence import (
    CaseRepository,
    AuditRepository,
)


class CaseService:
    """Service for case operations."""

    def __init__(
        self,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
    ):
        self.case_repo = case_repo
        self.audit_repo = audit_repo

    def get_case(self, case_id: str) -> Optional[dict[str, Any]]:
        """Get case by ID."""
        return self.case_repo.get(UUID(case_id))

    def get_case_by_invoice(self, invoice_id: str) -> Optional[dict[str, Any]]:
        """Get case by invoice ID."""
        return self.case_repo.get_by_invoice(invoice_id)

    def list_cases(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List cases with optional filtering."""
        return self.case_repo.list_all(status=status, limit=limit, offset=offset)