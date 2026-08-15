from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from apx.action.models import (
    ActionPlan, ActionResult, ActionStatus, ActionExecutorConfig, DeadLetterEntry
)
from apx.guardrail.engine import ActionGuardrail
from apx.risk.engine import CompoundRiskEngine
from apx.agent.controller import run_investigation
from apx.agent.models import InvestigationResult, InvestigationContext
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.schemas import EvidenceSet, ValidatedEvidence, ValidityStatus
from apx.guardrail.engine import ActionGuardrail
from apx.risk.engine import CompoundRiskEngine


class ActionExecutor:
    """
    Executes approved actions through registered adapters.
    Uses mock/dry-run adapters by default.
    Supports compensation/rollback and dead letter queue for failed actions.
    """
    
    def __init__(
        self,
        config: ActionExecutorConfig | None = None,
        risk_engine: CompoundRiskEngine | None = None,
        guardrail: ActionGuardrail | None = None,
    ):
        self.config = config or ActionExecutorConfig()
        self.risk_engine = risk_engine or CompoundRiskEngine()
        self.guardrail = guardrail or ActionGuardrail()
        self._adapters: dict[str, Any] = {}
        self._compensation_adapters: dict[str, Any] = {}
        self._dead_letter_queue: list[DeadLetterEntry] = []
        self._register_default_adapters()
        self._register_default_compensation_adapters()
    
    def _register_default_adapters(self) -> None:
        """Register default mock adapters for each action type."""
        from apx.action.models import ActionType
        
        self._adapters = {
            "AUTO_RESOLVE": self._adapter_auto_resolve,
            "REQUEST_INFORMATION": self._adapter_request_information,
            "ESCALATE_TO_HUMAN": self._adapter_escalate_to_human,
            "ADJUST_PAYMENT": self._adapter_adjust_payment,
            "VOID_INVOICE": self._adapter_void_invoice,
            "CONTACT_VENDOR": self._adapter_contact_vendor,
            "UPDATE_RECORDS": self._adapter_update_records,
            "MANUAL_REVIEW": self._adapter_manual_review,
        }
    
    def _register_default_compensation_adapters(self) -> None:
        """Register default compensation/rollback adapters for each action type."""
        from apx.action.models import ActionType
        
        self._compensation_adapters = {
            "AUTO_RESOLVE": self._compensate_auto_resolve,
            "REQUEST_INFORMATION": self._compensate_request_information,
            "ESCALATE_TO_HUMAN": self._compensate_escalate_to_human,
            "ADJUST_PAYMENT": self._compensate_adjust_payment,
            "VOID_INVOICE": self._compensate_void_invoice,
            "CONTACT_VENDOR": self._compensate_contact_vendor,
            "UPDATE_RECORDS": self._compensate_update_records,
            "MANUAL_REVIEW": self._compensate_manual_review,
        }
    
    def register_adapter(self, action_type: str, adapter: Any) -> None:
        """Register a custom adapter for an action type."""
        self._adapters[action_type.upper()] = adapter
    
    def register_compensation_adapter(self, action_type: str, adapter: Any) -> None:
        """Register a custom compensation adapter for an action type."""
        self._compensation_adapters[action_type.upper()] = adapter
    
    def get_dead_letter_queue(self) -> list[DeadLetterEntry]:
        """Get the dead letter queue entries."""
        return self._dead_letter_queue
    
    def clear_dead_letter_queue(self) -> None:
        """Clear the dead letter queue."""
        self._dead_letter_queue.clear()
    
    def execute(
        self,
        action_plan: Any,  # ActionPlan
    ) -> Any:  # ActionResult
        """
        Execute an approved action plan.
        
        Returns ActionResult with execution details.
        On failure after retries, attempts compensation and adds to dead letter queue.
        """
        from apx.action.models import ActionStatus
        
        # Verify action plan is approved
        if action_plan.approval_status not in ["NOT_REQUIRED", "APPROVED"]:
            return ActionResult(
                action_id=action_plan.action_id,
                success=False,
                error_message=f"Action not approved: {action_plan.approval_status}",
                dry_run=self.config.dry_run,
            )
        
        # Check guardrail decision
        if action_plan.guardrail_decision and action_plan.guardrail_decision.decision == "BLOCK":
            return ActionResult(
                action_id=action_plan.action_id,
                success=False,
                error_message="Action blocked by guardrail",
                dry_run=self.config.dry_run,
            )
        
        # Update status to executing
        action_plan.status = ActionStatus.EXECUTING
        action_plan.updated_at = datetime.utcnow()
        
        try:
            # Get adapter
            adapter = self._adapters.get(action_plan.action_type.value)
            if not adapter:
                raise ValueError(f"No adapter registered for action type: {action_plan.action_type}")
            
            # Execute with retries
            last_error = None
            for attempt in range(self.config.max_retries):
                action_plan.retry_count = attempt
                try:
                    result = adapter(action_plan)
                    
                    action_plan.status = ActionStatus.EXECUTED
                    action_plan.executed_at = datetime.utcnow()
                    action_plan.execution_result = result
                    action_plan.updated_at = datetime.utcnow()
                    
                    return ActionResult(
                        action_id=action_plan.action_id,
                        success=True,
                        result_data=result,
                        executed_at=datetime.utcnow(),
                        executed_by="system",
                        idempotency_key=action_plan.idempotency_key,
                        dry_run=self.config.dry_run,
                    )
                except Exception as e:
                    last_error = e
                    if attempt < self.config.max_retries - 1:
                        import time
                        time.sleep(self.config.retry_delay_seconds)
            
            # All retries failed - attempt compensation
            compensation_result = None
            if self.config.enable_compensation:
                compensation_result = self._attempt_compensation(action_plan, last_error)
            
            # Add to dead letter queue
            if self.config.enable_dead_letter_queue:
                self._add_to_dead_letter_queue(action_plan, last_error, compensation_result)
            
            action_plan.status = ActionStatus.FAILED
            action_plan.error_message = str(last_error)
            action_plan.updated_at = datetime.utcnow()
            
            return ActionResult(
                action_id=action_plan.action_id,
                success=False,
                error_message=str(last_error),
                dry_run=self.config.dry_run,
            )
            
        except Exception as e:
            # Unexpected error - attempt compensation
            compensation_result = None
            if self.config.enable_compensation:
                compensation_result = self._attempt_compensation(action_plan, e)
            
            # Add to dead letter queue
            if self.config.enable_dead_letter_queue:
                self._add_to_dead_letter_queue(action_plan, e, compensation_result)
            
            action_plan.status = ActionStatus.FAILED
            action_plan.error_message = str(e)
            action_plan.updated_at = datetime.utcnow()
            
            return ActionResult(
                action_id=action_plan.action_id,
                success=False,
                error_message=str(e),
                dry_run=self.config.dry_run,
            )
    
    def _attempt_compensation(self, action_plan: ActionPlan, error: Exception) -> dict[str, Any] | None:
        """Attempt to compensate/rollback a failed action."""
        compensation_adapter = self._compensation_adapters.get(action_plan.action_type.value)
        if not compensation_adapter:
            return {"status": "no_compensation_adapter", "action_type": action_plan.action_type.value}
        
        try:
            result = compensation_adapter(action_plan, error)
            return {"status": "success", "result": result}
        except Exception as comp_error:
            return {"status": "failed", "error": str(comp_error)}
    
    def _add_to_dead_letter_queue(
        self,
        action_plan: ActionPlan,
        error: Exception,
        compensation_result: dict[str, Any] | None
    ) -> None:
        """Add failed action to dead letter queue."""
        entry = DeadLetterEntry(
            action_id=action_plan.action_id,
            action_type=action_plan.action_type,
            target=action_plan.target,
            parameters=action_plan.parameters,
            error_message=str(error),
            retry_count=action_plan.retry_count,
            last_attempt_at=datetime.utcnow(),
            compensation_attempted=compensation_result is not None,
            compensation_result=compensation_result,
        )
        self._dead_letter_queue.append(entry)
    
    # Mock adapters
    def _adapter_auto_resolve(self, action_plan: Any) -> dict[str, Any]:
        """Auto-resolve the exception (mock)."""
        return {
            "action": "AUTO_RESOLVE",
            "invoice_id": action_plan.target,
            "resolution": "Exception auto-resolved based on evidence",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_request_information(self, action_plan: Any) -> dict[str, Any]:
        """Request additional information from vendor (mock)."""
        info_requested = action_plan.parameters.get("information_needed", ["Additional documentation"])
        return {
            "action": "REQUEST_INFORMATION",
            "vendor_id": action_plan.target,
            "information_requested": info_requested,
            "request_sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_escalate_to_human(self, action_plan: Any) -> dict[str, Any]:
        """Escalate to human reviewer (mock)."""
        return {
            "action": "ESCALATE_TO_HUMAN",
            "escalation_reason": action_plan.parameters.get("reason", "Requires human review"),
            "assigned_to": "review_queue",
            "priority": action_plan.parameters.get("priority", "NORMAL"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_adjust_payment(self, action_plan: Any) -> dict[str, Any]:
        """Adjust payment amount (mock)."""
        return {
            "action": "ADJUST_PAYMENT",
            "invoice_id": action_plan.target,
            "original_amount": action_plan.parameters.get("original_amount"),
            "adjusted_amount": action_plan.parameters.get("adjusted_amount"),
            "adjustment_reason": action_plan.parameters.get("reason", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_void_invoice(self, action_plan: Any) -> dict[str, Any]:
        """Void an invoice (mock)."""
        return {
            "action": "VOID_INVOICE",
            "invoice_id": action_plan.target,
            "void_reason": action_plan.parameters.get("reason", "Exception resolution"),
            "voided": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_contact_vendor(self, action_plan: Any) -> dict[str, Any]:
        """Contact vendor for clarification (mock)."""
        return {
            "action": "CONTACT_VENDOR",
            "vendor_id": action_plan.target,
            "contact_method": action_plan.parameters.get("method", "EMAIL"),
            "message": action_plan.parameters.get("message", "Please review exception"),
            "sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_update_records(self, action_plan: Any) -> dict[str, Any]:
        """Update internal records (mock)."""
        return {
            "action": "UPDATE_RECORDS",
            "record_type": action_plan.parameters.get("record_type", "INVOICE"),
            "record_id": action_plan.target,
            "updates": action_plan.parameters.get("updates", {}),
            "updated": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_manual_review(self, action_plan: Any) -> dict[str, Any]:
        """Flag for manual review (mock)."""
        return {
            "action": "MANUAL_REVIEW",
            "review_queue": action_plan.parameters.get("queue", "EXCEPTION_REVIEW"),
            "priority": action_plan.parameters.get("priority", "NORMAL"),
            "assigned_to": action_plan.parameters.get("assignee", "REVIEW_TEAM"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Compensation adapters (mock implementations)
    def _compensate_auto_resolve(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate auto-resolve by marking as unresolved."""
        return {
            "action": "COMPENSATE_AUTO_RESOLVE",
            "invoice_id": action_plan.target,
            "compensation": "Marked as unresolved - requires manual review",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_request_information(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate request information by marking as not sent."""
        return {
            "action": "COMPENSATE_REQUEST_INFORMATION",
            "vendor_id": action_plan.target,
            "compensation": "Information request marked as failed",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_escalate_to_human(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate escalate by removing from review queue."""
        return {
            "action": "COMPENSATE_ESCALATE_TO_HUMAN",
            "compensation": "Escalation removed from review queue",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_adjust_payment(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate payment adjustment by reverting."""
        return {
            "action": "COMPENSATE_ADJUST_PAYMENT",
            "invoice_id": action_plan.target,
            "compensation": "Payment adjustment reverted to original amount",
            "original_amount": action_plan.parameters.get("original_amount"),
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_void_invoice(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate void invoice by restoring."""
        return {
            "action": "COMPENSATE_VOID_INVOICE",
            "invoice_id": action_plan.target,
            "compensation": "Invoice voiding reversed - invoice restored",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_contact_vendor(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate contact vendor by marking as unsent."""
        return {
            "action": "COMPENSATE_CONTACT_VENDOR",
            "vendor_id": action_plan.target,
            "compensation": "Vendor contact marked as failed",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_update_records(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate record update by reverting."""
        return {
            "action": "COMPENSATE_UPDATE_RECORDS",
            "record_type": action_plan.parameters.get("record_type", "INVOICE"),
            "record_id": action_plan.target,
            "compensation": "Record updates reverted",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _compensate_manual_review(self, action_plan: Any, error: Exception) -> dict[str, Any]:
        """Compensate manual review by removing from queue."""
        return {
            "action": "COMPENSATE_MANUAL_REVIEW",
            "compensation": "Manual review removed from queue",
            "original_error": str(error),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    # Mock adapters
    def _adapter_auto_resolve(self, action_plan: Any) -> dict[str, Any]:
        """Auto-resolve the exception (mock)."""
        return {
            "action": "AUTO_RESOLVE",
            "invoice_id": action_plan.target,
            "resolution": "Exception auto-resolved based on evidence",
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_request_information(self, action_plan: Any) -> dict[str, Any]:
        """Request additional information from vendor (mock)."""
        info_requested = action_plan.parameters.get("information_needed", ["Additional documentation"])
        return {
            "action": "REQUEST_INFORMATION",
            "vendor_id": action_plan.target,
            "information_requested": info_requested,
            "request_sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_escalate_to_human(self, action_plan: Any) -> dict[str, Any]:
        """Escalate to human reviewer (mock)."""
        return {
            "action": "ESCALATE_TO_HUMAN",
            "escalation_reason": action_plan.parameters.get("reason", "Requires human review"),
            "assigned_to": "review_queue",
            "priority": action_plan.parameters.get("priority", "NORMAL"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_adjust_payment(self, action_plan: Any) -> dict[str, Any]:
        """Adjust payment amount (mock)."""
        return {
            "action": "ADJUST_PAYMENT",
            "invoice_id": action_plan.target,
            "original_amount": action_plan.parameters.get("original_amount"),
            "adjusted_amount": action_plan.parameters.get("adjusted_amount"),
            "adjustment_reason": action_plan.parameters.get("reason", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_void_invoice(self, action_plan: Any) -> dict[str, Any]:
        """Void an invoice (mock)."""
        return {
            "action": "VOID_INVOICE",
            "invoice_id": action_plan.target,
            "void_reason": action_plan.parameters.get("reason", "Exception resolution"),
            "voided": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_contact_vendor(self, action_plan: Any) -> dict[str, Any]:
        """Contact vendor for clarification (mock)."""
        return {
            "action": "CONTACT_VENDOR",
            "vendor_id": action_plan.target,
            "contact_method": action_plan.parameters.get("method", "EMAIL"),
            "message": action_plan.parameters.get("message", "Please review exception"),
            "sent": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_update_records(self, action_plan: Any) -> dict[str, Any]:
        """Update internal records (mock)."""
        return {
            "action": "UPDATE_RECORDS",
            "record_type": action_plan.parameters.get("record_type", "INVOICE"),
            "record_id": action_plan.target,
            "updates": action_plan.parameters.get("updates", {}),
            "updated": True,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _adapter_manual_review(self, action_plan: Any) -> dict[str, Any]:
        """Flag for manual review (mock)."""
        return {
            "action": "MANUAL_REVIEW",
            "review_queue": action_plan.parameters.get("queue", "EXCEPTION_REVIEW"),
            "priority": action_plan.parameters.get("priority", "NORMAL"),
            "assigned_to": action_plan.parameters.get("assignee", "REVIEW_TEAM"),
            "timestamp": datetime.utcnow().isoformat(),
        }