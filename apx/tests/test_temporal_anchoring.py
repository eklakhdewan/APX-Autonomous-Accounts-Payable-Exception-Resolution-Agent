"""Focused tests for temporal anchoring of the evidence pipeline.

These verify that the benchmark/evaluation temporal world is anchored to one
explicit reference date (APX_REFERENCE_DATE) and never to the machine wall clock.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest import mock

import pytest

from apx.evidence.dates import APX_REFERENCE_DATE
from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority, ValidityStatus
from apx.evidence.validity import EvidenceValidator


def _evidence(effective_from: date, effective_until: date, **kwargs) -> Evidence:
    return Evidence(
        evidence_id=kwargs.pop("evidence_id", "EV-TST-0001"),
        evidence_type=kwargs.pop("evidence_type", EvidenceType.HISTORICAL_RESOLUTION),
        scope=kwargs.pop("scope", "vendor_exception"),
        scope_target=kwargs.pop("scope_target", "V-0001:AMOUNT_MISMATCH"),
        vendor_id=kwargs.pop("vendor_id", "V-0001"),
        effective_from=effective_from,
        effective_until=effective_until,
        policy_version=kwargs.pop("policy_version", "v1.0"),
        outcome=kwargs.pop("outcome", "AUTO_APPROVED"),
        source_authority=kwargs.pop("source_authority", SourceAuthority.INTERNAL),
        usage_count=kwargs.pop("usage_count", 10),
        content=kwargs.pop("content", "test evidence"),
        metadata=kwargs.pop("metadata", {}),
    )


class TestExplicitReferenceDatePropagation:
    def test_validator_holds_explicit_reference_date(self):
        ref = date(2026, 8, 29)
        validator = EvidenceValidator(reference_date=ref)
        assert validator.reference_date == ref
        assert validator.reference_date != date.today()

    def test_benchmark_passes_reference_date_to_engine(self):
        with mock.patch("apx.evaluation.benchmark.HybridContextEngine") as engine_cls:
            from apx.evaluation.benchmark import BenchmarkOrchestrator

            orch = BenchmarkOrchestrator(tier="dev", seed=42)
            assert orch.reference_date == APX_REFERENCE_DATE
            kwargs = engine_cls.call_args.kwargs
            assert "reference_date" in kwargs
            assert kwargs["reference_date"] == APX_REFERENCE_DATE

    def test_benchmark_custom_reference_date_propagated(self):
        with mock.patch("apx.evaluation.benchmark.HybridContextEngine") as engine_cls:
            from apx.evaluation.benchmark import BenchmarkOrchestrator

            orch = BenchmarkOrchestrator(tier="dev", seed=42, reference_date="2026-03-15")
            assert orch.reference_date == date(2026, 3, 15)
            assert engine_cls.call_args.kwargs["reference_date"] == date(2026, 3, 15)


class TestValidityAtReferenceDate:
    def test_evidence_valid_at_reference_accepted(self):
        validator = EvidenceValidator(reference_date=APX_REFERENCE_DATE)
        ev = _evidence(date(2025, 1, 1), date(2027, 1, 1))
        result = validator.validate(ev, invoice_vendor_id="V-0001")
        assert result.is_valid
        assert result.status == ValidityStatus.VALID

    def test_evidence_expired_before_reference_rejected(self):
        validator = EvidenceValidator(reference_date=APX_REFERENCE_DATE)
        ev = _evidence(date(2024, 1, 1), date(2025, 1, 1))
        result = validator.validate(ev, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.STALE
        assert any("expired" in r.lower() for r in result.reasons)

    def test_future_evidence_rejected(self):
        validator = EvidenceValidator(reference_date=APX_REFERENCE_DATE)
        ev = _evidence(date(2027, 1, 1), date(2028, 1, 1))
        result = validator.validate(ev, invoice_vendor_id="V-0001")
        assert not result.is_valid
        assert result.status == ValidityStatus.STALE
        assert any("not yet effective" in r.lower() for r in result.reasons)

    def test_boundary_dates_deterministic(self):
        ref = APX_REFERENCE_DATE
        validator = EvidenceValidator(reference_date=ref)

        assert validator.validate(_evidence(ref, ref), invoice_vendor_id="V-0001").is_valid
        assert validator.validate(_evidence(ref, ref + timedelta(days=1)), invoice_vendor_id="V-0001").is_valid
        assert validator.validate(_evidence(ref - timedelta(days=1), ref), invoice_vendor_id="V-0001").is_valid

        not_effective = validator.validate(
            _evidence(ref + timedelta(days=1), ref + timedelta(days=365)), invoice_vendor_id="V-0001"
        )
        assert not not_effective.is_valid
        assert any("not yet effective" in r.lower() for r in not_effective.reasons)

        expired = validator.validate(
            _evidence(ref - timedelta(days=365), ref - timedelta(days=1)), invoice_vendor_id="V-0001"
        )
        assert not expired.is_valid
        assert any("expired" in r.lower() for r in expired.reasons)

    def test_explicit_reference_does_not_depend_on_wall_clock(self):
        ref = date(2026, 8, 29)
        validator = EvidenceValidator(reference_date=ref)
        assert validator.reference_date == ref

        ev_valid = _evidence(ref - timedelta(days=30), ref + timedelta(days=30))
        ev_expired = _evidence(date(2024, 1, 1), date(2025, 1, 1))

        first = validator.validate(ev_valid, invoice_vendor_id="V-0001").is_valid
        second = validator.validate(ev_valid, invoice_vendor_id="V-0001").is_valid
        assert first == second

        assert validator.validate(ev_valid, invoice_vendor_id="V-0001").is_valid
        assert not validator.validate(ev_expired, invoice_vendor_id="V-0001").is_valid


class TestReferenceRelativeGeneration:
    VENDORS = [f"V-{i:04d}" for i in range(1, 21)]
    CODES = [
        "VENDOR_MISMATCH", "PO_MISMATCH", "AMOUNT_MISMATCH", "GRN_MISMATCH",
        "DUPLICATE_INVOICE", "TAX_ERROR", "CURRENCY_MISMATCH", "LINE_ITEM_MISMATCH",
        "DISCOUNT_ERROR", "CREDIT_ISSUE",
    ]

    def _generate(self, reference_date: date):
        from apx.evidence.generate_evidence import EvidenceCorpusGenerator

        gen = EvidenceCorpusGenerator(seed=42, reference_date=reference_date)
        gen.generate_all(self.VENDORS, self.CODES)
        return gen.evidence

    def test_no_real_evidence_future_dated(self):
        evidence = self._generate(APX_REFERENCE_DATE)
        for ev in evidence:
            if ev.scope in ("irrelevant", "stale_test"):
                continue
            assert ev.effective_from <= APX_REFERENCE_DATE, ev.evidence_id
            assert ev.effective_from <= ev.effective_until

    def test_deliberately_stale_evidence_strictly_in_past(self):
        evidence = self._generate(APX_REFERENCE_DATE)
        for ev in evidence:
            if ev.scope in ("irrelevant", "stale_test"):
                assert ev.effective_until < APX_REFERENCE_DATE, ev.evidence_id

    def test_same_seed_and_reference_reproducible(self):
        a = self._generate(APX_REFERENCE_DATE)
        b = self._generate(APX_REFERENCE_DATE)
        a_data = [e.model_dump(mode="json") for e in a]
        b_data = [e.model_dump(mode="json") for e in b]
        assert a_data == b_data

    def test_reference_shift_keeps_ids_and_content(self):
        a = self._generate(APX_REFERENCE_DATE)
        b = self._generate(date(2026, 1, 15))
        assert [e.evidence_id for e in a] == [e.evidence_id for e in b]
        assert [e.content for e in a] == [e.content for e in b]
        assert any(
            av.effective_from != bv.effective_from for av, bv in zip(a, b)
        ), "dates should shift with the reference date"

    def test_export_records_reference_date(self):
        from apx.evidence.generate_evidence import EvidenceCorpusGenerator

        gen = EvidenceCorpusGenerator(seed=42, reference_date=APX_REFERENCE_DATE)
        gen.generate_all(self.VENDORS, self.CODES)
        exported = gen.export()
        assert exported["reference_date"] == APX_REFERENCE_DATE.isoformat()
        assert exported["generated_at"] == APX_REFERENCE_DATE.isoformat()
        assert len(exported["evidence"]) == 235
