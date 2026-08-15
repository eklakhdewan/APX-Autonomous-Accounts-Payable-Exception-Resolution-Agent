from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ApprovalEngine:
    """
    Manages human approval workflow for actions requiring approval.
    """
    
    def __init__(self):
        self._pending_approvals: dict[str, Any] = {}
        self._approval_history: list[dict] = []
    
    def request_approval(
        self,
        action_plan_id: str,
        action_type: str,
        risk_level: str,
        required_approvers: list[str],
        requested_by: str = "system",
        notes: str = "",
    ) -> Any:
        """Create an approval request."""
        from apx.action.models import ApprovalRequest, ApprovalStatus
        from uuid import uuid4
        from datetime import datetime
        
        approval = ApprovalRequest(
            approval_id=str(uuid4()),
            action_plan_id=action_plan_id,
            action_type=action_type,
            risk_level=risk_level,
            requested_by="system",
            status=ApprovalStatus.PENDING,
            required_approvers=required_approvers,
        )
        
        self._pending_approvals[approval.approval_id] = approval
        return approval
    
    def approve(self, approval_id: str, approver_id: str, notes: str = "") -> bool:
        """Record an approval."""
        if approval_id not in self._pending_approvals:
            return False
        
        approval = self._pending_approvals[approval_id]
        approval.approvals[approver_id] = True
        approval.resolved_by = approver_id
        approval.resolution_notes = notes
        
        # Check if all required approvers have approved
        all_approved = all(
            approver in approval.approvals and approval.approvals[approver]
            for approver in approval.required_approvers
        )
        
        if all_approved:
            approval.status = "APPROVED"
            approval.resolved_at = datetime.utcnow()
            self._move_to_history(approval)
        
        return True
    
    def reject(self, approval_id: str, approver_id: str, notes: str = "") -> bool:
        """Record a rejection."""
        if approval_id not in self._pending_approvals:
            return False
        
        approval = self._pending_approvals[approval_id]
        approval.approvals[approver_id] = False
        approval.resolved_by = approver_id
        approval.resolution_notes = notes
        approval.status = "REJECTED"
        approval.resolved_at = datetime.utcnow()
        
        self._move_to_history(approval)
        return True
    
    def get_approval(self, approval_id: str) -> Any | None:
        return self._pending_approvals.get(approval_id)
    
    def get_pending_approvals(self) -> list:
        return [a for a in self._pending_approvals.values() if a.status == "PENDING"]
    
    def _move_to_history(self, approval: Any) -> None:
        self._approval_history.append({
            "approval_id": approval.approval_id,
            "action_plan_id": approval.action_plan_id,
            "status": approval.status,
            "resolved_at": datetime.utcnow().isoformat(),
        })
        if approval.approval_id in self._pending_approvals:
            del self._pending_approvals[approval.approval_id]