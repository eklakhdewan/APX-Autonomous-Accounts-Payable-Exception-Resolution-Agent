import json
import pytest
from datetime import date
from pathlib import Path

from apx.config.settings import get_settings
from apx.evidence.populate_eval_labels import (
    determine_labels_for_case,
    evidence_matches_exception,
    evidence_applies_to_case,
)
from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority


class TestEvalDataset:
    def test_eval_dataset_has_ground_truth_labels(self):
        settings = get_settings()
        eval_path = settings.get_eval_path() / "eval_dataset.json"
        
        with eval_path.open("r") as f:
            data = json.load(f)
        
        cases = data["cases"]
        assert len(cases) == 10, f"Expected 10 eval cases, got {len(cases)}"
        
        for case in cases:
            # Check required fields exist
            assert "case_id" in case
            assert "exception_type" in case
            assert "vendor_id" in case
            assert "query" in case
            assert "relevant_evidence_ids" in case
            assert "irrelevant_evidence_ids" in case
            assert "invalid_evidence_ids" in case
            
            # Check all three label fields are populated (non-empty lists)
            assert isinstance(case["relevant_evidence_ids"], list)
            assert isinstance(case["irrelevant_evidence_ids"], list)
            assert isinstance(case["invalid_evidence_ids"], list)
            
            # At least one relevant item should exist for meaningful metrics
            assert len(case["relevant_evidence_ids"]) > 0, f"Case {case['case_id']} has no relevant evidence"
            
            # Check no duplicates within each category
            for cat_name in ["relevant_evidence_ids", "irrelevant_evidence_ids", "invalid_evidence_ids"]:
                ids = case[cat_name]
                assert len(ids) == len(set(ids)), f"Duplicate IDs in {cat_name} for {case['case_id']}"
            
            # Check no overlap between categories
            rel = set(case["relevant_evidence_ids"])
            irr = set(case["irrelevant_evidence_ids"])
            inv = set(case["invalid_evidence_ids"])
            assert rel.isdisjoint(irr), f"Overlap between relevant and irrelevant in {case['case_id']}"
            assert rel.isdisjoint(inv), f"Overlap between relevant and invalid in {case['case_id']}"
            assert irr.isdisjoint(inv), f"Overlap between irrelevant and invalid in {case['case_id']}"
    
    def test_eval_dataset_ids_exist_in_corpus(self):
        settings = get_settings()
        corpus_path = settings.get_corpus_path() / "evidence_corpus.json"
        eval_path = settings.get_eval_path() / "eval_dataset.json"
        
        with corpus_path.open("r") as f:
            corpus_data = json.load(f)
        corpus_ids = {e["evidence_id"] for e in corpus_data["evidence"]}
        
        with eval_path.open("r") as f:
            eval_data = json.load(f)
        
        for case in eval_data["cases"]:
            all_ids = (case["relevant_evidence_ids"] + 
                      case["irrelevant_evidence_ids"] + 
                      case["invalid_evidence_ids"])
            for eid in all_ids:
                assert eid in corpus_ids, f"Evidence ID {eid} in {case['case_id']} not found in corpus"
    
    def test_eval_dataset_deterministic(self):
        """Running the populate script twice with same seed produces identical labels."""
        import subprocess
        import os
        import tempfile
        
        env = os.environ.copy()
        env["PATH"] = "/home/eklakhdewan/.local/bin:" + env["PATH"]
        # Set PYTHONHASHSEED for deterministic hash() across processes
        env["PYTHONHASHSEED"] = "42"
        
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            # Run populate script twice
            subprocess.run(
                ["python3", "-m", "apx.evidence.populate_eval_labels", "--output-dir", tmpdir1],
                cwd="/mnt/d/Opencode", capture_output=True, env=env, check=True
            )
            subprocess.run(
                ["python3", "-m", "apx.evidence.populate_eval_labels", "--output-dir", tmpdir2],
                cwd="/mnt/d/Opencode", capture_output=True, env=env, check=True
            )
            
            # Compare outputs
            with open(f"{tmpdir1}/eval_dataset.json") as f1, open(f"{tmpdir2}/eval_dataset.json") as f2:
                data1 = json.load(f1)
                data2 = json.load(f2)
            
            # Cases should be identical
            for c1, c2 in zip(data1["cases"], data2["cases"]):
                assert c1["relevant_evidence_ids"] == c2["relevant_evidence_ids"], f"Relevant IDs differ for {c1['case_id']}"
                assert c1["irrelevant_evidence_ids"] == c2["irrelevant_evidence_ids"], f"Irrelevant IDs differ for {c1['case_id']}"
                assert c1["invalid_evidence_ids"] == c2["invalid_evidence_ids"], f"Invalid IDs differ for {c1['case_id']}"


