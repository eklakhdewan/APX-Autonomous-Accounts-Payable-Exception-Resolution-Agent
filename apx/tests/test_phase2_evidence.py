from __future__ import annotations

import pytest
from datetime import date
from pathlib import Path

from apx.evidence.schemas import (
    Evidence,
    EvidenceType,
    SourceAuthority,
    ValidityStatus,
    RetrievedCandidate,
    ValidatedEvidence,
    EvidenceSet,
)
from apx.evidence.validity import EvidenceValidator
from apx.data.schemas import ExceptionCode


class TestEvidenceSchema:
    def test_evidence_creation(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        assert evidence.evidence_id == "EV-00001"
        assert evidence.evidence_type == EvidenceType.HISTORICAL_RESOLUTION
        assert evidence.vendor_id == "V-0001"

    def test_evidence_serialization(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        data = evidence.model_dump(mode="json")
        assert data["evidence_id"] == "EV-00001"
        assert data["evidence_type"] == "historical_resolution"
        assert data["vendor_id"] == "V-0001"


class TestEvidenceValidity:
    def setup_method(self):
        self.validator = EvidenceValidator(reference_date=date(2025, 6, 15))

    def test_valid_evidence(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert result.is_valid
        assert result.status == ValidityStatus.VALID
        assert len(result.reasons) == 0

    def test_vendor_mismatch_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.VENDOR_POLICY,
            scope="payment_terms",
            scope_target="V-0002",
            vendor_id="V-0002",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="ACTIVE",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.VENDOR_MISMATCH
        assert any("Vendor mismatch" in r for r in result.reasons)

    def test_future_effective_date_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2026, 1, 1),  # Future date
            effective_until=date(2026, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.STALE
        assert any("not yet effective" in r for r in result.reasons)

    def test_expired_evidence_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2023, 1, 1),
            effective_until=date(2024, 12, 31),  # Expired
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.STALE
        assert any("expired" in r.lower() for r in result.reasons)

    def test_policy_version_mismatch_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v0.5",  # Old version
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert any("Outdated policy version" in r for r in result.reasons)

    def test_failed_historical_resolution_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="REJECTED",  # Failed outcome
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.INVALID_OUTCOME
        assert any("Invalid outcome" in r for r in result.reasons)

    def test_low_authority_source_flagged(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.EXTERNAL,  # Low authority
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        # Should still be valid but with warning
        assert result.is_valid  # External source doesn't make it invalid, just flagged
        assert any("Low authority source" in r for r in result.reasons)

    def test_scope_mismatch_rejected(self):
        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="irrelevant",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = self.validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.OUT_OF_SCOPE
        assert any("Test/scope flag" in r for r in result.reasons)

    def test_reference_date_injection(self):
        """Test that tests can inject a fixed reference date."""
        validator = EvidenceValidator()
        validator.set_reference_date(date(2025, 1, 1))

        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )
        result = validator.validate(evidence, invoice_vendor_id="V-0001")
        assert result.is_valid  # Valid as of 2025-01-01

        # Now test with a date after expiration
        validator.set_reference_date(date(2026, 1, 1))
        result = validator.validate(evidence, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.STALE


class TestRRF:
    def test_rrf_fusion(self):
        from apx.evidence.rrf import rrf_fuse
        from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority

        # Create mock evidence
        def make_evidence(eid: str) -> Evidence:
            return Evidence(
                evidence_id=eid,
                evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
                scope="vendor_exception",
                scope_target="V-0001:AMOUNT_MISMATCH",
                vendor_id="V-0001",
                effective_from=date(2024, 1, 1),
                effective_until=date(2025, 12, 31),
                policy_version="v1.0",
                outcome="AUTO_APPROVED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=10,
                content=f"Evidence {eid}",
                metadata={},
            )

        # BM25 candidates: EV-001 (rank 1), EV-002 (rank 2), EV-003 (rank 3)
        bm25_candidates = [
            RetrievedCandidate(evidence=make_evidence("EV-001"), bm25_score=10.0, bm25_rank=1, retrieval_sources=["BM25"]),
            RetrievedCandidate(evidence=make_evidence("EV-002"), bm25_score=8.0, bm25_rank=2, retrieval_sources=["BM25"]),
            RetrievedCandidate(evidence=make_evidence("EV-003"), bm25_score=5.0, bm25_rank=3, retrieval_sources=["BM25"]),
        ]

        # Dense candidates: EV-002 (rank 1), EV-001 (rank 2), EV-004 (rank 3)
        dense_candidates = [
            RetrievedCandidate(evidence=make_evidence("EV-002"), dense_score=0.9, dense_rank=1, retrieval_sources=["Dense"]),
            RetrievedCandidate(evidence=make_evidence("EV-001"), dense_score=0.8, dense_rank=2, retrieval_sources=["Dense"]),
            RetrievedCandidate(evidence=make_evidence("EV-004"), dense_score=0.7, dense_rank=3, retrieval_sources=["Dense"]),
        ]

        fused = rrf_fuse(bm25_candidates, dense_candidates, k=60, rrf_constant=60)

        # EV-001 and EV-002 appear in both, should rank highest
        # EV-003 only in BM25, EV-004 only in Dense
        assert len(fused) == 4
        assert fused[0].evidence.evidence_id in {"EV-001", "EV-002"}  # Both in both lists
        assert fused[1].evidence.evidence_id in {"EV-001", "EV-002"}
        assert fused[2].evidence.evidence_id in {"EV-003", "EV-004"}
        assert fused[3].evidence.evidence_id in {"EV-003", "EV-004"}

    def test_rrf_deterministic(self):
        from apx.evidence.rrf import rrf_fuse
        from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority

        def make_evidence(eid: str) -> Evidence:
            return Evidence(
                evidence_id=eid,
                evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
                scope="vendor_exception",
                scope_target="V-0001:AMOUNT_MISMATCH",
                vendor_id="V-0001",
                effective_from=date(2024, 1, 1),
                effective_until=date(2025, 12, 31),
                policy_version="v1.0",
                outcome="AUTO_APPROVED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=10,
                content=f"Evidence {eid}",
                metadata={},
            )

        bm25_candidates = [
            RetrievedCandidate(evidence=make_evidence("EV-001"), bm25_score=10.0, bm25_rank=1, retrieval_sources=["BM25"]),
            RetrievedCandidate(evidence=make_evidence("EV-002"), bm25_score=8.0, bm25_rank=2, retrieval_sources=["BM25"]),
        ]

        dense_candidates = [
            RetrievedCandidate(evidence=make_evidence("EV-001"), dense_score=0.9, dense_rank=1, retrieval_sources=["Dense"]),
            RetrievedCandidate(evidence=make_evidence("EV-002"), dense_score=0.8, dense_rank=2, retrieval_sources=["Dense"]),
        ]

        fused1 = rrf_fuse(bm25_candidates, dense_candidates)
        fused2 = rrf_fuse(bm25_candidates, dense_candidates)

        # Should be deterministic
        assert [c.evidence.evidence_id for c in fused1] == [c.evidence.evidence_id for c in fused2]
        assert [c.rrf_score for c in fused1] == [c.rrf_score for c in fused2]


class TestRetrievedCandidate:
    def test_candidate_creation(self):
        from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority, RetrievedCandidate

        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )

        candidate = RetrievedCandidate(
            evidence=evidence,
            bm25_score=10.0,
            bm25_rank=1,
            dense_score=0.9,
            dense_rank=2,
            rrf_score=0.05,
            rrf_rank=1,
            retrieval_sources=["BM25", "Dense"],
        )
        assert candidate.evidence.evidence_id == "EV-00001"
        assert candidate.bm25_rank == 1
        assert candidate.dense_rank == 2
        assert candidate.rrf_rank == 1
        assert "BM25" in candidate.retrieval_sources
        assert "Dense" in candidate.retrieval_sources


class TestValidatedEvidence:
    def test_validated_evidence_creation(self):
        from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority, ValidatedEvidence, ValidityStatus

        evidence = Evidence(
            evidence_id="EV-00001",
            evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
            scope="vendor_exception",
            scope_target="V-0001:AMOUNT_MISMATCH",
            vendor_id="V-0001",
            effective_from=date(2024, 1, 1),
            effective_until=date(2025, 12, 31),
            policy_version="v1.0",
            outcome="AUTO_APPROVED",
            source_authority=SourceAuthority.INTERNAL,
            usage_count=10,
            content="Test evidence content",
            metadata={},
        )

        validated = ValidatedEvidence(
            evidence=evidence,
            relevance_score=0.95,
            reranker_score=0.92,
            retrieval_sources=["BM25", "Dense", "Reranker"],
            rank=1,
            validity_status=ValidityStatus.VALID,
            validity_reasons=[],
            scope_metadata={"scope": "vendor_exception", "vendor_id": "V-0001"},
            source_authority=SourceAuthority.INTERNAL,
            content="Test evidence content",
        )
        assert validated.evidence.evidence_id == "EV-00001"
        assert validated.validity_status == ValidityStatus.VALID
        assert validated.rank == 1


class TestEvidenceSet:
    def test_evidence_set_counts(self):
        from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority, ValidatedEvidence, ValidityStatus, EvidenceSet

        def make_validated(eid: str, valid: bool = True) -> ValidatedEvidence:
            evidence = Evidence(
                evidence_id=eid,
                evidence_type=EvidenceType.HISTORICAL_RESOLUTION,
                scope="vendor_exception",
                scope_target="V-0001:AMOUNT_MISMATCH",
                vendor_id="V-0001",
                effective_from=date(2024, 1, 1),
                effective_until=date(2025, 12, 31),
                policy_version="v1.0",
                outcome="AUTO_APPROVED" if valid else "REJECTED",
                source_authority=SourceAuthority.INTERNAL,
                usage_count=10,
                content="Test evidence content",
                metadata={},
            )
            return ValidatedEvidence(
                evidence=evidence,
                relevance_score=0.9,
                reranker_score=0.85,
                retrieval_sources=["BM25", "Dense", "Reranker"],
                rank=1,
                validity_status=ValidityStatus.VALID if valid else ValidityStatus.INVALID_OUTCOME,
                validity_reasons=[] if valid else ["Invalid outcome: REJECTED"],
                scope_metadata={},
                source_authority=SourceAuthority.INTERNAL,
                content="Test",
            )

        validated = [make_validated("EV-001", True), make_validated("EV-002", True), make_validated("EV-003", False)]

        evidence_set = EvidenceSet(
            invoice_id="INV-001",
            vendor_id="V-0001",
            exception_codes=["AMOUNT_MISMATCH"],
            query="test query",
            validated_evidence=validated,
        )
        assert evidence_set.valid_count == 2
        assert evidence_set.invalid_count == 1