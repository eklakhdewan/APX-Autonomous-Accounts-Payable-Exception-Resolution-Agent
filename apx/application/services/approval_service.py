from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

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

        if approval.status != "PENDING":
            raise ValueError(f"Approval is not pending: {approval.status}")

        # Record approval
        self.approval_repo.add_approval(UUID(approval.approval_id), approver_id, True, notes)

        # Update approval status
        self.approval_repo.update_status(
            UUID(approval.approval_id),
            "APPROVED",
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

        return {
            "approval_id": str(approval.approval_id),
            "case_id": case_id,
            "status": "APPROVED",
            "message": "Approval granted",
        }

    def reject_case(self, case_id: str, approver_id: str, notes: str) -> dict[str, Any]:
        """Reject a case."""
        approval = self.approval_repo.get_by_case(UUID(case_id))
        if not approval:
            raise ValueError(f"No approval found for case {case_id}")

        if approval.status != "PENDING":
            raise ValueError(f"Approval is not pending: {approval.status}")

        # Record rejection
        self.approval_repo.add_approval(UUID(approval.approval_id), approver_id, False, notes)

        # Update approval status
        self.approval_repo.update_status(
            UUID(approval.approval_id),
            "REJECTED",
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

        return {
            "approval_id": str(approval.approval_id),
            "case_id": case_id,
            "status": "REJECTED",
            "message": "Approval rejected",
        }

    def get_approval(self, case_id: str) -> Optional[dict[str, Any]]:
        """Get approval for a case."""
        approval = self.approval_repo.get_by_case(UUID(case_id))
        if not approval:
            return None
        return {
            "approval_id": str(approval.approval_id),
            "case_id": str(approval.action_plan_id) if approval.action_plan_id else case_id,
            "action_type": approval.action_type,
            "risk_level": approval.risk_level,
            "status": approval.status,
            "required_approvers": approval.required_approvers,
            "approvals": approval.approvals,
            "requested_by": approval.requested_by,
            "requested_at": approval.requested_at,
            "resolved_by": approval.resolved_by,
            "resolved_at": approval.resolved_at,
            "notes": approval.notes,
        }