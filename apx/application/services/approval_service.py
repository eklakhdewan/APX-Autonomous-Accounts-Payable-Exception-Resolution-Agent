from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from apx.action.models import ApprovalStatus
from apx.persistence import (
    ApprovalRepository,
    CaseRepository,
    AuditRepository,
)


class ApprovalService:
    """Service for approval operations."""

    def __init__(
        self,
        approval_repo: ApprovalRepository,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
    ):
        self.approval_repo = approval_repo
        self.case_repo = case_repo
        self.audit_repo = audit_repo

    def approve_case(self, case_id: str, approver_id: str, notes: str = "") -> dict[str, Any]:
        """Approve a case."""
        # Get the approval for this case
        approval = self.approval_repo.get_by_case(UUID(case_id))
        if not approval:
            raise ValueError(f"No approval found for case {case_id}")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval.status}")

        # Record approval
        self.approval_repo.add_approval(UUID(approval.approval_id), approver_id, True, notes)

        # Update approval status
        self.approval_repo.update_status(
            UUID(approval.approval_id),
            ApprovalStatus.APPROVED,
            approver_id,
            notes,
        )

        # Update case status
        case = self.case_repo.get(UUID(case_id))
        if case and case["action_status"] == "PENDING":
            self.case_repo.update_status(UUID(case_id), "APPROVED", action_status="APPROVED")

        # Log audit event
        self.audit_repo.log(
            case_id=UUID(case_id),
            event_type="APPROVAL_GRANTED",
            phase="phase4",
            component="approval_service",
            payload={
                "approval_id": str(approval.approval_id),
                "approver_id": approver_id,
                "notes": notes,
            },
        )

        # Return updated approval
        return self.get_approval(case_id)

    def reject_case(self, case_id: str, approver_id: str, notes: str) -> dict[str, Any]:
        """Reject a case."""
        approval = self.approval_repo.get_by_case(UUID(case_id))
        if not approval:
            raise ValueError(f"No approval found for case {case_id}")

        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval is not pending: {approval.status}")

        # Record rejection
        self.approval_repo.add_approval(UUID(approval.approval_id), approver_id, False, notes)

        # Update approval status
        self.approval_repo.update_status(
            UUID(approval.approval_id),
            ApprovalStatus.REJECTED,
            approver_id,
            notes,
        )

        # Update case status
        self.case_repo.update_status(UUID(case_id), "REJECTED", action_status="REJECTED")

        # Log audit event
        self.audit_repo.log(
            case_id=UUID(case_id),
            event_type="APPROVAL_REJECTED",
            phase="phase4",
            component="approval_service",
            payload={
                "approval_id": str(approval.approval_id),
                "approver_id": approver_id,
                "notes": notes,
            },
        )

        # Return updated approval
        return self.get_approval(case_id)

    def get_approval(self, case_id: str) -> Optional[dict[str, Any]]:
        """Get approval for a case."""
        from apx.persistence.sqlite_repos import SQLiteApprovalRepository
        from uuid import UUID

        # Get the full ORM object to access approvals_json with full details
        approval_repo = SQLiteApprovalRepository()
        # We need to access the ORM directly to get full approvals_json
        from apx.persistence.database import session_scope
        from apx.persistence.models import ApprovalORM
        from sqlalchemy import select

        with session_scope() as session:
            stmt = select(ApprovalORM).where(ApprovalORM.case_id == UUID(case_id))
            orm = session.execute(stmt).scalar_one_or_none()
            if not orm:
                return None

            # Extract full approvals dict
            approvals_full = {}
            if orm.approvals_json:
                for k, v in orm.approvals_json.items():
                    if isinstance(v, dict):
                        approvals_full[k] = v
                    elif isinstance(v, bool):
                        approvals_full[k] = {"approved": v, "notes": "", "timestamp": ""}

            return {
                "approval_id": str(orm.approval_id),
                "case_id": str(orm.case_id),
                "action_type": orm.action_type,
                "risk_level": orm.risk_level,
                "status": orm.status,
                "required_approvers": orm.required_approvers,
                "approvals": approvals_full,
                "requested_by": orm.requested_by,
                "requested_at": orm.requested_at,
                "resolved_by": orm.resolved_by,
                "resolved_at": orm.resolved_at,
                "notes": orm.notes,
            }