def test_evaluation_metrics_are_numeric():
    """Verify that evaluation produces numeric metrics, not N/A."""
    from apx.evidence.evaluate import compute_recall_at_k, compute_mrr, compute_ndcg_at_k
    
    relevant = ["EV-001", "EV-002", "EV-003"]
    retrieved = ["EV-002", "EV-004", "EV-001", "EV-005", "EV-003"]
    
    r5 = compute_recall_at_k(relevant, retrieved, 5)
    r10 = compute_recall_at_k(relevant, retrieved, 10)
    mrr = compute_mrr(relevant, retrieved)
    ndcg = compute_ndcg_at_k(relevant, retrieved, 10)
    
    assert isinstance(r5, float) and 0 <= r5 <= 1
    assert isinstance(r10, float) and 0 <= r10 <= 1
    assert isinstance(mrr, float) and 0 <= mrr <= 1
    assert isinstance(ndcg, float) and 0 <= ndcg <= 1
    
    # With perfect retrieval
    perfect_retrieved = ["EV-001", "EV-002", "EV-003", "EV-004"]
    assert compute_recall_at_k(relevant, perfect_retrieved, 10) == 1.0
    assert compute_mrr(relevant, perfect_retrieved) == 1.0
    assert compute_ndcg_at_k(relevant, perfect_retrieved, 10) == 1.0
    
    # With empty relevant
    assert compute_recall_at_k([], retrieved, 5) == 1.0
    assert compute_mrr([], retrieved) == 1.0
    assert compute_ndcg_at_k([], retrieved, 10) == 1.0


def test_historical_resolution_requires_matching_exception_code():
    evidence = {
        "evidence_id": "EV-TEST-1",
        "evidence_type": "historical_resolution",
        "vendor_id": "V-0007",
        "scope": "vendor_exception",
        "effective_from": date(2025, 1, 1),
        "effective_until": date(2026, 12, 31),
        "policy_version": "v1.0",
        "outcome": "AUTO_APPROVED",
        "source_authority": "internal",
        "metadata": {"exception_code": "CURRENCY_MISMATCH"},
        "applicable_exception_types": ["CURRENCY_MISMATCH"],
    }
    assert evidence_matches_exception(evidence, "CURRENCY_MISMATCH") is True
    assert evidence_matches_exception(evidence, "PO_MISMATCH") is False


def test_policy_without_explicit_applicability_is_not_relevant():
    evidence = {
        "evidence_id": "EV-TEST-2",
        "evidence_type": "vendor_policy",
        "vendor_id": "V-0007",
        "scope": "payment_terms",
        "effective_from": date(2025, 1, 1),
        "effective_until": date(2026, 12, 31),
        "policy_version": "v1.0",
        "outcome": "ACTIVE",
        "source_authority": "internal",
        "metadata": {"policy_scope": "payment_terms"},
        "applicable_exception_types": [],
    }
    assert evidence_applies_to_case(evidence, "DISCOUNT_ERROR") is False
    assert evidence_applies_to_case(evidence, "AMOUNT_MISMATCH") is False


