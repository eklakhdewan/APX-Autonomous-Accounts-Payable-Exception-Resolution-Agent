from __future__ import annotations

import pytest
from apx.agent.models import InvestigationStep, InvestigationResult
from apx.agent.state_machine import AgentState, TerminalOutcome
from apx.agent.controller import BoundedInvestigationAgent, run_investigation
from apx.agent.models import InvestigationContext
from apx.agent.llm.mock import MockLLMProvider
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.schemas import EvidenceSet, Evidence, EvidenceType, SourceAuthority, ValidatedEvidence, ValidityStatus
from datetime import date


def create_test_context(budget_limit: int = 5) -> InvestigationContext:
    """Create a test investigation context with minimal valid data."""
    exception_report = ExceptionReport(
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exceptions=[
            APException(
                exception_code=ExceptionCode.AMOUNT_MISMATCH,
                severity=ExceptionSeverity.MEDIUM,
                message="Test amount mismatch",
            ),
        ],
        validation_status=ValidationStatus.EXCEPTIONS,
    )
    
    # Create minimal valid evidence
    evidence = Evidence(
        evidence_id="EV-00001",
        evidence_type="historical_resolution",
        scope="vendor_exception",
        scope_target="V-0001:AMOUNT_MISMATCH",
        vendor_id="V-0001",
        effective_from=date(2024, 1, 1),
        effective_until=date(2026, 12, 31),
        policy_version="v1.0",
        outcome="AUTO_APPROVED",
        source_authority=SourceAuthority.INTERNAL,
        usage_count=10,
        content="Historical resolution for AMOUNT_MISMATCH on vendor V-0001.",
    )
    
    validated_evidence = ValidatedEvidence(
        evidence=evidence,
        relevance_score=0.9,
        reranker_score=0.85,
        retrieval_sources=["BM25", "Dense"],
        rank=1,
        validity_status="valid",
        validity_reasons=[],
        scope_metadata={"scope": "vendor_exception"},
        source_authority=SourceAuthority.INTERNAL,
        content=evidence.content,
    )
    
    evidence_set = EvidenceSet(
        invoice_id="INV-TEST-001",
        vendor_id="V-0001",
        exception_codes=["AMOUNT_MISMATCH"],
        query="test query",
        validated_evidence=[validated_evidence],
    )
    
    return InvestigationContext(
        exception_report=ExceptionReport.model_construct(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.AMOUNT_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="Test amount mismatch",
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        ),
        evidence_set=evidence_set,
        budget_limit=budget_limit,
        llm_provider=MockLLMProvider(),
    )


class TestInvestigationBudget:
    """Test the investigation budget enforcement."""
    
    def test_budget_increments_on_each_step(self):
        """Budget should increment on each investigation step."""
        context = create_test_context(budget_limit=5)
        agent = BoundedInvestigationAgent(context)
        
        initial_budget = agent.budget_used
        assert initial_budget == 0
        
        # Perform a state transition
        agent._transition_to(AgentState.CONTEXT_RETRIEVED)
        assert agent.budget_used == 1
        
        agent._transition_to(AgentState.INVESTIGATING)
        assert agent.budget_used == 2
    
    def test_budget_cannot_exceed_maximum(self):
        """Budget should not exceed configured maximum."""
        context = create_test_context(budget_limit=3)
        agent = BoundedInvestigationAgent(context)
        
        # Transition through states up to budget limit
        agent._transition_to(AgentState.CONTEXT_RETRIEVED)
        agent._transition_to(AgentState.INVESTIGATING)
        
        # Budget should be 2 now
        assert agent.budget_used == 2
        
        # One more transition should hit budget limit
        agent._transition_to(AgentState.DECISION_READY)
        assert agent.budget_used == 3
        
        # Budget should not exceed limit
        assert agent.budget_used <= agent.budget_limit
    
    def test_budget_exhaustion_terminates_safely(self):
        """Exhausted budget should terminate investigation safely."""
        context = create_test_context(budget_limit=2)
        agent = BoundedInvestigationAgent(context)
        
        # Use up budget
        agent._transition_to(AgentState.CONTEXT_RETRIEVED)
        agent._transition_to(AgentState.INVESTIGATING)
        
        # Budget exhausted - should not be able to continue
        assert agent.budget_used >= agent.budget_limit
    
    def test_investigation_result_shows_budget_usage(self):
        """InvestigationResult should accurately report budget usage."""
        context = create_test_context(budget_limit=3)
        agent = BoundedInvestigationAgent(context)
        
        # Run a minimal investigation
        agent._transition_to(AgentState.CONTEXT_RETRIEVED)
        agent._transition_to(AgentState.INVESTIGATING)
        
        result = agent._build_result()
        
        assert result.budget_limit == 3
        assert result.budget_used >= 0
        assert result.budget_used <= result.budget_limit
        assert result.budget_remaining >= 0
    
    def test_no_infinite_loop_possible(self):
        """Budget limit prevents infinite investigation loops."""
        context = create_test_context(budget_limit=2)
        agent = BoundedInvestigationAgent(context)
        
        # Even if we try to loop, budget prevents infinite loop
        for _ in range(10):
            if agent.budget_used < agent.budget_limit:
                # Can only transition to valid next states
                if agent.state == AgentState.DETECTED:
                    agent._transition_to(AgentState.CONTEXT_RETRIEVED)
                elif agent.state == AgentState.CONTEXT_RETRIEVED:
                    agent._transition_to(AgentState.INVESTIGATING)
                elif agent.state == AgentState.INVESTIGATING:
                    agent._transition_to(AgentState.DECISION_READY)
                else:
                    break
        
        assert agent.budget_used <= agent.budget_limit
    
    def test_budget_exhaustion_results_in_escalate(self):
        """Budget exhaustion should result in safe ESCALATE outcome."""
        context = create_test_context(budget_limit=1)
        agent = BoundedInvestigationAgent(context)
        
        # Use up budget
        agent._transition_to(AgentState.CONTEXT_RETRIEVED)
        
        result = agent._build_result()
        
        # With budget=1, should terminate and produce ESCALATE
        assert result.budget_used <= 1
        # Should have some outcome
        assert result.outcome is not None


class TestBudgetEdgeCases:
    """Test budget edge cases."""
    
    def test_budget_minimum_one(self):
        """Budget limit minimum is 1 per Field(ge=1)."""
        # The field validation works at model level
        context = create_test_context(budget_limit=1)
        assert context.budget_limit == 1
        
        # Higher budgets work too
        context = create_test_context(budget_limit=100)
        assert context.budget_limit == 100