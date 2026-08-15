from __future__ import annotations

from datetime import date
from typing import Any

from apx.config.settings import get_settings
from apx.data.schemas import ExceptionCode
from apx.evidence.schemas import Evidence, EvidenceValidityResult, ValidityStatus, SourceAuthority


class EvidenceValidator:
    def __init__(self, reference_date: date | None = None):
        self.reference_date = reference_date or date.today()
        self.settings = get_settings()

    def set_reference_date(self, reference_date: date):
        """Allow tests/evaluation to inject a fixed date."""
        self.reference_date = reference_date

    def validate(self, evidence: Evidence, exception_report: ExceptionCode | list[ExceptionCode] | None = None, invoice_vendor_id: str | None = None) -> EvidenceValidityResult:
        reasons = []
        is_valid = True

        # 1. Check effective dates
        if evidence.effective_from > self.reference_date:
            reasons.append(f"Evidence not yet effective (effective_from: {evidence.effective_from})")
            is_valid = False
        elif evidence.effective_until < self.reference_date:
            reasons.append(f"Evidence expired (effective_until: {evidence.effective_until})")
            is_valid = False

        # 2. Check vendor match
        if invoice_vendor_id and evidence.vendor_id:
            if evidence.vendor_id != invoice_vendor_id:
                reasons.append(f"Vendor mismatch: evidence vendor {evidence.vendor_id} != invoice vendor {invoice_vendor_id}")
                is_valid = False

        # 3. Check policy version (basic check)
        if evidence.policy_version and evidence.policy_version.startswith("v0."):
            reasons.append(f"Outdated policy version: {evidence.policy_version}")
            is_valid = False

        # 4. Check outcome validity
        invalid_outcomes = {"REJECTED", "EXPIRED", "FAILED", "INVALID"}
        if evidence.outcome in invalid_outcomes:
            reasons.append(f"Invalid outcome: {evidence.outcome}")
            is_valid = False

        # 5. Check source authority
        low_authority = {SourceAuthority.EXTERNAL}
        if evidence.source_authority in low_authority:
            reasons.append(f"Low authority source: {evidence.source_authority.value}")

        # 6. Check scope relevance
        if evidence.scope in {"irrelevant", "stale_test"}:
            reasons.append(f"Test/scope flag: {evidence.scope}")
            is_valid = False

        # Determine status
        if is_valid:
            status = ValidityStatus.VALID
        elif evidence.effective_until < self.reference_date or evidence.effective_from > self.reference_date:
            status = ValidityStatus.STALE
        elif invoice_vendor_id and evidence.vendor_id and evidence.vendor_id != invoice_vendor_id:
            status = ValidityStatus.VENDOR_MISMATCH
        elif evidence.outcome in invalid_outcomes:
            status = ValidityStatus.INVALID_OUTCOME
        elif evidence.scope in {"irrelevant", "stale_test"}:
            status = ValidityStatus.OUT_OF_SCOPE
        else:
            status = ValidityStatus.INVALID

        return EvidenceValidityResult(
            evidence_id=evidence.evidence_id,
            is_valid=is_valid,
            status=status,
            reasons=reasons,
        )

    def validate_batch(
        self,
        evidence_list: list[Evidence],
        exception_report: ExceptionCode | list[ExceptionCode] | None = None,
        invoice_vendor_id: str | None = None,
    ) -> list[EvidenceValidityResult]:
        return [self.validate(e, exception_report, invoice_vendor_id) for e in evidence_list]