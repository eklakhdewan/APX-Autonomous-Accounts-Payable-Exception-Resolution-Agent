from __future__ import annotations

import pytest
from decimal import Decimal
from apx.guardrail.models import (
    GuardrailDecision,
    GuardrailDecisionResult,
    GuardrailCheckResult,
    ActionPolicy,
    ActionType,
    ApprovalStatus,
    ActionGuardrailConfig,
)
from apx.guardrail.engine import ActionGuardrail
from apx.risk.models import RiskAssessment, RiskDimensionScore, RiskLevel, RiskDimension
from apx.agent.models import InvestigationResult
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.agent.models import InvestigationResult
from apx.agent.state_machine import AgentState
from apx.risk.models import RiskAssessment, RiskDimensionScore, RiskLevel, RiskDimension
from datetime import date


class TestActionGuardrail:
    """Test the action guardrail."""

    def _create_risk_assessment(self, risk_level="MEDIUM"):
        """Create a mock risk assessment."""
        from apx.risk.models import RiskAssessment, RiskDimensionScore, RiskDimension, RiskLevel
        from decimal import Decimal

        return RiskAssessment(
            overall_score=Decimal("0.5") if risk_level == "MEDIUM" else Decimal("0.2"),
            risk_level=RiskLevel(risk_level),
            dimension_scores=[
                RiskDimensionScore(
                    dimension=RiskDimension.FINANCIAL,
                    score=Decimal("0.5"),
                    weight=Decimal("0.25"),
                    weighted_score=Decimal("0.125"),
                    factors=["Amount near threshold"],
                    source_evidence_ids=[],
                ),
            ],
            investigation_outcome="RESOLVE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=["Test reason"],
        )

    def _create_investigation_result(self, outcome="RESOLVE", evidence_count=2) -> InvestigationResult:
        from apx.agent.models import InvestigationResult, InvestigationStep, TerminalOutcome
        from apx.agent.state_machine import AgentState
        from datetime import datetime

        return InvestigationResult(
            case_id="INV-TEST-001",
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            final_state=AgentState.DECISION_READY,
            outcome=TerminalOutcome.RESOLVE if outcome == "RESOLVE" else TerminalOutcome.ESCALATE,
            evidence_ids=[f"EV-{i:05d}" for i in range(evidence_count)],
            findings="Test findings",
            steps=[],
            budget_limit=10,
            budget_used=3,
            termination_reason="Test completed",
        )

    def _create_exception_report(self, exception_codes=None):
        from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus

        if exception_codes is None:
            exception_codes = [ExceptionCode.AMOUNT_MISMATCH]

        exceptions = []
        for code in exception_codes:
            exceptions.append(APException(
                exception_code=code,
                severity=ExceptionSeverity.MEDIUM,
                message=f"Test {code.value}",
                details={},
            ))

        return ExceptionReport(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=exceptions,
            validation_status=ValidationStatus.EXCEPTIONS,
        )

    def test_guardrail_initialization(self):
        """Test guardrail initializes with default policies."""
        guardrail = ActionGuardrail()

        assert "AUTO_RESOLVE" in guardrail.config.policies
        assert "REQUEST_INFORMATION" in guardrail.config.policies
        assert "ESCALATE_TO_HUMAN" in guardrail.config.policies
        assert "ADJUST_PAYMENT" in guardrail.config.policies
        assert "VOID_INVOICE" in guardrail.config.policies
        assert "CONTACT_VENDOR" in guardrail.config.policies
        assert "UPDATE_RECORDS" in guardrail.config.policies
        assert "MANUAL_REVIEW" in guardrail.config.policies

    def test_guardrail_allow_low_risk(self):
        """Test guardrail allows low-risk auto-resolve."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 2)
        exception_report = self._create_exception_report()

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            idempotency_key="test-key-allow-low-risk",
        )

        assert result.decision.value == "ALLOW"

    def test_guardrail_block_high_risk(self):
        """Test guardrail blocks high-risk auto-resolve."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.9"),
            risk_level="CRITICAL",
            dimension_scores=[],
            investigation_outcome="ESCALATE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=["Critical risk"],
        )

        investigation = self._create_investigation_result("ESCALATE", 0)
        exception_report = self._create_exception_report()

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        assert result.decision.value == "BLOCK"

    def test_guardrail_requires_approval_for_medium_risk(self):
        """Test guardrail requires approval for medium risk action that allows medium risk."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.5"),
            risk_level="MEDIUM",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 1)
        exception_report = self._create_exception_report()

        # MANUAL_REVIEW requires approval above LOW risk, so MEDIUM requires approval
        result = guardrail.evaluate(
            action_type="MANUAL_REVIEW",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            idempotency_key="test-key-require-approval-medium-risk",
        )

        # Decision is ALLOW but requires approval before execution
        assert result.decision.value == "ALLOW"
        assert result.requires_approval is True
        assert result.approval_status.value == "PENDING"

    def test_guardrail_blocks_critical_risk(self):
        """Test guardrail blocks critical risk for all actions."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.9"),
            risk_level="CRITICAL",
            dimension_scores=[],
            investigation_outcome="ESCALATE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=["Critical risk"],
        )

        investigation = self._create_investigation_result("ESCALATE", 0)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        # Test multiple action types
        for action_type in ["AUTO_RESOLVE", "ADJUST_PAYMENT", "VOID_INVOICE", "CONTACT_VENDOR"]:
            result = guardrail.evaluate(
                action_type=action_type,
                risk_assessment=risk_assessment,
                investigation_result=investigation,
                exception_report=exception_report,
            )
            assert result.decision.value == "BLOCK", f"Action {action_type} should be blocked at CRITICAL risk"

    def test_escalate_allowed_at_critical(self):
        """Test ESCALATE_TO_HUMAN is allowed even at CRITICAL risk."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.9"),
            risk_level="CRITICAL",
            dimension_scores=[],
            investigation_outcome="ESCALATE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=["Critical risk"],
        )

        investigation = self._create_investigation_result("ESCALATE", 0)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        result = guardrail.evaluate(
            action_type="ESCALATE_TO_HUMAN",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        assert result.decision.value == "ALLOW"

    def test_escalate_outcome_blocks_auto_resolve(self):
        """Test ESCALATE outcome blocks AUTO_RESOLVE."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="ESCALATE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("ESCALATE", 1)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        assert result.decision.value == "BLOCK"

        # But should allow ESCALATE_TO_HUMAN
        result2 = guardrail.evaluate(
            action_type="ESCALATE_TO_HUMAN",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )
        assert result2.decision.value == "ALLOW"

    def test_evidence_sufficiency_check(self):
        """Test evidence sufficiency check."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.3"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 0)  # No evidence
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        # Should require approval due to insufficient evidence
        assert result.decision.value in ["REQUIRE_APPROVAL", "BLOCK"]

    def test_idempotency_check(self):
        """Test idempotency key validation."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 1)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        # First call should pass
        result1 = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            idempotency_key="test-key-123",
        )
        assert result1.decision.value == "ALLOW"

        # Record the action (simulating execution)
        guardrail.record_action("AUTO_RESOLVE", "test-key-123")

        # Second call with same key should fail
        result2 = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            idempotency_key="test-key-123",
        )
        assert result2.decision.value == "BLOCK"

    def test_rate_limiting(self):
        """Test rate limiting."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 1)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        # Make multiple requests up to rate limit
        for i in range(20):  # AUTO_RESOLVE limit is 20/hour
            result = guardrail.evaluate(
                action_type="AUTO_RESOLVE",
                risk_assessment=risk_assessment,
                investigation_result=investigation,
                exception_report=exception_report,
                idempotency_key=f"test-key-{i}",
            )
            if i < 20:
                assert result.decision.value == "ALLOW"
            else:
                assert result.decision.value == "BLOCK"

    def test_investigation_outcome_compatibility(self):
        """Test investigation outcome compatibility with actions."""
        guardrail = ActionGuardrail()

        # ESCALATE outcome should block AUTO_RESOLVE
        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="ESCALATE",
            evidence_ids=[],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("ESCALATE", 1)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        assert result.decision.value == "BLOCK"

        # But should allow ESCALATE_TO_HUMAN
        result2 = guardrail.evaluate(
            action_type="ESCALATE_TO_HUMAN",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )
        assert result2.decision.value == "ALLOW"

    def test_decision_result_structure(self):
        """Test guardrail decision result has all required fields."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.3"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 1)
        exception_report = ExceptionReport(
            invoice_id="INV-001",
            vendor_id="V-001",
            exceptions=[],
            validation_status="EXCEPTIONS",
        )

        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
        )

        # Check all required fields
        assert hasattr(result, 'decision')
        assert hasattr(result, 'checks')
        assert hasattr(result, 'risk_level')
        assert hasattr(result, 'requires_approval')
        assert hasattr(result, 'approval_status')
        assert hasattr(result, 'approval_reason')
        assert hasattr(result, 'idempotency_key')
        assert hasattr(result, 'rate_limit_ok')
        assert hasattr(result, 'block_reason')
        assert hasattr(result, 'allowed_action_types')
        assert hasattr(result, 'required_approvals')
        assert hasattr(result, 'metadata')
        assert isinstance(result.checks, list)
        assert isinstance(result.allowed_action_types, list)
        assert isinstance(result.required_approvals, list)

    def test_amount_check_warning_triggers_require_approval(self):
        """Test amount check with WARNING severity triggers REQUIRE_APPROVAL decision."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 2)
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.AMOUNT_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="Test amount mismatch",
                    details={"amount": "5000"},
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )

        # AUTO_RESOLVE has max_amount_without_approval=1000, so 5000 should trigger WARNING
        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            action_params={"amount": "5000"},
            idempotency_key="test-amount-warning",
        )

        # Decision should be REQUIRE_APPROVAL (not BLOCK) due to WARNING severity
        assert result.decision.value == "REQUIRE_APPROVAL"
        assert result.requires_approval is True
        assert result.approval_status.value == "PENDING"

        # Verify amount check is in checks with WARNING severity
        amount_checks = [c for c in result.checks if c.check_name == "amount_check"]
        assert len(amount_checks) == 1
        assert amount_checks[0].passed is False
        assert amount_checks[0].severity == "WARNING"
        assert "exceeds max without approval" in amount_checks[0].reason

    def test_amount_check_within_limit_allows(self):
        """Test amount check within limit passes with INFO severity."""
        guardrail = ActionGuardrail()

        risk_assessment = RiskAssessment(
            overall_score=Decimal("0.2"),
            risk_level="LOW",
            dimension_scores=[],
            investigation_outcome="RESOLVE",
            evidence_ids=["EV-001"],
            calculation_metadata={},
            reasons=[],
        )

        investigation = self._create_investigation_result("RESOLVE", 2)
        exception_report = ExceptionReport(
            invoice_id="INV-TEST-001",
            vendor_id="V-0001",
            exceptions=[
                APException(
                    exception_code=ExceptionCode.AMOUNT_MISMATCH,
                    severity=ExceptionSeverity.MEDIUM,
                    message="Test amount mismatch",
                    details={"amount": "500"},
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )

        # Amount 500 is within AUTO_RESOLVE limit of 1000
        result = guardrail.evaluate(
            action_type="AUTO_RESOLVE",
            risk_assessment=risk_assessment,
            investigation_result=investigation,
            exception_report=exception_report,
            action_params={"amount": "500"},
            idempotency_key="test-amount-within-limit",
        )

        # Decision should be ALLOW (assuming other checks pass)
        assert result.decision.value == "ALLOW"

        # Verify amount check passes with INFO severity
        amount_checks = [c for c in result.checks if c.check_name == "amount_check"]
        assert len(amount_checks) == 1
        assert amount_checks[0].passed is True
        assert amount_checks[0].severity == "INFO"
        assert "within approval limit" in amount_checks[0].reason