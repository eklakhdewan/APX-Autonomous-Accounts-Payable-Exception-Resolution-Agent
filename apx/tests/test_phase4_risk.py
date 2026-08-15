from __future__ import annotations

import pytest
from decimal import Decimal
from apx.risk.models import (
    RiskAssessment,
    RiskDimension,
    RiskDimensionScore,
    RiskLevel,
    RiskPolicyConfig,
    RiskThresholds,
)
from apx.risk.engine import CompoundRiskEngine
from apx.agent.models import InvestigationResult, InvestigationStep
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.schemas import EvidenceSet, Evidence, EvidenceType, SourceAuthority, ValidatedEvidence, ValidityStatus
from datetime import date


class TestCompoundRiskEngine:
    """Test the compound risk engine."""
    
    def _create_test_investigation(self, outcome="RESOLVE", evidence_count=1) -> InvestigationResult:
        """Create a test investigation result."""
        from apx.agent.models import InvestigationResult, InvestigationStep, TerminalOutcome
        from apx.agent.state_machine import AgentState
        from datetime import datetime
        
        return InvestigationResult(
            case_id="INV-TEST-001",
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            final_state=AgentState.DECISION_READY,
            outcome="RESOLVE" if outcome == "RESOLVE" else "ESCALATE" if outcome == "ESCALATE" else "REQUEST_INFO",
            evidence_ids=[f"EV-{i:05d}" for i in range(evidence_count)],
            findings="Test findings",
            steps=[],
            budget_limit=10,
            budget_used=3,
            termination_reason="Test completed",
        )
    
    def _create_exception_report(self, exception_codes=None, severities=None):
        """Create a test exception report."""
        if exception_codes is None:
            exception_codes = [ExceptionCode.AMOUNT_MISMATCH]
        if severities is None:
            severities = [ExceptionSeverity.MEDIUM]
        
        exceptions = []
        for i, code in enumerate(exception_codes):
            exceptions.append(APException(
                exception_code=code,
                severity=severities[i] if i < len(severities) else ExceptionSeverity.MEDIUM,
                message=f"Test {code.value}",
                details={"amount": "50000"} if code == ExceptionCode.AMOUNT_MISMATCH else {},
            ))
        
        return ExceptionReport(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=exceptions,
            validation_status=ValidationStatus.EXCEPTIONS,
        )
    
    def test_risk_engine_initialization(self):
        """Test risk engine initializes correctly."""
        engine = CompoundRiskEngine()
        assert engine.config is not None
        assert "financial" in engine.config.dimension_weights
        assert "compliance" in engine.config.dimension_weights
        assert "vendor" in engine.config.dimension_weights
        assert "operational" in engine.config.dimension_weights
        assert "evidence_confidence" in engine.config.dimension_weights
    
    def test_risk_engine_assess_basic(self):
        """Test basic risk assessment."""
        engine = CompoundRiskEngine()
        investigation = self._create_test_investigation()
        exception_report = self._create_exception_report()
        
        assessment = engine.assess(investigation, exception_report)
        
        assert isinstance(assessment, RiskAssessment)
        assert assessment.overall_score >= Decimal("0")
        assert assessment.overall_score <= Decimal("1")
        assert assessment.risk_level in RiskLevel
        assert len(assessment.dimension_scores) == 5
        assert len(assessment.reasons) > 0
    
    def test_financial_risk_high_amount(self):
        """Test financial risk is high for large amounts."""
        engine = CompoundRiskEngine()
        investigation = self._create_test_investigation()
        exception_report = self._create_exception_report(
            exception_codes=[ExceptionCode.AMOUNT_MISMATCH],
            severities=[ExceptionSeverity.HIGH]
        )
        
        assessment = engine.assess(investigation, exception_report)
        
        financial_dim = next(d for d in assessment.dimension_scores if d.dimension.value == "financial")
        assert financial_dim.score >= Decimal("0.7")
    
    def test_compliance_risk_high_severity(self):
        """Test compliance risk is high for critical severity."""
        engine = CompoundRiskEngine()
        investigation = self._create_test_investigation()
        exception_report = self._create_exception_report(
            exception_codes=[ExceptionCode.VENDOR_MISMATCH],
            severities=[ExceptionSeverity.CRITICAL]
        )
        
        assessment = engine.assess(investigation, exception_report)
        
        compliance_dim = next(d for d in assessment.dimension_scores if d.dimension.value == "compliance")
        assert compliance_dim.score >= Decimal("0.7")
    
    def test_evidence_confidence_risk(self):
        """Test evidence confidence risk calculation."""
        engine = CompoundRiskEngine()
        
        # Test with many evidence items
        investigation = self._create_test_investigation(evidence_count=5)
        exception_report = self._create_exception_report()
        
        assessment = engine.assess(investigation, exception_report)
        
        evidence_conf_dim = next(d for d in assessment.dimension_scores if d.dimension.value == "evidence_confidence")
        assert evidence_conf_dim.score < Decimal("0.5")  # Low risk = high confidence
    
    def test_risk_level_determination(self):
        """Test risk level determination from score."""
        engine = CompoundRiskEngine()
        
        # Test thresholds
        assert engine._determine_risk_level(Decimal("0.2")) == RiskLevel.LOW
        assert engine._determine_risk_level(Decimal("0.4")) == RiskLevel.MEDIUM
        assert engine._determine_risk_level(Decimal("0.7")) == RiskLevel.HIGH
        assert engine._determine_risk_level(Decimal("0.9")) == RiskLevel.CRITICAL
    
    def test_always_escalate_rules(self):
        """Test always escalate rules."""
        engine = CompoundRiskEngine()
        investigation = self._create_test_investigation()
        exception_report = self._create_exception_report(
            exception_codes=[ExceptionCode.CREDIT_ISSUE]
        )
        
        assert engine._check_always_escalate(exception_report, None) is True
    
    def test_auto_resolve_rules(self):
        """Test auto-resolve rules."""
        engine = CompoundRiskEngine()
        investigation = self._create_test_investigation()
        exception_report = self._create_exception_report(
            exception_codes=[ExceptionCode.DISCOUNT_ERROR]
        )
        
        assert engine._check_auto_resolve(exception_report, None) is True


class TestRiskModels:
    """Test risk models."""
    
    def test_risk_assessment_creation(self):
        """Test RiskAssessment creation."""
        assessment = RiskAssessment(
            overall_score=Decimal("0.5"),
            risk_level="MEDIUM",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=["Test reason"],
        )
        
        assert assessment.overall_score == Decimal("0.5")
        assert assessment.risk_level == RiskLevel.MEDIUM
        assert assessment.investigation_outcome == "RESOLVE"
    
    def test_risk_dimension_score(self):
        """Test RiskDimensionScore creation."""
        score = RiskDimensionScore(
            dimension="financial",
            score=Decimal("0.5"),
            weight=Decimal("0.25"),
            weighted_score=Decimal("0.125"),
            factors=["Amount near threshold"],
            source_evidence_ids=["EV-001"],
        )
        
        assert score.dimension == RiskDimension.FINANCIAL
        assert score.weighted_score == Decimal("0.125")
    
    def test_risk_thresholds(self):
        """Test risk thresholds."""
        thresholds = RiskThresholds(
            low_max=Decimal("0.3"),
            medium_max=Decimal("0.6"),
            high_max=Decimal("0.8"),
        )
        
        assert thresholds.low_max == Decimal("0.3")
        assert thresholds.medium_max == Decimal("0.6")
        assert thresholds.high_max == Decimal("0.8")