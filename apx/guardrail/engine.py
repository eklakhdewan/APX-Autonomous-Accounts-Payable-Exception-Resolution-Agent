from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Optional

from apx.config.settings import get_settings
from apx.risk.models import RiskAssessment, RiskLevel
from apx.agent.models import InvestigationResult
from apx.data.schemas import ExceptionReport, ExceptionCode
from apx.guardrail.models import (
    ActionGuardrailConfig,
    ActionPolicy,
    ActionType,
    GuardrailDecision,
    GuardrailDecisionResult,
    GuardrailCheckResult,
    ApprovalStatus,
    ActionPolicy,
)


class ActionGuardrail:
    """
    Deterministic action guardrail that evaluates proposed actions against
    risk level, investigation outcome, evidence sufficiency, and policy rules.
    """

    def __init__(self, config: ActionGuardrailConfig | None = None):
        self.settings = get_settings()
        self.config = config or self._load_config()
        self._action_history: list[dict] = []  # In-memory for rate limiting/idempotency

    def _load_config(self) -> ActionGuardrailConfig:
        """Load guardrail configuration from settings."""
        # For now, use default config. In future, could load from YAML.
        return ActionGuardrailConfig(
            policies={
                "AUTO_RESOLVE": ActionPolicy(
                    action_type="AUTO_RESOLVE",
                    allowed_risk_levels=["LOW"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("1000"),
                    requires_idempotency=True,
                    rate_limit_per_hour=20,
                    required_evidence_min=1,
                    required_approvals=[],
                    blocked_risk_levels=["HIGH", "CRITICAL"],
                ),
                "REQUEST_INFORMATION": ActionPolicy(
                    action_type="REQUEST_INFORMATION",
                    allowed_risk_levels=["LOW", "MEDIUM", "HIGH"],
                    requires_approval_above_risk="HIGH",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=True,
                    rate_limit_per_hour=10,
                    required_evidence_min=0,
                    required_approvals=[],
                    blocked_risk_levels=["CRITICAL"],
                ),
                "ESCALATE_TO_HUMAN": ActionPolicy(
                    action_type="ESCALATE_TO_HUMAN",
                    allowed_risk_levels=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=False,
                    rate_limit_per_hour=5,
                    required_evidence_min=0,
                    required_approvals=["human_review"],
                    blocked_risk_levels=[],
                ),
                "ADJUST_PAYMENT": ActionPolicy(
                    action_type="ADJUST_PAYMENT",
                    allowed_risk_levels=["LOW", "MEDIUM"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("5000"),
                    requires_idempotency=True,
                    rate_limit_per_hour=5,
                    required_evidence_min=2,
                    required_approvals=["finance_approval"],
                    blocked_risk_levels=["HIGH", "CRITICAL"],
                ),
                "VOID_INVOICE": ActionPolicy(
                    action_type="VOID_INVOICE",
                    allowed_risk_levels=["LOW", "MEDIUM"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=True,
                    rate_limit_per_hour=5,
                    required_evidence_min=2,
                    required_approvals=["finance_approval"],
                    blocked_risk_levels=["HIGH", "CRITICAL"],
                ),
                "CONTACT_VENDOR": ActionPolicy(
                    action_type="CONTACT_VENDOR",
                    allowed_risk_levels=["LOW", "MEDIUM", "HIGH"],
                    requires_approval_above_risk="MEDIUM",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=True,
                    rate_limit_per_hour=10,
                    required_evidence_min=1,
                    required_approvals=[],
                    blocked_risk_levels=["CRITICAL"],
                ),
                "UPDATE_RECORDS": ActionPolicy(
                    action_type="UPDATE_RECORDS",
                    allowed_risk_levels=["LOW", "MEDIUM"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=True,
                    rate_limit_per_hour=20,
                    required_evidence_min=1,
                    required_approvals=[],
                    blocked_risk_levels=["HIGH", "CRITICAL"],
                ),
                "MANUAL_REVIEW": ActionPolicy(
                    action_type="MANUAL_REVIEW",
                    allowed_risk_levels=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    requires_approval_above_risk="LOW",
                    max_amount_without_approval=Decimal("0"),
                    requires_idempotency=False,
                    rate_limit_per_hour=5,
                    required_evidence_min=0,
                    required_approvals=["human_review"],
                    blocked_risk_levels=[],
                ),
            },
            default_policy=ActionPolicy(
                action_type="MANUAL_REVIEW",
                allowed_risk_levels=["LOW", "MEDIUM"],
                requires_approval_above_risk="MEDIUM",
                max_amount_without_approval=Decimal("1000"),
                requires_idempotency=True,
                rate_limit_per_hour=10,
                required_evidence_min=1,
                required_approvals=[],
                blocked_risk_levels=["CRITICAL"],
            ),
            global_rate_limit_per_hour=100,
            idempotency_window_hours=24,
        )

    def evaluate(
        self,
        action_type: str,
        risk_assessment: Any,  # RiskAssessment
        investigation_result: Any,  # InvestigationResult
        exception_report: Any,  # ExceptionReport
        action_params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:  # GuardrailDecisionResult
        """
        Evaluate an action against guardrail policies.
        
        Returns GuardrailDecisionResult with decision and detailed checks.
        """
        action_type_str = action_type.upper()
        policy = self.config.policies.get(action_type_str, self.config.default_policy)
        
        checks = []
        
        # 1. Risk level check
        risk_level = risk_assessment.risk_level.value if hasattr(risk_assessment.risk_level, 'value') else str(risk_assessment.risk_level)
        risk_check = self._check_risk_level(risk_level, policy)
        checks.append(risk_check)
        
        # 2. Action type allowed for risk level
        allowed_check = self._check_action_allowed(action_type_str, risk_level, policy)
        checks.append(allowed_check)
        
        # 3. Evidence sufficiency
        evidence_check = self._check_evidence_sufficiency(investigation_result, policy)
        checks.append(evidence_check)
        
        # 4. Amount check (if applicable)
        amount_check = self._check_amount(
            investigation_result, policy, exception_report, action_params
        )
        if amount_check:
            checks.append(amount_check)
        
        # 5. Idempotency check
        idempotency_check = self._check_idempotency(idempotency_key, policy)
        if idempotency_check:
            checks.append(idempotency_check)
        
        # 6. Rate limit check
        rate_limit_check = self._check_rate_limit(action_type, policy)
        checks.append(rate_limit_check)
        
        # 6. Investigation outcome compatibility
        outcome_check = self._check_investigation_outcome(investigation_result, action_type)
        checks.append(outcome_check)
        
        # 7. Always escalate rules
        escalate_check = self._check_always_escalate(exception_report, investigation_result)
        if escalate_check:
            checks.append(escalate_check)
        
        # 8. Auto-resolve rules
        auto_resolve_check = self._check_auto_resolve(exception_report, investigation_result)
        if auto_resolve_check:
            checks.append(auto_resolve_check)

        # Determine overall decision
        decision = self._determine_decision(checks, policy, risk_level)
        
        # Determine approval requirements
        requires_approval = self._requires_approval(decision, policy, risk_level)
        approval_status = ApprovalStatus.PENDING if requires_approval else ApprovalStatus.NOT_REQUIRED
        
        return GuardrailDecisionResult(
            decision=decision,
            action_type=ActionType(action_type) if action_type in [a.value for a in ActionType] else ActionType.MANUAL_REVIEW,
            checks=checks,
            risk_level=risk_level,
            requires_approval=requires_approval,
            approval_status=approval_status,
            approval_reason=self._get_approval_reason(decision, policy, risk_level),
            idempotency_key=idempotency_key or "",
            rate_limit_ok=all(c.passed for c in checks if c.check_name == "rate_limit"),
            rate_limit_reason=self._get_rate_limit_reason(checks),
            block_reason=self._get_block_reason(checks),
            allowed_action_types=self._get_allowed_actions(policy, risk_level),
            required_approvals=self._get_required_approvals(policy, decision),
            metadata={
                "action_type": action_type,
                "risk_level": risk_level,
                "investigation_outcome": investigation_result.outcome.value if investigation_result.outcome else "UNKNOWN",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def _check_risk_level(self, risk_level: str, policy: ActionPolicy) -> GuardrailCheckResult:
        """Check if risk level is allowed for this action."""
        if risk_level in policy.blocked_risk_levels:
            return GuardrailCheckResult(
                check_name="risk_level_blocked",
                passed=False,
                reason=f"Risk level {risk_level} is blocked for this action",
                severity="ERROR",
            )
        return GuardrailCheckResult(
            check_name="risk_level_allowed",
            passed=True,
            reason=f"Risk level {risk_level} is allowed",
            severity="INFO",
        )

    def _check_action_allowed(self, action_type: str, risk_level: str, policy: ActionPolicy) -> GuardrailCheckResult:
        """Check if action type is allowed for the given risk level."""
        if risk_level not in policy.allowed_risk_levels:
            return GuardrailCheckResult(
                check_name="action_allowed_for_risk",
                passed=False,
                reason=f"Action {action_type} not allowed for risk level {risk_level}",
                severity="ERROR",
            )
        return GuardrailCheckResult(
            check_name="action_allowed_for_risk",
            passed=True,
            reason=f"Action {action_type} allowed for risk level {risk_level}",
            severity="INFO",
        )

    def _check_evidence_sufficiency(self, investigation_result: Any, policy: ActionPolicy) -> GuardrailCheckResult:
        """Check if investigation has sufficient evidence."""
        evidence_count = len(investigation_result.evidence_ids) if investigation_result.evidence_ids else 0
        required = policy.required_evidence_min
        
        if evidence_count < required:
            return GuardrailCheckResult(
                check_name="evidence_sufficiency",
                passed=False,
                reason=f"Insufficient evidence: {evidence_count}/{required}",
                severity="ERROR",
            )
        return GuardrailCheckResult(
            check_name="evidence_sufficiency",
            passed=True,
            reason=f"Sufficient evidence: {evidence_count}/{required}",
            severity="INFO",
        )

    def _check_amount(
        self,
        investigation_result: Any,
        policy: ActionPolicy,
        exception_report: Any = None,
        action_params: dict[str, Any] | None = None,
    ) -> Optional[GuardrailCheckResult]:
        """Check if action amount is within approval limits."""
        # Try to get amount from action_params first, then from exception_report
        amount = None
        
        if action_params and "amount" in action_params:
            try:
                amount = Decimal(str(action_params["amount"]))
            except (ValueError, TypeError):
                pass
        
        if amount is None and exception_report:
            for exc in exception_report.exceptions:
                if "amount" in exc.details:
                    try:
                        amount = Decimal(str(exc.details["amount"]))
                        break
                    except (ValueError, TypeError):
                        pass
                elif "invoice_total" in exc.details:
                    try:
                        amount = Decimal(str(exc.details["invoice_total"]))
                        break
                    except (ValueError, TypeError):
                        pass
                elif "po_total" in exc.details:
                    try:
                        amount = Decimal(str(exc.details["po_total"]))
                        break
                    except (ValueError, TypeError):
                        pass
        
        if amount is None:
            return None
        
        max_without_approval = policy.max_amount_without_approval
        if max_without_approval is None or max_without_approval == Decimal("0"):
            return GuardrailCheckResult(
                check_name="amount_check",
                passed=True,
                reason=f"Amount check not applicable (max_amount_without_approval=0)",
                severity="INFO",
            )
        
        if amount > max_without_approval:
            return GuardrailCheckResult(
                check_name="amount_check",
                passed=False,
                reason=f"Amount {amount} exceeds max without approval {max_without_approval}",
                severity="WARNING",
            )
        
        return GuardrailCheckResult(
            check_name="amount_check",
            passed=True,
            reason=f"Amount {amount} within approval limit {max_without_approval}",
            severity="INFO",
        )

    def _check_idempotency(self, idempotency_key: Optional[str], policy: ActionPolicy) -> Optional[GuardrailCheckResult]:
        """Check idempotency key."""
        if not policy.requires_idempotency:
            return None
        
        if not idempotency_key:
            return GuardrailCheckResult(
                check_name="idempotency_key_required",
                passed=False,
                reason="Idempotency key required for this action",
                severity="ERROR",
            )
        
        # Check if key was used recently
        window_start = datetime.utcnow() - timedelta(hours=24)
        for action in self._action_history:
            if action.get("idempotency_key") == idempotency_key:
                action_time = action.get("timestamp")
                if isinstance(action_time, str):
                    action_time = datetime.fromisoformat(action_time)
                if action_time >= window_start:
                    return GuardrailCheckResult(
                        check_name="idempotency_duplicate",
                        passed=False,
                        reason=f"Idempotency key {idempotency_key} already used within window",
                        severity="ERROR",
                    )
        
        return GuardrailCheckResult(
            check_name="idempotency_valid",
            passed=True,
            reason="Idempotency key is valid",
            severity="INFO",
        )

    def _check_rate_limit(self, action_type: str, policy: ActionPolicy) -> GuardrailCheckResult:
        """Check rate limit for action type."""
        window_start = datetime.utcnow() - timedelta(hours=1)
        recent_count = sum(
            1 for a in self._action_history
            if a.get("action_type") == action_type
            and a.get("timestamp", datetime.min) >= window_start
        )
        
        if recent_count >= policy.rate_limit_per_hour:
            return GuardrailCheckResult(
                check_name="rate_limit",
                passed=False,
                reason=f"Rate limit exceeded: {recent_count}/{policy.rate_limit_per_hour} per hour",
                severity="ERROR",
            )
        return GuardrailCheckResult(
            check_name="rate_limit",
            passed=True,
            reason=f"Rate limit OK: {recent_count}/{policy.rate_limit_per_hour} per hour",
            severity="INFO",
        )

    def _check_investigation_outcome(self, investigation_result: Any, action_type: str) -> GuardrailCheckResult:
        """Check if investigation outcome is compatible with action."""
        outcome = investigation_result.outcome
        
        if outcome == "ESCALATE" and action_type in ["AUTO_RESOLVE", "ADJUST_PAYMENT", "VOID_INVOICE"]:
            return GuardrailCheckResult(
                check_name="investigation_outcome_compatible",
                passed=False,
                reason=f"Investigation outcome ESCALATE incompatible with action {action_type}",
                severity="ERROR",
            )
        elif outcome == "REQUEST_INFO" and action_type in ["AUTO_RESOLVE", "ADJUST_PAYMENT", "VOID_INVOICE"]:
            return GuardrailCheckResult(
                check_name="investigation_outcome_compatible",
                passed=False,
                reason=f"Investigation outcome REQUEST_INFO incompatible with action {action_type}",
                severity="ERROR",
            )
        return GuardrailCheckResult(
            check_name="investigation_outcome_compatible",
            passed=True,
            reason=f"Investigation outcome compatible with action",
            severity="INFO",
        )

    def _check_always_escalate(
        self, exception_report: Any, investigation_result: Any = None
    ) -> Optional[GuardrailCheckResult]:
        """Check if any always-escalate rules from risk policy are triggered."""
        risk_policy = self.settings.risk_policy
        
        for rule in risk_policy.always_escalate_rules:
            # Check by exception code
            if rule.exception_code:
                if any(
                    exc.exception_code.value == rule.exception_code
                    for exc in exception_report.exceptions
                ):
                    return GuardrailCheckResult(
                        check_name="always_escalate",
                        passed=False,
                        reason=f"Always-escalate rule triggered: {rule.reason}",
                        severity="ERROR",
                    )
            # Check by condition (e.g., "amount > 100000")
            elif rule.condition:
                condition = rule.condition
                if "amount >" in condition:
                    try:
                        threshold_str = condition.split(">")[1].strip()
                        threshold = Decimal(threshold_str)
                        # Extract amount from exception report
                        amount = Decimal("0")
                        for exc in exception_report.exceptions:
                            if "amount" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["amount"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                            elif "invoice_total" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["invoice_total"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                            elif "po_total" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["po_total"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if amount > threshold:
                            return GuardrailCheckResult(
                                check_name="always_escalate",
                                passed=False,
                                reason=f"Always-escalate rule triggered: {rule.reason}",
                                severity="ERROR",
                            )
                    except (ValueError, IndexError):
                        pass
        return None

    def _check_auto_resolve(
        self, exception_report: Any, investigation_result: Any = None
    ) -> Optional[GuardrailCheckResult]:
        """Check if any auto-resolve rules from risk policy are triggered."""
        risk_policy = self.settings.risk_policy
        
        for rule in risk_policy.auto_resolve_rules:
            if rule.exception_code:
                if any(
                    exc.exception_code.value == rule.exception_code
                    for exc in exception_report.exceptions
                ):
                    # Also check amount threshold if specified
                    max_amount = rule.max_amount
                    if max_amount is not None:
                        max_amount_decimal = Decimal(str(max_amount))
                        # Extract amount from exception report
                        amount = Decimal("0")
                        for exc in exception_report.exceptions:
                            if "amount" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["amount"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                            elif "invoice_total" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["invoice_total"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                            elif "po_total" in exc.details:
                                try:
                                    amount = Decimal(str(exc.details["po_total"]))
                                    break
                                except (ValueError, TypeError):
                                    pass
                        if amount > max_amount_decimal:
                            continue  # Amount exceeds auto-resolve limit
                    
                    return GuardrailCheckResult(
                        check_name="auto_resolve",
                        passed=True,
                        reason=f"Auto-resolve rule matched: {rule.reason}",
                        severity="INFO",
                    )
        return None

    def _determine_decision(
        self,
        checks: list[GuardrailCheckResult],
        policy: ActionPolicy,
        risk_level: str,
    ) -> str:
        """Determine overall guardrail decision from checks."""
        # If any check failed with ERROR severity, block
        for check in checks:
            if not check.passed and check.severity == "ERROR":
                return "BLOCK"
        
        # If any check failed with WARNING, require approval
        for check in checks:
            if not check.passed and check.severity == "WARNING":
                return "REQUIRE_APPROVAL"
        
        # All checks passed
        return "ALLOW"

    def _requires_approval(self, decision: str, policy: ActionPolicy, risk_level: str) -> bool:
        """Determine if human approval is required."""
        if decision == "REQUIRE_APPROVAL":
            return True
        if decision == "BLOCK":
            return False
        # Check if risk level requires approval
        if risk_level in ["HIGH", "CRITICAL"]:
            return True
        # Check if risk level meets or exceeds the approval threshold
        risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        threshold = risk_order.get(policy.requires_approval_above_risk, 0)
        if risk_order.get(risk_level, 0) >= threshold:
            return True
        return False

    def _get_approval_reason(self, decision: str, policy: ActionPolicy, risk_level: str) -> str:
        if decision == "REQUIRE_APPROVAL":
            return f"Action requires human approval (risk: {risk_level})"
        if decision == "BLOCK":
            return "Action blocked by guardrail"
        return "No approval required"

    def _get_rate_limit_reason(self, checks: list) -> str:
        for check in checks:
            if check.check_name == "rate_limit" and not check.passed:
                return check.reason
        return "Rate limit OK"

    def _get_block_reason(self, checks: list) -> str:
        for check in checks:
            if not check.passed and check.severity == "ERROR":
                return check.reason
        return ""

    def _get_allowed_actions(self, policy: ActionPolicy, risk_level: str) -> list[str]:
        # Return all action types that would be allowed at this risk level
        from apx.guardrail.models import ActionType
        return [a.value for a in ActionType if risk_level in self.config.policies.get(a.value, self.config.default_policy).allowed_risk_levels]

    def _get_required_approvals(self, policy: ActionPolicy, decision: str) -> list[str]:
        if decision in ["REQUIRE_APPROVAL", "BLOCK"]:
            return policy.required_approvals or ["human_review"]
        return []

    def record_action(self, action_type: str, idempotency_key: str | None = None) -> None:
        """Record an action for rate limiting and idempotency tracking."""
        self._action_history.append({
            "action_type": action_type,
            "timestamp": datetime.utcnow(),
            "idempotency_key": idempotency_key,
        })
        
        # Clean old history
        window_start = datetime.utcnow() - timedelta(hours=25)
        self._action_history = [
            a for a in self._action_history
            if a.get("timestamp", datetime.min) >= datetime.utcnow() - timedelta(hours=25)
        ]