from __future__ import annotations

import pytest
from apx.agent.llm.mock import MockLLMProvider
from apx.agent.llm.base import InvestigationFindings, LLMProvider
from apx.agent.models import InvestigationStep, InvestigationResult
from apx.agent.state_machine import AgentState, TerminalOutcome


class TestMockLLMProvider:
    """Test the deterministic mock LLM provider."""
    
    def test_mock_provider_name(self):
        provider = MockLLMProvider()
        assert provider.get_provider_name() == "mock"
    
    def test_mock_investigate_returns_structured_findings(self):
        provider = MockLLMProvider()
        
        findings = provider.investigate(
            exception_report="Test AMOUNT_MISMATCH",
            evidence_summaries=[{"evidence_id": "EV-001", "validity_status": "valid"}],
            current_state="INVESTIGATING",
            budget_remaining=5,
        )
        
        assert isinstance(findings, InvestigationFindings)
        assert findings.proposed_outcome in ["RESOLVE", "REQUEST_INFO", "ESCALATE"]
        assert 0.0 <= findings.confidence <= 1.0
        assert isinstance(findings.evidence_ids, list)
        assert isinstance(findings.information_needed, list)
        assert isinstance(findings.findings, str)
    
    def test_mock_deterministic(self):
        """Same seed should produce same results."""
        provider1 = MockLLMProvider(seed=42)
        provider2 = MockLLMProvider(seed=42)
        
        f1 = provider1.investigate("test", [], "INVESTIGATING", 5)
        f2 = provider2.investigate("test", [], "INVESTIGATING", 5)
        
        assert f1.proposed_outcome == f2.proposed_outcome
        assert f1.confidence == f2.confidence
    
    def test_call_count_increments(self):
        provider = MockLLMProvider()
        assert provider.get_call_count() == 0
        
        provider.investigate("test", [], "INVESTIGATING", 5)
        assert provider.get_call_count() == 1
        
        provider.investigate("test", [], "INVESTIGATING", 5)
        assert provider.get_call_count() == 2
    
    def test_invalid_provider_implementation(self):
        """Test that abstract base class cannot be instantiated."""
        with pytest.raises(TypeError):
            LLMProvider()


class TestInvestigationStep:
    """Test InvestigationStep model."""
    
    def test_step_creation(self):
        step = InvestigationStep(
            step_number=1,
            action="test_action",
            state_before="DETECTED",
            state_after="CONTEXT_RETRIEVED",
            evidence_ids=["EV-001"],
            finding="Test finding",
        )
        
        assert step.step_number == 1
        assert step.action == "test_action"
        assert step.state_before == "DETECTED"
        assert step.state_after == "CONTEXT_RETRIEVED"
        assert step.evidence_ids == ["EV-001"]
        assert step.finding == "Test finding"
        assert step.budget_consumed == 1
    
    def test_step_defaults(self):
        step = InvestigationStep(
            step_number=1,
            action="test",
            state_before="DETECTED",
            state_after="CONTEXT_RETRIEVED",
        )
        
        assert step.evidence_ids == []
        assert step.finding == ""
        assert step.budget_consumed == 1
        assert step.timestamp is not None


class TestInvestigationResult:
    """Test InvestigationResult model."""
    
    def test_result_creation(self):
        result = InvestigationResult(
            case_id="INV-001",
            invoice_id="INV-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            final_state="DECISION_READY",
            outcome="RESOLVE",
            evidence_ids=["EV-001"],
            findings="Test findings",
            steps=[],
            budget_limit=10,
            budget_used=3,
            termination_reason="Completed",
        )
        
        assert result.case_id == "INV-001"
        assert result.invoice_id == "INV-001"
        assert result.vendor_id == "V-0001"
        assert result.budget_limit == 10
        assert result.budget_used == 3
        assert result.budget_remaining == 7
        assert result.is_resolved
        assert not result.is_escalated
        assert not result.requests_info
    
    def test_result_properties(self):
        result = InvestigationResult(
            case_id="INV-001",
            invoice_id="INV-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            final_state="DECISION_READY",
            outcome="ESCALATE",
            evidence_ids=["EV-001"],
            findings="Test",
            steps=[],
            budget_limit=10,
            budget_used=10,
            termination_reason="Budget exhausted",
        )
        
        assert result.budget_remaining == 0
        assert result.is_escalated
        assert not result.is_resolved
        assert not result.requests_info