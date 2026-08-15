from __future__ import annotations

from decimal import Decimal
from typing import Any

from apx.config.settings import get_settings
from apx.data.schemas import ExceptionCode, ExceptionReport
from apx.evidence.schemas import EvidenceSet, ValidityStatus
from apx.agent.models import InvestigationResult
from apx.risk.models import (
    RiskAssessment,
    RiskDimension,
    RiskDimensionScore,
    RiskLevel,
    RiskPolicyConfig,
    RiskThresholds,
)


class CompoundRiskEngine:
    """
    Deterministic compound risk engine evaluating five risk dimensions:
    - financial
    - compliance
    - vendor
    - operational
    - evidence_confidence
    """

    def __init__(self, config: RiskPolicyConfig | None = None):
        self.settings = get_settings()
        self.risk_policy = self.settings.risk_policy
        self.config = config or self._load_config()

    def _load_config(self) -> RiskPolicyConfig:
        """Load risk configuration from settings."""
        return RiskPolicyConfig(
            thresholds=RiskThresholds(
                low_max=Decimal("0.3"),
                medium_max=Decimal("0.6"),
                high_max=Decimal("0.8"),
            ),
            dimension_weights={
                "financial": Decimal(str(self.risk_policy.compound_risk_weights.amount)),
                "compliance": Decimal(str(self.risk_policy.compound_risk_weights.severity)),
                "vendor": Decimal(str(self.risk_policy.compound_risk_weights.historical)),
                "operational": Decimal(str(self.risk_policy.compound_risk_weights.evidence)),
                "evidence_confidence": Decimal(str(self.risk_policy.compound_risk_weights.confidence)),
            },
            financial_thresholds={
                "auto_resolve_max": Decimal(str(self.risk_policy.amount_thresholds.auto_resolve_max)),
                "review_required_min": Decimal(str(self.risk_policy.amount_thresholds.review_required_min)),
                "escalate_min": Decimal(str(self.risk_policy.amount_thresholds.escalate_min)),
            },
            severity_weights={
                "LOW": Decimal(str(self.risk_policy.severity_risk.weights.get("LOW", 0.1))),
                "MEDIUM": Decimal(str(self.risk_policy.severity_risk.weights.get("MEDIUM", 0.3))),
                "HIGH": Decimal(str(self.risk_policy.severity_risk.weights.get("HIGH", 0.7))),
                "CRITICAL": Decimal(str(self.risk_policy.severity_risk.weights.get("CRITICAL", 1.0))),
            },
            confidence_thresholds={
                "auto_resolve_min": Decimal(str(self.risk_policy.confidence_thresholds.auto_resolve_min)),
                "human_review_max": Decimal(str(self.risk_policy.confidence_thresholds.human_review_max)),
            },
            evidence_thresholds={
                "auto_resolve_min": self.risk_policy.evidence_thresholds.auto_resolve_min,
                "human_review_min": self.risk_policy.evidence_thresholds.human_review_min,
            },
            historical_thresholds={
                "auto_resolve_min": Decimal(str(self.risk_policy.historical_success_thresholds.auto_resolve_min)),
            },
            always_escalate_rules=[
                {"exception_code": r.exception_code, "reason": r.reason}
                for r in self.risk_policy.always_escalate_rules
            ],
            auto_resolve_rules=[
                {"exception_code": r.exception_code, "max_amount": str(r.max_amount), "reason": r.reason}
                for r in self.risk_policy.auto_resolve_rules
            ],
            compound_weights={
                "amount": Decimal(str(self.risk_policy.compound_risk_weights.amount)),
                "severity": Decimal(str(self.risk_policy.compound_risk_weights.severity)),
                "confidence": Decimal(str(self.risk_policy.compound_risk_weights.confidence)),
                "evidence": Decimal(str(self.risk_policy.compound_risk_weights.evidence)),
                "historical": Decimal(str(self.risk_policy.compound_risk_weights.historical)),
            },
        )

    def assess(
        self,
        investigation_result: InvestigationResult,
        exception_report: ExceptionReport,
        evidence_set: Any = None,
    ) -> RiskAssessment:
        """
        Compute compound risk assessment from investigation result.

        Args:
            investigation_result: Phase 3 investigation result
            exception_report: Phase 1 exception report
            evidence_set: Phase 2 evidence set (optional, for evidence count)

        Returns:
            RiskAssessment with overall score, level, and dimension breakdown
        """
        dimension_scores = []

        # 1. Financial Risk
        financial_score, financial_factors, financial_evidence = self._calculate_financial_risk(
            exception_report, investigation_result
        )
        dimension_scores.append(RiskDimensionScore(
            dimension=RiskDimension.FINANCIAL,
            score=financial_score,
            weight=self.config.dimension_weights.get("financial", Decimal("0.25")),
            weighted_score=financial_score * self.config.dimension_weights.get("financial", Decimal("0.25")),
            factors=financial_factors,
            source_evidence_ids=financial_evidence,
        ))

        # 2. Compliance Risk (Severity-based)
        compliance_score, compliance_factors, compliance_evidence = self._calculate_compliance_risk(
            exception_report, investigation_result
        )
        dimension_scores.append(RiskDimensionScore(
            dimension=RiskDimension.COMPLIANCE,
            score=compliance_score,
            weight=self.config.dimension_weights.get("compliance", Decimal("0.25")),
            weighted_score=compliance_score * self.config.dimension_weights.get("compliance", Decimal("0.25")),
            factors=compliance_factors,
            source_evidence_ids=compliance_evidence,
        ))

        # 3. Vendor Risk (Historical)
        vendor_score, vendor_factors, vendor_evidence = self._calculate_vendor_risk(
            exception_report, investigation_result
        )
        dimension_scores.append(RiskDimensionScore(
            dimension=RiskDimension.VENDOR,
            score=vendor_score,
            weight=self.config.dimension_weights.get("vendor", Decimal("0.15")),
            weighted_score=vendor_score * self.config.dimension_weights.get("vendor", Decimal("0.15")),
            factors=vendor_factors,
            source_evidence_ids=vendor_evidence,
        ))

        # 4. Operational Risk (Evidence quality/quantity)
        operational_score, operational_factors, operational_evidence = self._calculate_operational_risk(
            exception_report, investigation_result, evidence_set
        )
        dimension_scores.append(RiskDimensionScore(
            dimension=RiskDimension.OPERATIONAL,
            score=operational_score,
            weight=self.config.dimension_weights.get("operational", Decimal("0.15")),
            weighted_score=operational_score * self.config.dimension_weights.get("operational", Decimal("0.15")),
            factors=operational_factors,
            source_evidence_ids=operational_evidence,
        ))

        # 5. Evidence/Confidence Risk
        evidence_confidence_score, evidence_confidence_factors, evidence_confidence_evidence = self._calculate_evidence_confidence_risk(
            exception_report, investigation_result, evidence_set
        )
        dimension_scores.append(RiskDimensionScore(
            dimension=RiskDimension.EVIDENCE_CONFIDENCE,
            score=evidence_confidence_score,
            weight=self.config.dimension_weights.get("evidence_confidence", Decimal("0.20")),
            weighted_score=evidence_confidence_score * self.config.dimension_weights.get("evidence_confidence", Decimal("0.20")),
            factors=evidence_confidence_factors,
            source_evidence_ids=evidence_confidence_evidence,
        ))

        # Calculate overall score
        overall_score = sum(ds.weighted_score for ds in dimension_scores)
        overall_score = min(overall_score, Decimal("1.0"))

        # Determine risk level
        risk_level = self._determine_risk_level(overall_score)

        # Collect all evidence IDs
        all_evidence_ids = []
        for ds in dimension_scores:
            all_evidence_ids.extend(ds.source_evidence_ids)

        # Generate reasons
        reasons = self._generate_reasons(dimension_scores, investigation_result, exception_report)

        # Build calculation metadata
        calculation_metadata = {
            "dimension_weights": {k: str(v) for k, v in self.config.dimension_weights.items()},
            "thresholds": {
                "low_max": str(self.config.thresholds.low_max),
                "medium_max": str(self.config.thresholds.medium_max),
                "high_max": str(self.config.thresholds.high_max),
            },
            "always_escalate_triggered": self._check_always_escalate(exception_report, investigation_result),
            "auto_resolve_triggered": self._check_auto_resolve(exception_report, investigation_result),
        }

        return RiskAssessment(
            overall_score=overall_score,
            risk_level=risk_level,
            dimension_scores=dimension_scores,
            investigation_outcome=investigation_result.outcome.value if investigation_result.outcome else "UNKNOWN",
            evidence_ids=list(dict.fromkeys(all_evidence_ids)),  # deduplicate
            calculation_metadata=calculation_metadata,
            reasons=reasons,
        )

    def _calculate_financial_risk(
        self,
        exception_report: ExceptionReport,
        investigation_result: Any,
    ) -> tuple[Decimal, list[str], list[str]]:
        """Calculate financial risk based on invoice amount and thresholds."""
        factors = []
        evidence_ids = []

        # Extract amount from exception report details
        amount = Decimal("0")
        for exc in exception_report.exceptions:
            if "amount" in exc.details:
                try:
                    amount = Decimal(str(exc.details["amount"]))
                except (ValueError, TypeError):
                    pass
            elif "invoice_total" in exc.details:
                try:
                    amount = Decimal(str(exc.details["invoice_total"]))
                except (ValueError, TypeError):
                    pass
            elif "po_total" in exc.details:
                try:
                    amount = Decimal(str(exc.details["po_total"]))
                except (ValueError, TypeError):
                    pass

        auto_resolve_max = self.config.financial_thresholds.get("auto_resolve_max", Decimal("5000"))
        review_required_min = self.config.financial_thresholds.get("review_required_min", Decimal("5000"))
        escalate_min = self.config.financial_thresholds.get("escalate_min", Decimal("50000"))

        if amount >= self.config.financial_thresholds.get("escalate_min", Decimal("50000")):
            score = Decimal("1.0")
            factors.append(f"Amount {amount} exceeds escalation threshold")
        elif amount >= self.config.financial_thresholds.get("review_required_min", Decimal("5000")):
            score = Decimal("0.7")
            factors.append(f"Amount {amount} requires review")
        elif amount >= self.config.financial_thresholds.get("auto_resolve_max", Decimal("5000")):
            score = Decimal("0.4")
            factors.append(f"Amount {amount} near review threshold")
        else:
            score = Decimal("0.1")
            factors.append(f"Amount {amount} within auto-resolve range")

        return score, factors, evidence_ids

    def _calculate_compliance_risk(
        self,
        exception_report: ExceptionReport,
        investigation_result: Any,
    ) -> tuple[Decimal, list[str], list[str]]:
        """Calculate compliance risk based on exception severity."""
        factors = []
        evidence_ids = []

        # Get highest severity from exceptions
        max_severity = "LOW"
        severity_values = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        
        for exc in exception_report.exceptions:
            if severity_values.get(exc.severity.value, 0) > severity_values.get(max_severity, 0):
                max_severity = exc.severity.value

        severity_weights = self.config.severity_weights
        score = severity_weights.get(max_severity, Decimal("0.1"))
        
        factors.append(f"Highest exception severity: {max_severity}")
        if max_severity in ("HIGH", "CRITICAL"):
            factors.append("High-severity exception requires careful review")

        return score, factors, evidence_ids

    def _calculate_vendor_risk(
        self,
        exception_report: ExceptionReport,
        investigation_result: Any,
    ) -> tuple[Decimal, list[str], list[str]]:
        """Calculate vendor risk based on historical success rate and credit status."""
        factors = []
        evidence_ids = []

        # Check for credit issues
        credit_issue = any(exc.exception_code == ExceptionCode.CREDIT_ISSUE for exc in exception_report.exceptions)
        
        # Get historical success rate from investigation (if available)
        # For now, use a default based on credit issue presence
        if credit_issue:
            score = Decimal("0.9")
            factors.append("Vendor has credit hold/issue")
        else:
            # Use historical success threshold as baseline
            auto_resolve_min = self.config.historical_thresholds.get("auto_resolve_min", Decimal("0.85"))
            score = Decimal("1.0") - auto_resolve_min  # inverse: lower success rate = higher risk
            factors.append(f"Vendor historical success rate baseline: {auto_resolve_min}")

        return min(score, Decimal("1.0")), factors, evidence_ids

    def _calculate_operational_risk(
        self,
        exception_report: ExceptionReport,
        investigation_result: Any,
        evidence_set: Any = None,
    ) -> tuple[Decimal, list[str], list[str]]:
        """Calculate operational risk based on evidence quality and quantity."""
        factors = []
        evidence_ids = []

        valid_count = 0
        total_count = 0
        
        if evidence_set and hasattr(evidence_set, "validated_evidence"):
            for ev in evidence_set.validated_evidence:
                total_count += 1
                if ev.validity_status == ValidityStatus.VALID:
                    valid_count += 1
                    evidence_ids.append(ev.evidence.evidence_id)

        if total_count == 0:
            score = Decimal("0.8")
            factors.append("No validated evidence available")
        else:
            validity_ratio = Decimal(str(valid_count)) / Decimal(str(total_count))
            if validity_ratio < Decimal("0.5"):
                score = Decimal("0.7")
                factors.append(f"Low evidence validity ratio: {validity_ratio:.1%}")
            elif validity_ratio < Decimal("0.8"):
                score = Decimal("0.4")
                factors.append(f"Moderate evidence validity ratio: {validity_ratio:.1%}")
            else:
                score = Decimal("0.1")
                factors.append(f"High evidence validity ratio: {validity_ratio:.1%}")

            # Check evidence count thresholds
            auto_resolve_min = self.config.evidence_thresholds.get("auto_resolve_min", 3)
            human_review_min = self.config.evidence_thresholds.get("human_review_min", 1)
            
            if valid_count < human_review_min:
                score = max(score, Decimal("0.8"))
                factors.append(f"Insufficient valid evidence: {valid_count}")
            elif valid_count < auto_resolve_min:
                score = max(score, Decimal("0.5"))
                factors.append(f"Below auto-resolve evidence threshold: {valid_count}/{auto_resolve_min}")

        return min(score, Decimal("1.0")), factors, evidence_ids

    def _calculate_evidence_confidence_risk(
        self,
        exception_report: ExceptionReport,
        investigation_result: Any,
        evidence_set: Any = None,
    ) -> tuple[Decimal, list[str], list[str]]:
        """Calculate evidence/confidence risk based on investigation confidence and evidence quality."""
        factors = []
        evidence_ids = []

        # Base confidence from investigation result
        # The mock LLM provides confidence in its findings
        base_confidence = Decimal("0.5")  # default
        
        # Check if we have high-confidence evidence
        if investigation_result and investigation_result.evidence_ids:
            evidence_ids = investigation_result.evidence_ids
            
            # Higher confidence if investigation had relevant evidence
            if len(investigation_result.evidence_ids) >= 3:
                base_confidence = Decimal("0.8")
                factors.append("Multiple relevant evidence items found")
            elif len(investigation_result.evidence_ids) >= 1:
                base_confidence = Decimal("0.6")
                factors.append("Some relevant evidence found")
            else:
                base_confidence = Decimal("0.3")
                factors.append("No relevant evidence found in investigation")
        else:
            base_confidence = Decimal("0.3")
            factors.append("No evidence referenced in investigation")

        # Risk is inverse of confidence
        score = Decimal("1.0") - base_confidence
        
        # Check confidence thresholds
        auto_resolve_min = self.config.confidence_thresholds.get("auto_resolve_min", Decimal("0.9"))
        human_review_max = self.config.confidence_thresholds.get("human_review_max", Decimal("0.7"))
        
        if base_confidence >= auto_resolve_min:
            factors.append(f"High confidence ({base_confidence}) supports auto-resolve")
        elif base_confidence <= human_review_max:
            factors.append(f"Low confidence ({base_confidence}) requires human review")

        return min(score, Decimal("1.0")), factors, evidence_ids

    def _determine_risk_level(self, overall_score: Decimal) -> RiskLevel:
        """Determine risk level from overall score."""
        if overall_score <= self.config.thresholds.low_max:
            return RiskLevel.LOW
        elif overall_score <= self.config.thresholds.medium_max:
            return RiskLevel.MEDIUM
        elif overall_score <= self.config.thresholds.high_max:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _generate_reasons(
        self,
        dimension_scores: list,
        investigation_result: Any,
        exception_report: ExceptionReport,
    ) -> list[str]:
        """Generate human-readable reasons for the risk assessment."""
        reasons = []
        
        # Add dimension-specific reasons
        for ds in dimension_scores:
            reasons.extend([f"{ds.dimension.value}: {f}" for f in ds.factors])
        
        # Add investigation outcome reason
        if investigation_result.outcome:
            reasons.append(f"Investigation outcome: {investigation_result.outcome.value}")
        
        # Add exception codes
        if exception_report.exceptions:
            exception_types = [exc.exception_code.value for exc in exception_report.exceptions]
            reasons.append(f"Exceptions detected: {', '.join(exception_types)}")
        
        return reasons

    def _check_always_escalate(self, exception_report: ExceptionReport, investigation_result: Any) -> bool:
        """Check if any always-escalate rules are triggered."""
        for rule in self.config.always_escalate_rules:
            if "exception_code" in rule:
                if any(exc.exception_code.value == rule["exception_code"] for exc in exception_report.exceptions):
                    return True
            elif "condition" in rule:
                # Simple condition evaluation (amount > threshold)
                if "amount >" in rule["condition"]:
                    try:
                        threshold_str = rule["condition"].split(">")[1].strip()
                        threshold = Decimal(threshold_str)
                        # Would need actual amount from exception report
                        pass
                    except (ValueError, IndexError):
                        pass
        return False

    def _check_auto_resolve(self, exception_report: ExceptionReport, investigation_result: Any) -> bool:
        """Check if any auto-resolve rules are triggered."""
        for rule in self.config.auto_resolve_rules:
            if "exception_code" in rule:
                if any(exc.exception_code.value == rule["exception_code"] for exc in exception_report.exceptions):
                    # Also check amount threshold
                    if "max_amount" in rule:
                        # Would need actual amount
                        pass
                    return True
        return False