def test_contract_without_explicit_applicability_is_not_relevant():
    evidence = {"evidence_type": "contract", "applicable_exception_types": [], "vendor_id": "V-0007"}
    assert evidence_applies_to_case(evidence, "AMOUNT_MISMATCH") is False


def test_payment_term_without_explicit_applicability_is_not_relevant():
    evidence = {"evidence_type": "payment_term", "applicable_exception_types": [], "vendor_id": "V-0007"}
    assert evidence_applies_to_case(evidence, "DISCOUNT_ERROR") is False


def test_explicit_applicability_makes_generic_evidence_relevant():
    evidence = {
        "evidence_id": "EV-TEST-3",
        "evidence_type": "contract",
        "vendor_id": "V-0007",
        "scope": "contractual_terms",
        "effective_from": date(2025, 1, 1),
        "effective_until": date(2026, 12, 31),
        "policy_version": "v1.0",
        "outcome": "ACTIVE",
        "source_authority": "internal",
        "metadata": {"contract_id": "CTR-1"},
        "applicable_exception_types": ["DISCOUNT_ERROR", "AMOUNT_MISMATCH"],
    }
    assert evidence_applies_to_case(evidence, "DISCOUNT_ERROR") is True
    assert evidence_applies_to_case(evidence, "AMOUNT_MISMATCH") is True
    assert evidence_applies_to_case(evidence, "PO_MISMATCH") is False


def test_label_generation_requires_applicability_and_vendor_scope():
    case = {"case_id": "EVAL-TEST", "exception_type": "PO_MISMATCH", "vendor_id": "V-0006"}
    evidence_corpus = {
        "EV-VALID-PO": {
            "evidence_id": "EV-VALID-PO",
            "evidence_type": "historical_resolution",
            "vendor_id": "V-0006",
            "scope": "vendor_exception",
            "effective_from": date(2025, 1, 1),
            "effective_until": date(2026, 12, 31),
            "policy_version": "v1.0",
            "outcome": "AUTO_APPROVED",
            "source_authority": "internal",
            "metadata": {"exception_code": "PO_MISMATCH"},
            "applicable_exception_types": ["PO_MISMATCH"],
        },
        "EV-WRONG-EXCEPTION": {
            "evidence_id": "EV-WRONG-EXCEPTION",
            "evidence_type": "historical_resolution",
            "vendor_id": "V-0006",
            "scope": "vendor_exception",
            "effective_from": date(2025, 1, 1),
            "effective_until": date(2026, 12, 31),
            "policy_version": "v1.0",
            "outcome": "AUTO_APPROVED",
            "source_authority": "internal",
            "metadata": {"exception_code": "LINE_ITEM_MISMATCH"},
            "applicable_exception_types": ["LINE_ITEM_MISMATCH"],
        },
        "EV-OTHER-VENDOR": {
            "evidence_id": "EV-OTHER-VENDOR",
            "evidence_type": "historical_resolution",
            "vendor_id": "V-9999",
            "scope": "vendor_exception",
            "effective_from": date(2025, 1, 1),
            "effective_until": date(2026, 12, 31),
            "policy_version": "v1.0",
            "outcome": "AUTO_APPROVED",
            "source_authority": "internal",
            "metadata": {"exception_code": "PO_MISMATCH"},
            "applicable_exception_types": ["PO_MISMATCH"],
        },
        "EV-STALE": {
            "evidence_id": "EV-STALE",
            "evidence_type": "historical_resolution",
            "vendor_id": "V-0006",
            "scope": "vendor_exception",
            "effective_from": date(2020, 1, 1),
            "effective_until": date(2021, 1, 1),
            "policy_version": "v1.0",
            "outcome": "AUTO_APPROVED",
            "source_authority": "internal",
            "metadata": {"exception_code": "PO_MISMATCH"},
            "applicable_exception_types": ["PO_MISMATCH"],
        },
    }
    relevant, irrelevant, invalid = determine_labels_for_case(case, evidence_corpus, date(2026, 1, 1))
    assert "EV-VALID-PO" in relevant
    assert "EV-WRONG-EXCEPTION" not in relevant
    assert "EV-OTHER-VENDOR" not in relevant
    assert "EV-STALE" not in relevant


