from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel


class InvestigationFindings(BaseModel):
    """Structured output from LLM investigation."""
    findings: str = ""
    evidence_ids: list[str] = []
    proposed_outcome: str = "ESCALATE"
    confidence: float = 0.0
    information_needed: list[str] = []


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def investigate(
        self,
        exception_report: str,
        evidence_summaries: list[dict],
        current_state: str,
        budget_remaining: int,
    ) -> InvestigationFindings:
        """
        Perform an investigation step.
        
        Args:
            exception_report: Description of the exception being investigated
            evidence_summaries: List of evidence summaries to consider
            current_state: Current agent state
            budget_remaining: Investigation steps remaining
            
        Returns:
            Structured investigation findings
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider identifier."""
        pass