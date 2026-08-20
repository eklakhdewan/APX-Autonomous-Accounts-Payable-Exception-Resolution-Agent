from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from apx.persistence import AuditRepository


class AuditService:
    """Service for audit operations."""

    def __init__(self, audit_repo: AuditRepository):
        self.audit_repo = audit_repo

    def get_audit_events(
        self,
        case_id: str,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get audit events for a case."""
        return self.audit_repo.get_by_case(UUID(case_id), limit=limit, offset=offset)

    def get_audit_events_by_type(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get audit events by type."""
        return self.audit_repo.get_by_type(event_type, since=since, limit=limit, offset=offset)

    def list_all_audit_events(
        self,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List all audit events."""
        return self.audit_repo.list_all(limit=limit, offset=offset)