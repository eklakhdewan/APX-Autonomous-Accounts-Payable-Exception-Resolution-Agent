from __future__ import annotations

from typing import Any, Optional

from apx.agent.llm.base import LLMProvider, InvestigationFindings
from apx.agent.models import InvestigationContext, InvestigationResult, InvestigationStep
from apx.agent.state_machine import AgentState, TerminalOutcome, transition, TransitionError
from apx.data.schemas import ExceptionReport
from apx.evidence.schemas import EvidenceSet, ValidatedEvidence, ValidityStatus


class BoundedInvestigationAgent:
    """
    Bounded investigation agent for AP exception resolution.
    
    Implements a deterministic state machine with bounded investigation budget.
    The agent consumes Phase 1 ExceptionReport and Phase 2 EvidenceSet to
    produce a structured InvestigationResult.
    """
    
    def __init__(
        self,
        context: InvestigationContext,
    ):
        self.context = context
        self.state = AgentState.DETECTED
        self.budget_limit = context.budget_limit
        self.budget_used = 0
        self.steps: list[InvestigationStep] = []
        self.evidence_ids_used: list[str] = []
        self.findings_log: list[str] = []
        self.termination_reason = ""
        self._llm: LLMProvider = context.llm_provider
    
    def run(self) -> InvestigationResult:
        """
        Run the complete investigation workflow.
        
        Returns:
            InvestigationResult with final state and findings
        """
        try:
            # Phase 1: Context Retrieval
            self._transition_to(AgentState.CONTEXT_RETRIEVED)
            self._log_step("context_retrieval", "Retrieved evidence context from Phase 2")
            
            # Phase 2: Investigation
            self._transition_to(AgentState.INVESTIGATING)
            
            while self.state == AgentState.INVESTIGATING:
                if self.budget_used >= self.budget_limit:
                    self.termination_reason = "Budget exhausted"
                    break
                
                self._investigation_step()
                
                # Check if we should move to decision ready
                if self._should_make_decision():
                    self._transition_to(AgentState.DECISION_READY)
            
            # Phase 3: Decision
            if self.state == AgentState.DECISION_READY:
                self._make_final_decision()
            
        except Exception as e:
            self.termination_reason = f"Investigation error: {str(e)}"
            if self.state != AgentState.DECISION_READY:
                self._transition_to(TerminalOutcome.ESCALATE)
        
        return self._build_result()
    
    def _transition_to(self, target: AgentState | TerminalOutcome) -> None:
        """Perform a state transition, recording the step."""
        old_state = self.state
        new_state = transition(self.state, target)
        
        step = InvestigationStep(
            step_number=len(self.steps) + 1,
            action=f"state_transition_{old_state.value}_to_{new_state.value}",
            state_before=old_state,
            state_after=new_state if isinstance(new_state, AgentState) else AgentState.DECISION_READY,
            evidence_ids=[],
            finding=f"State transition: {old_state.value} -> {new_state.value}",
        )
        self.steps.append(step)
        self.budget_used += 1
        
        if isinstance(new_state, AgentState):
            self.state = new_state
        else:
            # Terminal outcome
            self.state = AgentState.DECISION_READY  # Will be overridden in _build_result
    
    def _log_step(self, action: str, finding: str, evidence_ids: list[str] | None = None) -> None:
        """Record an investigation step."""
        step = InvestigationStep(
            step_number=len(self.steps) + 1,
            action=action,
            state_before=self.state,
            state_after=self.state,
            evidence_ids=evidence_ids or [],
            finding=finding,
            budget_consumed=1,
        )
        self.steps.append(step)
        self.budget_used += 1
        self.findings_log.append(finding)
        if evidence_ids:
            self.evidence_ids_used.extend(evidence_ids)
    
    def _investigation_step(self) -> None:
        """Perform a single investigation step using the LLM."""
        if self.budget_used >= self.budget_limit:
            return
        
        # Prepare evidence summaries for LLM
        evidence_summaries = self._prepare_evidence_summaries()
        exception_report_str = self._format_exception_report()
        
        try:
            findings = self._llm.investigate(
                exception_report=exception_report_str,
                evidence_summaries=evidence_summaries,
                current_state=self.state.value,
                budget_remaining=self.budget_limit - self.budget_used,
            )
            
            # Validate evidence IDs exist in EvidenceSet
            valid_evidence_ids = self._validate_evidence_ids(findings.evidence_ids)
            
            self.evidence_ids_used.extend(valid_evidence_ids)
            self.findings_log.append(findings.findings)
            
            # Check if we should move to decision
            if findings.proposed_outcome in ["RESOLVE", "REQUEST_INFO", "ESCALATE"]:
                if findings.confidence >= 0.7 or self.budget_used >= self.budget_limit - 1:
                    self._transition_to(AgentState.DECISION_READY)
                    self.termination_reason = f"LLM proposed {findings.proposed_outcome} with confidence {findings.confidence}"
            
            self._log_step(
                action="llm_investigation",
                finding=findings.findings,
                evidence_ids=valid_evidence_ids,
            )
            
        except Exception as e:
            self._log_step(
                action="llm_investigation",
                finding=f"LLM error: {str(e)}",
            )
    
    def _prepare_evidence_summaries(self) -> list[dict]:
        """Prepare evidence summaries for LLM consumption."""
        summaries = []
        for ev in self.context.evidence_set.validated_evidence:
            summaries.append({
                "evidence_id": ev.evidence.evidence_id,
                "evidence_type": ev.evidence.evidence_type.value,
                "scope": ev.evidence.scope,
                "scope_target": ev.evidence.scope_target,
                "vendor_id": ev.evidence.vendor_id,
                "relevance_score": ev.relevance_score,
                "reranker_score": ev.reranker_score,
                "validity_status": ev.validity_status.value,
                "validity_reasons": ev.validity_reasons,
                "source_authority": ev.source_authority.value,
                "content_preview": ev.content[:200] + "..." if len(ev.content) > 200 else ev.content,
            })
        return summaries
    
    def _format_exception_report(self) -> str:
        """Format exception report for LLM."""
        lines = [
            f"Invoice ID: {self.context.exception_report.invoice_id}",
            f"Vendor ID: {self.context.exception_report.vendor_id}",
            "Exceptions:",
        ]
        for exc in self.context.exception_report.exceptions:
            lines.append(f"  - {exc.exception_code.value}: {exc.message}")
        return "\n".join(lines)
    
    def _validate_evidence_ids(self, evidence_ids: list[str]) -> list[str]:
        """Validate that evidence IDs exist in the EvidenceSet."""
        valid_ids = set()
        for ev in self.context.evidence_set.validated_evidence:
            valid_ids.add(ev.evidence.evidence_id)
        
        validated = []
        for eid in evidence_ids:
            if eid in valid_ids:
                validated.append(eid)
            else:
                # Log warning but don't fail - just skip invalid IDs
                pass
        return validated
    
    def _should_make_decision(self) -> bool:
        """Determine if we have enough information to make a decision."""
        if self.budget_used >= self.budget_limit:
            return True
        if len(self.findings_log) >= 3:
            return True
        # Check if we have high-confidence evidence
        valid_evidence = [e for e in self.context.evidence_set.validated_evidence 
                         if e.validity_status == ValidityStatus.VALID]
        if valid_evidence:
            return True
        return False
    
    def _make_final_decision(self) -> None:
        """Make the final decision based on investigation findings."""
        # Get the last LLM findings if available
        last_findings = self.findings_log[-1] if self.findings_log else ""
        
        # Determine outcome based on findings
        if "RESOLVE" in str(self.findings_log).upper():
            pass  # Will be handled in _build_result
        elif "REQUEST_INFO" in str(self.findings_log).upper():
            pass
        else:
            pass  # Default to ESCALATE
    
    def _build_result(self) -> InvestigationResult:
        """Build the final investigation result."""
        # Determine outcome from final state
        outcome = None
        if self.state == AgentState.DECISION_READY:
            # Determine from findings
            findings_text = " ".join(self.findings_log).upper()
            if "RESOLVE" in findings_text:
                outcome = TerminalOutcome.RESOLVE
            elif "REQUEST_INFO" in findings_text:
                outcome = TerminalOutcome.REQUEST_INFO
            else:
                outcome = TerminalOutcome.ESCALATE
        
        # If no outcome determined, default based on budget
        if outcome is None:
            if self.budget_used >= self.budget_limit:
                outcome = TerminalOutcome.ESCALATE
                self.termination_reason = self.termination_reason or "Budget exhausted"
            else:
                outcome = TerminalOutcome.ESCALATE
        
        # Deduplicate evidence IDs
        unique_evidence_ids = list(dict.fromkeys(self.evidence_ids_used))
        
        return InvestigationResult(
            case_id=self.context.exception_report.invoice_id,
            invoice_id=self.context.exception_report.invoice_id,
            vendor_id=self.context.exception_report.vendor_id,
            exception_codes=[e.value for e in self.context.exception_report.exception_codes],
            final_state=self.state if isinstance(self.state, AgentState) else AgentState.DECISION_READY,
            outcome=outcome,
            evidence_ids=unique_evidence_ids,
            findings=" | ".join(self.findings_log),
            steps=self.steps,
            budget_limit=self.budget_limit,
            budget_used=self.budget_used,
            termination_reason=self.termination_reason or "Investigation completed",
        )


def run_investigation(
    exception_report: ExceptionReport,
    evidence_set: EvidenceSet,
    budget_limit: int = 10,
    llm_provider: Optional[Any] = None,
) -> InvestigationResult:
    """
    Convenience function to run a complete investigation.
    
    Args:
        exception_report: Phase 1 exception report
        evidence_set: Phase 2 evidence set
        budget_limit: Maximum investigation steps (default from config)
        llm_provider: LLM provider (uses mock if None)
        
    Returns:
        InvestigationResult with findings and outcome
    """
    from apx.agent.llm.mock import MockLLMProvider
    from apx.config.settings import get_settings
    
    if llm_provider is None:
        llm_provider = MockLLMProvider()
    
    settings = get_settings()
    agent_settings = settings.get_agent_settings()
    budget = budget_limit or agent_settings.max_investigation_steps
    
    context = InvestigationContext(
        exception_report=exception_report,
        evidence_set=evidence_set,
        budget_limit=budget,
        llm_provider=llm_provider,
    )
    
    agent = BoundedInvestigationAgent(context)
    return agent.run()