def test_wrong_vendor_is_not_relevant():
    evidence = {"evidence_type": "vendor_policy", "vendor_id": "V-9999", "applicable_exception_types": ["PO_MISMATCH"]}
    case = {"case_id": "VENDOR", "vendor_id": "V-0006", "exception_type": "PO_MISMATCH"}
    relevant, _, _ = determine_labels_for_case(case, {"EV": evidence | {
        "effective_from": date(2025, 1, 1), "effective_until": date(2026, 12, 31),
        "policy_version": "v1.0", "outcome": "ACTIVE", "scope": "policy", "source_authority": "internal",
    }}, date(2026, 1, 1))
    assert relevant == []


def test_expired_evidence_is_not_relevant():
    evidence = {"evidence_type": "contract", "vendor_id": "V-0006", "applicable_exception_types": ["PO_MISMATCH"],
                "effective_from": date(2020, 1, 1), "effective_until": date(2021, 1, 1), "policy_version": "v1.0",
                "outcome": "ACTIVE", "scope": "contract", "source_authority": "internal"}
    case = {"case_id": "EXPIRED", "vendor_id": "V-0006", "exception_type": "PO_MISMATCH"}
    _, _, invalid = determine_labels_for_case(case, {"EV": evidence}, date(2026, 1, 1))
    assert invalid == ["EV"]


def test_future_evidence_is_not_relevant():
    evidence = {"evidence_type": "contract", "vendor_id": "V-0006", "applicable_exception_types": ["PO_MISMATCH"],
                "effective_from": date(2027, 1, 1), "effective_until": date(2028, 1, 1), "policy_version": "v1.0",
                "outcome": "ACTIVE", "scope": "contract", "source_authority": "internal"}
    case = {"case_id": "FUTURE", "vendor_id": "V-0006", "exception_type": "PO_MISMATCH"}
    _, _, invalid = determine_labels_for_case(case, {"EV": evidence}, date(2026, 1, 1))
    assert invalid == ["EV"]


def test_wrong_exception_is_not_relevant():
    evidence = {"evidence_type": "contract", "vendor_id": "V-0006", "applicable_exception_types": ["TAX_ERROR"],
                "effective_from": date(2025, 1, 1), "effective_until": date(2026, 12, 31), "policy_version": "v1.0",
                "outcome": "ACTIVE", "scope": "contract", "source_authority": "internal"}
    case = {"case_id": "WRONG", "vendor_id": "V-0006", "exception_type": "PO_MISMATCH"}
    relevant, _, _ = determine_labels_for_case(case, {"EV": evidence}, date(2026, 1, 1))
    assert relevant == []


def test_generated_corpus_populates_exception_applicability_deterministically():
    from apx.evidence.generate_evidence import EvidenceCorpusGenerator

    gen = EvidenceCorpusGenerator(seed=42, reference_date=date(2026, 8, 29))
    gen.generate_all(
        vendors=[f"V-{i:04d}" for i in range(1, 21)],
        exception_codes=[
            "VENDOR_MISMATCH", "PO_MISMATCH", "AMOUNT_MISMATCH", "GRN_MISMATCH",
            "DUPLICATE_INVOICE", "TAX_ERROR", "CURRENCY_MISMATCH", "LINE_ITEM_MISMATCH",
            "DISCOUNT_ERROR", "CREDIT_ISSUE",
        ],
    )

    populated = [e for e in gen.evidence if e.applicable_exception_types]
    assert populated
    assert all(isinstance(e.applicable_exception_types, list) for e in populated)
    assert any(e.evidence_type == "contract" and not e.applicable_exception_types for e in gen.evidence)
    assert any(e.evidence_type == "payment_term" and e.applicable_exception_types for e in gen.evidence)


