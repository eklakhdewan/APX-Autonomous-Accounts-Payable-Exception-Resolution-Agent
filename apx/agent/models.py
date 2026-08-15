from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from apx.agent.state_machine import AgentState, TerminalOutcome


class InvestigationStep(BaseModel):
    """Represents a single investigation step."""
    step_number: int = Field(..., ge=1)
    action: str
    state_before: AgentState
    state_after: AgentState | TerminalOutcome
    evidence_ids: list[str] = Field(default_factory=list)
    finding: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    budget_consumed: int = Field(default=1, ge=1)


class InvestigationResult(BaseModel):
    """Final result of an investigation."""
    case_id: str
    invoice_id: str
    vendor_id: str
    exception_codes: list[str]
    final_state: AgentState | TerminalOutcome
    outcome: TerminalOutcome | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    findings: str = ""
    steps: list[InvestigationStep] = Field(default_factory=list)
    budget_limit: int
    budget_used: int
    termination_reason: str = ""
    
    @property
    def budget_remaining(self) -> int:
        return max(0, self.budget_limit - self.budget_used)
    
    @property
    def is_resolved(self) -> bool:
        return self.outcome == TerminalOutcome.RESOLVE
    
    @property
    def is_escalated(self) -> bool:
        return self.outcome == TerminalOutcome.ESCALATE
    
    @property
    def requests_info(self) -> bool:
        return self.outcome == TerminalOutcome.REQUEST_INFO


class InvestigationContext(BaseModel):
    """Context passed to the agent for investigation."""
    exception_report: Any
    evidence_set: Any
    budget_limit: int
    llm_provider: Any