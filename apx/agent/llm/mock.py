from __future__ import annotations

from typing import Any

from apx.agent.llm.base import InvestigationFindings, LLMProvider


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock LLM provider for testing.
    
    Returns deterministic findings based on the exception type and available evidence.
    Does not require network access or API keys.
    """
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        self._call_count = 0
    
    def get_provider_name(self) -> str:
        return "mock"
    
    def investigate(
        self,
        exception_report: str,
        evidence_summaries: list[dict],
        current_state: str,
        budget_remaining: int,
    ) -> InvestigationFindings:
        """Generate deterministic findings based on input."""
        self._call_count += 1
        
        # Parse exception type from report
        exception_type = "UNKNOWN"
        if "AMOUNT_MISMATCH" in exception_report:
            exception_type = "AMOUNT_MISMATCH"
        elif "GRN_MISMATCH" in exception_report:
            exception_type = "GRN_MISMATCH"
        elif "VENDOR_MISMATCH" in exception_report:
            exception_type = "VENDOR_MISMATCH"
        elif "TAX_ERROR" in exception_report:
            exception_type = "TAX_ERROR"
        elif "CREDIT_ISSUE" in exception_report:
            exception_type = "CREDIT_ISSUE"
        elif "PO_MISMATCH" in exception_report:
            exception_type = "PO_MISMATCH"
        elif "CURRENCY_MISMATCH" in exception_report:
            exception_type = "CURRENCY_MISMATCH"
        elif "LINE_ITEM_MISMATCH" in exception_report:
            exception_type = "LINE_ITEM_MISMATCH"
        elif "DISCOUNT_ERROR" in exception_report:
            exception_type = "DISCOUNT_ERROR"
        elif "DUPLICATE_INVOICE" in exception_report:
            exception_type = "DUPLICATE_INVOICE"
        
        # Determine outcome based on available evidence
        valid_evidence = [e for e in evidence_summaries if e.get("validity_status") == "valid"]
        highly_relevant = [e for e in valid_evidence if e.get("relevance_score", 0) > 0.3]
        
        if highly_relevant and self._call_count >= 1:
            # After 1+ steps with relevant evidence, propose resolution
            if exception_type in ["AMOUNT_MISMATCH", "GRN_MISMATCH", "TAX_ERROR", "DISCOUNT_ERROR"]:
                return InvestigationFindings(
                    findings=f"Found {len(highly_relevant)} highly relevant valid evidence items supporting {exception_type} resolution.",
                    evidence_ids=[e["evidence_id"] for e in highly_relevant[:3]],
                    proposed_outcome="RESOLVE",
                    confidence=0.85,
                    information_needed=[],
                )
            elif exception_type in ["VENDOR_MISMATCH", "CREDIT_ISSUE", "PO_MISMATCH"]:
                return InvestigationFindings(
                    findings=f"Found {len(highly_relevant)} highly relevant valid evidence items for {exception_type}. Requires manual review.",
                    evidence_ids=[e["evidence_id"] for e in highly_relevant[:3]],
                    proposed_outcome="REQUEST_INFO",
                    confidence=0.75,
                    information_needed=["Vendor confirmation", "Updated documentation"],
                )
        
        if self._call_count >= 3:
            # Budget exhausted or enough investigation done
            return InvestigationFindings(
                findings=f"Investigated {exception_type} with {len(valid_evidence)} valid evidence items. Insufficient evidence for resolution.",
                evidence_ids=[e["evidence_id"] for e in valid_evidence[:3]],
                proposed_outcome="ESCALATE",
                confidence=0.6,
                information_needed=["Additional documentation", "Vendor response"],
            )
        
        # First step - need more information
        return InvestigationFindings(
            findings=f"Initial investigation of {exception_type}. Found {len(valid_evidence)} valid evidence items. Need to examine specific evidence.",
            evidence_ids=[e["evidence_id"] for e in valid_evidence[:2]],
            proposed_outcome="ESCALATE",
            confidence=0.4,
            information_needed=["Detailed evidence review", "Vendor communication"],
        )
    
    def get_call_count(self) -> int:
        return self._call_count