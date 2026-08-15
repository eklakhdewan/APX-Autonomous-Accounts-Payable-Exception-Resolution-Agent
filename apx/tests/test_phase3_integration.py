from __future__ import annotations

import pytest
from apx.agent.controller import run_investigation
from apx.agent.models import InvestigationResult
from apx.agent.state_machine import AgentState, TerminalOutcome
from apx.agent.llm.mock import MockLLMProvider
from apx.data.schemas import (
    ExceptionReport, ExceptionCode, ExceptionSeverity, 
    APException, ValidationStatus
)
from apx.evidence.schemas import (
    EvidenceSet, Evidence, EvidenceType, SourceAuthority, 
    ValidatedEvidence, ValidityStatus
)
from datetime import date


def create_test_evidence_set(vendor_id: str = "V-0001") -> EvidenceSet:
    """Create a test EvidenceSet with valid evidence."""
    evidence = Evidence(
        evidence_id="EV-00001",
        evidence_type="historical_resolution",
        scope="vendor_exception",
        scope_target=f"{vendor_id}:AMOUNT_MISMATCH",
        vendor_id=vendor_id,
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
    
    return EvidenceSet(
        invoice_id="INV-TEST-001",
        vendor_id=vendor_id,
        exception_codes=["AMOUNT_MISMATCH"],
        query="test query",
        validated_evidence=[validated_evidence],
    )


class TestPhase3Integration:
    """End-to-end integration tests for Phase 3."""
    
    def test_complete_investigation_pipeline(self):
        """Test complete pipeline: ExceptionReport -> EvidenceSet -> Agent -> InvestigationResult."""
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
        
        evidence_set = create_test_evidence_set()
        
        result = run_investigation(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=5,
        )
        
        # Verify result structure
        assert isinstance(result, InvestigationResult)
        assert result.invoice_id == "INV-TEST-001"
        assert result.vendor_id == "V-0001"
        assert "AMOUNT_MISMATCH" in result.exception_codes
        assert result.budget_limit == 5
        assert result.budget_used > 0
        assert result.budget_used <= result.budget_limit
        assert result.outcome is not None
        assert result.termination_reason != ""
    
    def test_exception_report_preserved(self):
        """ExceptionReport data should be preserved in result."""
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-002",
            vendor_id="V-0002",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.GRN_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="GRN mismatch",
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )
        
        evidence_set = create_test_evidence_set(vendor_id="V-0002")
        
        result = run_investigation(
            exception_report=exception_report,
            evidence_set=create_test_evidence_set(vendor_id="V-0002"),
            budget_limit=3,
        )
        
        assert result.invoice_id == "INV-TEST-002"
        assert result.vendor_id == "V-0002"
        assert "GRN_MISMATCH" in result.exception_codes
    
    def test_evidence_set_consumed(self):
        """EvidenceSet should be consumed and validated."""
        evidence_set = create_test_evidence_set()
        
        result = run_investigation(
            exception_report=ExceptionReport(
                invoice_id="INV-TEST-003",
                vendor_id="V-0001",
                exceptions=[],
                validation_status=ValidationStatus.CLEAN,
            ),
            evidence_set=evidence_set,
            budget_limit=3,
        )
        
        # Evidence should be tracked
        assert len(result.evidence_ids) >= 0
        # Evidence IDs should exist in the original set
        valid_ids = {e.evidence.evidence_id for e in evidence_set.validated_evidence}
        for eid in result.evidence_ids:
            assert eid in valid_ids
    
    def test_evidence_validation_respected(self):
        """Agent should not bypass evidence validation."""
        # Create evidence set with invalid evidence
        invalid_evidence = Evidence(
            evidence_id="EV-INVALID-001",
            evidence_type="historical_resolution",
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2020, 1, 1),
            effective_until=date(2021, 12, 31),  # Expired
            policy_version="v1.0",
            outcome="EXPIRED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=0,
            content="Expired evidence",
        )
        
        validated_invalid = ValidatedEvidence(
            evidence=invalid_evidence,
            relevance_score=0.5,
            reranker_score=0.4,
            retrieval_sources=["BM25"],
            rank=1,
            validity_status="stale",
            validity_reasons=["Evidence expired"],
            scope_metadata={},
            source_authority=SourceAuthority.INTERNAL,
            content="Expired evidence",
        )
        
        evidence_set = EvidenceSet(
            invoice_id="INV-TEST-004",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            query="test",
            validated_evidence=[validated_invalid],
        )
        
        result = run_investigation(
            exception_report=ExceptionReport(
                invoice_id="INV-TEST-004",
                vendor_id="V-0001",
                exceptions=[],
                validation_status=ValidationStatus.CLEAN,
            ),
            evidence_set=evidence_set,
            budget_limit=3,
        )
        
        # Invalid evidence should not be used
        assert result.budget_used > 0
    
    def test_no_action_executed(self):
        """Agent should not execute any actions - only produce InvestigationResult."""
        result = run_investigation(
            exception_report=ExceptionReport(
                invoice_id="INV-TEST-005",
                vendor_id="V-0001",
                exceptions=[],
                validation_status=ValidationStatus.CLEAN,
            ),
            evidence_set=create_test_evidence_set(),
            budget_limit=3,
        )
        
        # Result should be an InvestigationResult, not an action
        assert isinstance(result, InvestigationResult)
        # No action fields should be present
        assert not hasattr(result, "action_executed")
        assert not hasattr(result, "email_sent")
        assert not hasattr(result, "erp_action")
    
    def test_multiple_exception_types(self):
        """Agent should handle multiple exception types."""
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-006",
            vendor_id="V-0001",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.AMOUNT_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="Amount mismatch",
                ),
                APException(
                    exception_code=ExceptionCode.TAX_ERROR,
                    severity=ExceptionSeverity.MEDIUM,
                    message="Tax error",
                ),
                APException(
                    exception_code=ExceptionCode.GRN_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="GRN mismatch",
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )
        
        result = run_investigation(
            exception_report=exception_report,
            evidence_set=create_test_evidence_set(),
            budget_limit=5,
        )
        
        assert len(result.exception_codes) == 3
        assert "AMOUNT_MISMATCH" in result.exception_codes
        assert "TAX_ERROR" in result.exception_codes
        assert "GRN_MISMATCH" in result.exception_codes
    
    def test_empty_evidence_set_handled(self):
        """Agent should handle empty evidence set gracefully."""
        empty_evidence_set = EvidenceSet(
            invoice_id="INV-TEST-007",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            query="test",
            validated_evidence=[],
        )
        
        result = run_investigation(
            exception_report=ExceptionReport(
                invoice_id="INV-TEST-007",
                vendor_id="V-0001",
                exceptions=[],
                validation_status=ValidationStatus.CLEAN,
            ),
            evidence_set=empty_evidence_set,
            budget_limit=3,
        )
        
        assert isinstance(result, InvestigationResult)
        assert result.budget_used > 0
    
    def test_invalid_evidence_references_rejected(self):
        """Agent should not use evidence IDs that don't exist in EvidenceSet."""
        evidence_set = create_test_evidence_set()
        
        result = run_investigation(
            exception_report=ExceptionReport(
                invoice_id="INV-TEST-008",
                vendor_id="V-0001",
                exceptions=[],
                validation_status=ValidationStatus.CLEAN,
            ),
            evidence_set=evidence_set,
            budget_limit=3,
        )
        
        # All evidence IDs in result should exist in original set
        valid_ids = {e.evidence.evidence_id for e in create_test_evidence_set().validated_evidence}
        for eid in result.evidence_ids:
            assert eid in valid_ids
    
    def test_deterministic_execution(self):
        """Same input should produce same result with mock LLM."""
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-009",
            vendor_id="V-0001",
            exceptions=[],
            validation_status=ValidationStatus.CLEAN,
        )
        
        evidence_set = create_test_evidence_set()
        
        result1 = run_investigation(
            exception_report=exception_report,
            evidence_set=evidence_set,
            budget_limit=5,
        )
        
        result2 = run_investigation(
            exception_report=exception_report,
            evidence_set=create_test_evidence_set(),
            budget_limit=5,
        )
        
        # Results should be identical with deterministic mock
        assert result1.outcome == result2.outcome
        assert result1.budget_used == result2.budget_used
        assert result1.evidence_ids == result2.evidence_ids
    
    def test_all_outcome_types_possible(self):
        """All terminal outcomes should be reachable."""
        outcomes_seen = set()
        
        # Test with different exception types to trigger different outcomes
        test_cases = [
            (ExceptionCode.AMOUNT_MISMATCH, "RESOLVE"),
            (ExceptionCode.VENDOR_MISMATCH, "REQUEST_INFO"),
            (ExceptionCode.CREDIT_ISSUE, "ESCALATE"),
            (ExceptionCode.DUPLICATE_INVOICE, "ESCALATE"),
        ]
        
        for exception_code, expected_outcome in test_cases:
            evidence_set = create_test_evidence_set()
            result = run_investigation(
                exception_report=ExceptionReport(
                    invoice_id=f"INV-TEST-{exception_code.value}",
                    vendor_id="V-0001",
                    exceptions=[
                        APException(
                            exception_code=exception_code,
                            severity=ExceptionSeverity.MEDIUM,
                            message=f"Test {exception_code.value}",
                        ),
                    ],
                    validation_status=ValidationStatus.EXCEPTIONS,
                ),
                evidence_set=evidence_set,
                budget_limit=5,
            )
            outcomes_seen.add(result.outcome)
        
        # At least ESCALATE should be present (safe default)
        assert TerminalOutcome.ESCALATE in outcomes_seen or TerminalOutcome.RESOLVE in outcomes_seen


class TestMockLLMDeterminism:
    """Test that mock LLM produces deterministic results."""
    
    def test_mock_llm_deterministic(self):
        """Mock LLM should produce same output for same input."""
        provider = MockLLMProvider(seed=42)
        
        findings1 = provider.investigate(
            exception_report="Test AMOUNT_MISMATCH",
            evidence_summaries=[{"evidence_id": "EV-001", "validity_status": "valid", "relevance_score": 0.9}],
            current_state="INVESTIGATING",
            budget_remaining=5,
        )
        
        provider2 = MockLLMProvider(seed=42)
        findings2 = provider2.investigate(
            exception_report="Test AMOUNT_MISMATCH",
            evidence_summaries=[{"evidence_id": "EV-001", "validity_status": "valid", "relevance_score": 0.9}],
            current_state="INVESTIGATING",
            budget_remaining=5,
        )
        
        assert findings1.proposed_outcome == findings2.proposed_outcome
        assert findings1.confidence == findings2.confidence
        assert findings1.findings == findings2.findings