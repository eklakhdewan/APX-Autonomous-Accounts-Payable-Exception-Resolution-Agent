from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from apx.agent.controller import run_investigation
from apx.agent.models import InvestigationContext, InvestigationResult
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.schemas import EvidenceSet, ValidatedEvidence
from apx.evidence.engine import HybridContextEngine
from apx.risk.engine import CompoundRiskEngine
from apx.risk.models import RiskAssessment
from apx.guardrail.engine import ActionGuardrail
from apx.guardrail.models import GuardrailDecisionResult, ActionType
from apx.action.models import ActionPlan, ActionType, ActionStatus, ApprovalStatus, ActionResult
from apx.action.executor import ActionExecutor, ActionExecutorConfig
from apx.approval.engine import ApprovalEngine
from apx.config.settings import get_settings


class Phase4Pipeline:
    """
    Complete Phase 4 pipeline: InvestigationResult → Risk Assessment → Guardrail → Action Plan → Execution
    """
    
    def __init__(
        self,
        risk_engine: CompoundRiskEngine | None = None,
        guardrail: Any | None = None,
        executor: Any | None = None,
        approval_engine: Any | None = None,
    ):
        self.settings = get_settings()
        self.risk_engine = risk_engine or CompoundRiskEngine()
        self.guardrail = guardrail or ActionGuardrail()
        self.executor = executor or ActionExecutor()
        self.approval_engine = approval_engine
    
    def process(
        self,
        investigation_result: Any,  # InvestigationResult
        exception_report: Any,  # ExceptionReport
        evidence_set: Any = None,  # EvidenceSet
        action_type: str | None = None,
        action_params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:  # ActionPlan
        """
        Process an investigation result through the full Phase 4 pipeline.
        
        Returns an ActionPlan ready for execution (or already executed if auto-approved).
        """
        # Step 1: Risk Assessment
        risk_assessment = self.risk_engine.assess(
            investigation_result=investigation_result,
            exception_report=exception_report,
            evidence_set=None,  # Could pass evidence set if available
        )
        
        # Step 2: Determine action type if not provided
        if action_type is None:
            action_type = self._determine_action_type(investigation_result, risk_assessment)
        
        # Step 3: Guardrail evaluation
        guardrail_result = self.guardrail.evaluate(
            action_type=action_type,
            risk_assessment=risk_assessment,
            investigation_result=investigation_result,
            exception_report=exception_report,
            action_params=action_params,
            idempotency_key=idempotency_key,
        )
        
        # Step 4: Create action plan
        action_plan = self._create_action_plan(
            exception_report=exception_report,
            investigation_result=investigation_result,
            risk_assessment=risk_assessment,
            guardrail_result=guardrail_result,
            action_type=action_type,
            action_params=action_params,
        )
        
        # Step 5: Handle approval if required
        if action_plan.approval_status == "PENDING":
            # In production, this would trigger human approval workflow
            # For now, we simulate based on configuration
            from apx.config.settings import get_settings
            settings = get_settings()
            agent_settings = settings.get_agent_settings()
            
            # In DEV mode with mock, auto-approve for testing
            if settings.retrieval.defaults.get("active_profile") == "DEV":
                action_plan.approval_status = "APPROVED"
                action_plan.approval_resolved_at = datetime.utcnow()
                action_plan.status = ActionStatus.APPROVED
        else:
            # No approval required - transition to APPROVED status for execution
            action_plan.status = ActionStatus.APPROVED
        
        return action_plan
    
    def execute_action(self, action_plan: Any) -> Any:  # ActionResult
        """Execute an approved action plan."""
        return self.executor.execute(action_plan)
    
    def run_full_pipeline(
        self,
        exception_report: Any,  # ExceptionReport
        evidence_set: Any = None,  # EvidenceSet
        budget_limit: int = 10,
        action_type: str | None = None,
        action_params: dict[str, Any] | None = None,
    ) -> tuple[Any, Any, Any]:  # (InvestigationResult, ActionPlan, ActionResult)
        """
        Run the complete Phase 1→2→3→4 pipeline.
        
        Returns: (InvestigationResult, ActionPlan, ActionResult)
        """
        # Phase 3: Investigation
        from apx.agent.controller import run_investigation
        investigation_result = run_investigation(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=10,
        )
        
        # Phase 4: Risk + Guardrail + Action
        action_plan = self.process(
            investigation_result=investigation_result,
            exception_report=exception_report,
            evidence_set=None,
            action_type=action_type,
            action_params=action_params,
        )
        
        # Execute if approved
        if action_plan.status in ["APPROVED", "EXECUTING"]:
            action_result = self.executor.execute(action_plan)
        else:
            action_result = None
        
        return investigation_result, action_plan, action_result
    
    def _determine_action_type(
        self,
        investigation_result: Any,
        risk_assessment: Any,
    ) -> str:
        """Determine appropriate action type based on investigation outcome and risk."""
        # Use investigation outcome as primary signal
        if investigation_result.outcome:
            outcome = investigation_result.outcome.value if hasattr(investigation_result.outcome, 'value') else str(investigation_result.outcome)
            if outcome == "RESOLVE":
                return "AUTO_RESOLVE"
            elif outcome == "REQUEST_INFO":
                return "REQUEST_INFORMATION"
            elif outcome == "ESCALATE":
                return "ESCALATE_TO_HUMAN"
        
        # Fall back to risk level
        risk_level = risk_assessment.risk_level.value if hasattr(risk_assessment.risk_level, 'value') else str(risk_assessment.risk_level)
        if risk_level in ["LOW", "MEDIUM"]:
            return "AUTO_RESOLVE"
        elif risk_level == "HIGH":
            return "ESCALATE_TO_HUMAN"
        else:
            return "ESCALATE_TO_HUMAN"
    
    def _create_action_plan(
        self,
        exception_report: Any,
        investigation_result: Any,
        risk_assessment: Any,
        guardrail_result: Any,
        action_type: str,
        action_params: dict[str, Any] | None = None,
    ) -> Any:  # ActionPlan
        from apx.action.models import ActionPlan, ActionType, ActionStatus, ApprovalStatus
        from uuid import uuid4
        from datetime import datetime
        
        action_id = str(uuid4())
        
        # Determine if approval is required
        approval_status = ApprovalStatus.NOT_REQUIRED
        if guardrail_result.requires_approval:
            approval_status = "PENDING"
        
        action_plan = ActionPlan(
            action_id=str(uuid4()),
            exception_id=exception_report.invoice_id,
            action_type=ActionType(action_type.upper()),
            target=exception_report.invoice_id,
            parameters=action_params or {},
            risk_assessment=risk_assessment,
            guardrail_decision=guardrail_result,
            approval_status=approval_status,
            idempotency_key=str(uuid4()),
            rate_limit_ok=True,
            evidence_ids=investigation_result.evidence_ids,
            investigation_result_ref=investigation_result.case_id if hasattr(investigation_result, 'case_id') else investigation_result.invoice_id,
            investigation_outcome=investigation_result.outcome.value if investigation_result.outcome else "UNKNOWN",
            status=ActionStatus.PENDING,
        )
        
        return action_plan