def test_generated_applicability_is_deterministic():
    from apx.evidence.generate_evidence import EvidenceCorpusGenerator

    kwargs = dict(vendors=[f"V-{i:04d}" for i in range(1, 21)], exception_codes=[
        "AMOUNT_MISMATCH", "GRN_MISMATCH", "VENDOR_MISMATCH", "TAX_ERROR", "CREDIT_ISSUE",
        "PO_MISMATCH", "CURRENCY_MISMATCH", "LINE_ITEM_MISMATCH", "DISCOUNT_ERROR", "DUPLICATE_INVOICE",
    ])
    left = EvidenceCorpusGenerator(seed=42, reference_date=date(2026, 8, 29))
    right = EvidenceCorpusGenerator(seed=42, reference_date=date(2026, 8, 29))
    left.generate_all(**kwargs)
    right.generate_all(**kwargs)
    assert [e.applicable_exception_types for e in left.evidence] == [e.applicable_exception_types for e in right.evidence]


def test_quantity_does_not_infer_grn_or_line_item_applicability():
    evidence = {"evidence_type": "vendor_policy", "content": "Quantity is recorded for reporting.", "applicable_exception_types": []}
    assert evidence_applies_to_case(evidence, "GRN_MISMATCH") is False
    assert evidence_applies_to_case(evidence, "LINE_ITEM_MISMATCH") is False


def test_tax_does_not_infer_tax_error_applicability():
    evidence = {"evidence_type": "contract", "content": "Tax is listed for accounting.", "applicable_exception_types": []}
    assert evidence_applies_to_case(evidence, "TAX_ERROR") is False


def test_every_canonical_exception_has_a_genuine_applicable_template():
    from apx.evidence.generate_evidence import EvidenceCorpusGenerator

    generator = EvidenceCorpusGenerator(seed=42, reference_date=date(2026, 8, 29))
    generator.generate_all(
        vendors=[f"V-{i:04d}" for i in range(1, 21)],
        exception_codes=[code for _, code, _ in generator.SEMANTIC_POLICY_TEMPLATES],
    )
    applicable = {code for evidence in generator.evidence for code in evidence.applicable_exception_types}
    assert applicable >= {code for _, code, _ in generator.SEMANTIC_POLICY_TEMPLATES}


def test_label_generation_has_no_vendor_wide_leakage_from_other_vendors():
    case = {"case_id": "EVAL-LEAK", "exception_type": "CURRENCY_MISMATCH", "vendor_id": "V-0007"}
    evidence_corpus = {
        "EV-REL": {
            "evidence_id": "EV-REL",
            "evidence_type": "historical_resolution",
            "vendor_id": "V-0007",
            "scope": "vendor_exception",
            "effective_from": date(2025, 1, 1),
            "effective_until": date(2026, 12, 31),
            "policy_version": "v1.0",
            "outcome": "AUTO_APPROVED",
            "source_authority": "internal",
            "metadata": {"exception_code": "CURRENCY_MISMATCH"},
            "applicable_exception_types": ["CURRENCY_MISMATCH"],
        },
        "EV-OTHER": {
            "evidence_id": "EV-OTHER",
            "evidence_type": "vendor_policy",
            "vendor_id": "V-9999",
            "scope": "payment_terms",
            "effective_from": date(2025, 1, 1),
            "effective_until": date(2026, 12, 31),
            "policy_version": "v2.0",
            "outcome": "ACTIVE",
            "source_authority": "internal",
            "metadata": {"policy_scope": "payment_terms"},
            "applicable_exception_types": ["DISCOUNT_ERROR"],
        },
    }
    relevant, irrelevant, invalid = determine_labels_for_case(case, evidence_corpus, date(2026, 1, 1))
    assert "EV-REL" in relevant
    assert "EV-OTHER" not in relevant
    assert all(ev["vendor_id"] == "V-0007" for ev in [evidence_corpus[eid] for eid in irrelevant] if eid in evidence_corpus)
    assert "EV-OTHER" not in irrelevant