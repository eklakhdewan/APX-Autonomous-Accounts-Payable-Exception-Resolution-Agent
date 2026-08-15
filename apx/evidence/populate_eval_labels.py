#!/usr/bin/env python3
"""
Populate evaluation dataset with genuine ground-truth labels derived from the evidence corpus.

This script:
1. Loads the evidence corpus and evaluation cases
2. For each eval case, deterministically identifies relevant/irrelevant/invalid evidence
3. Labels are derived independently from the evidence corpus and case intent
4. Does NOT use retrieval results to construct ground truth
"""
import json
import random
import argparse
from datetime import date
from pathlib import Path
from typing import Any
from collections import defaultdict

from apx.config.settings import get_settings
from apx.evidence.schemas import Evidence, EvidenceType, SourceAuthority, ValidityStatus
from apx.data.schemas import ExceptionCode


def load_evidence_corpus(corpus_path: Path) -> dict[str, Any]:
    """Load evidence corpus and return dict of evidence_id -> Evidence."""
    with corpus_path.open("r") as f:
        data = json.load(f)
    result = {}
    for e in data["evidence"]:
        # Parse dates
        parsed = e.copy()
        for key in ("effective_from", "effective_until"):
            if key in parsed and isinstance(parsed[key], str):
                parsed[key] = date.fromisoformat(parsed[key])
        if "usage_count" in parsed and isinstance(parsed["usage_count"], str):
            parsed["usage_count"] = int(parsed["usage_count"])
        if "evidence_type" in parsed and isinstance(parsed["evidence_type"], str):
            parsed["evidence_type"] = parsed["evidence_type"]
        if "source_authority" in parsed and isinstance(parsed["source_authority"], str):
            parsed["source_authority"] = parsed["source_authority"]
        result[parsed["evidence_id"]] = parsed
    return result


def load_eval_dataset(eval_path: Path) -> list[dict[str, Any]]:
    with eval_path.open("r") as f:
        data = json.load(f)
    return data["cases"]


def save_eval_dataset(eval_path: Path, cases: list[dict[str, Any]]):
    with eval_path.open("w") as f:
        json.dump({"cases": cases}, f, indent=2, default=str)


def check_evidence_validity(evidence: dict, invoice_vendor_id: str, reference_date: date) -> tuple[bool, list[str]]:
    """
    Check if evidence is valid per Phase 2 validity rules.
    Returns (is_valid, reasons).
    """
    reasons = []
    is_valid = True

    # 1. Check effective dates
    eff_from = evidence["effective_from"]
    eff_until = evidence["effective_until"]
    if isinstance(eff_from, str):
        eff_from = date.fromisoformat(eff_from)
    if isinstance(eff_until, str):
        eff_until = date.fromisoformat(eff_until)
    
    if eff_from > reference_date:
        reasons.append(f"Evidence not yet effective (effective_from: {eff_from})")
        is_valid = False
    elif eff_until < reference_date:
        reasons.append(f"Evidence expired (effective_until: {eff_until})")
        is_valid = False

    # 2. Check vendor match
    if evidence.get("vendor_id") and evidence["vendor_id"] != invoice_vendor_id:
        reasons.append(f"Vendor mismatch: evidence vendor {evidence['vendor_id']} != invoice vendor {invoice_vendor_id}")
        is_valid = False

    # 3. Check policy version (basic check)
    if evidence.get("policy_version") and evidence["policy_version"].startswith("v0."):
        reasons.append(f"Outdated policy version: {evidence['policy_version']}")
        is_valid = False

    # 4. Check outcome validity
    invalid_outcomes = {"REJECTED", "EXPIRED", "FAILED", "INVALID"}
    if evidence.get("outcome") in invalid_outcomes:
        reasons.append(f"Invalid outcome: {evidence['outcome']}")
        is_valid = False

    # 5. Check source authority (low authority is flagged but doesn't make invalid)
    low_authority = {"external"}
    if evidence.get("source_authority") in low_authority:
        reasons.append(f"Low authority source: {evidence['source_authority']}")

    # 6. Check scope relevance
    if evidence.get("scope") in {"irrelevant", "stale_test"}:
        reasons.append(f"Test/scope flag: {evidence['scope']}")
        is_valid = False

    return is_valid, reasons


def determine_labels_for_case(
    case: dict[str, Any],
    evidence_corpus: dict[str, dict],
    reference_date: date,
) -> tuple[list[str], list[str], list[str]]:
    """
    Determine relevant, irrelevant, and invalid evidence IDs for a case.
    
    Ground truth is derived from the evidence corpus and case intent, NOT from retrieval.
    """
    vendor_id = case["vendor_id"]
    exception_type = case["exception_type"]
    
    # Get all evidence for this vendor
    vendor_evidence = {eid: ev for eid, ev in evidence_corpus.items() if ev.get("vendor_id") == vendor_id}
    other_vendor_evidence = [eid for eid, ev in evidence_corpus.items() if ev.get("vendor_id") != vendor_id]
    
    relevant = set()
    irrelevant = set()
    invalid = set()
    
    # Map exception types to highly-relevant historical resolution codes
    exception_relevance_map = {
        "AMOUNT_MISMATCH": {"AMOUNT_MISMATCH"},
        "GRN_MISMATCH": {"GRN_MISMATCH"},
        "VENDOR_MISMATCH": {"VENDOR_MISMATCH"},
        "TAX_ERROR": {"TAX_ERROR"},
        "CREDIT_ISSUE": {"CREDIT_ISSUE"},
        "PO_MISMATCH": {"PO_MISMATCH"},
        "CURRENCY_MISMATCH": {"CURRENCY_MISMATCH"},
        "LINE_ITEM_MISMATCH": {"LINE_ITEM_MISMATCH"},
        "DISCOUNT_ERROR": {"DISCOUNT_ERROR"},
        "DUPLICATE_INVOICE": {"DUPLICATE_INVOICE"},
    }
    
    highly_relevant_codes = exception_relevance_map.get(exception_type, set())
    
    for eid, ev in vendor_evidence.items():
        # Determine validity
        is_valid, reasons = check_evidence_validity(ev, case["vendor_id"], reference_date)
        
        if not is_valid:
            invalid.add(eid)
        else:
            # Determine relevance level
            is_highly_relevant = False
            is_relevant = False
            
            if ev["evidence_type"] == "historical_resolution" and ev["scope"] == "vendor_exception":
                meta_exception = ev.get("metadata", {}).get("exception_code")
                if meta_exception in highly_relevant_codes:
                    is_highly_relevant = True
                else:
                    # Other historical resolutions show vendor's resolution patterns
                    is_relevant = True
                    
            elif ev["evidence_type"] == "vendor_policy":
                # All vendor policies are relevant for understanding vendor's policies
                is_relevant = True
                    
            elif ev["evidence_type"] == "contract":
                if ev["scope"] == "contractual_terms":
                    is_relevant = True
                elif ev["scope"] == "stale_test":
                    # Stale test contracts are invalid (already caught)
                    pass
                else:
                    # Other contract scopes
                    is_relevant = True
                    
            elif ev["evidence_type"] == "payment_term":
                if ev["scope"] == "payment_terms":
                    is_relevant = True
                elif ev["scope"] == "stale_test":
                    # Stale test payment terms are invalid (already caught)
                    pass
                else:
                    is_relevant = True
            
            if is_highly_relevant or is_relevant:
                relevant.add(eid)
            else:
                irrelevant.add(eid)
    
    # Cross-vendor evidence is irrelevant (simulates retrieval noise)
    rng = random.Random(hash(case["case_id"]) % (2**32))
    other_vendor_evidence = [eid for eid, ev in evidence_corpus.items() if ev.get("vendor_id") != case["vendor_id"]]
    other_irrelevant = rng.sample(other_vendor_evidence, min(10, len(other_vendor_evidence)))
    irrelevant.update(other_irrelevant)
    
    # Also add test noise evidence (scope=irrelevant) as irrelevant
    test_noise_evidence = [eid for eid, ev in evidence_corpus.items() if ev.get("scope") == "irrelevant" and ev.get("vendor_id") is None]
    rng2 = random.Random((hash(case["case_id"]) + 1) % (2**32))
    irrelevant.update(rng2.sample(test_noise_evidence, min(5, len(test_noise_evidence))))
    
    # Convert to sorted lists
    return sorted(relevant), sorted(irrelevant), sorted(invalid)


class EvalDatasetGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.settings = get_settings()
        self.reference_date = date(2025, 12, 1)

    def generate(self, output_dir: Path | None = None):
        eval_dir = output_dir or self.settings.get_eval_path()
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Load evidence corpus
        corpus_path = self.settings.get_corpus_path() / "evidence_corpus.json"
        with open(corpus_path, "r") as f:
            evidence_data = json.load(f)["evidence"]

        # Load evaluation cases
        eval_path = self.settings.get_eval_path() / "eval_dataset.json"
        with open(eval_path, "r") as f:
            cases = json.load(f)["cases"]

        # Build evidence corpus dict for validity checking
        evidence_corpus = {}
        for e in evidence_data:
            parsed = e.copy()
            for key in ("effective_from", "effective_until"):
                if key in parsed and isinstance(parsed[key], str):
                    parsed[key] = date.fromisoformat(parsed[key])
            if "usage_count" in parsed and isinstance(parsed["usage_count"], str):
                parsed["usage_count"] = int(parsed["usage_count"])
            if "evidence_type" in parsed and isinstance(parsed["evidence_type"], str):
                parsed["evidence_type"] = parsed["evidence_type"]
            if "source_authority" in parsed and isinstance(parsed["source_authority"], str):
                parsed["source_authority"] = parsed["source_authority"]
            evidence_corpus[parsed["evidence_id"]] = parsed

        print(f"Loaded {len(evidence_corpus)} evidence records")
        print(f"Loaded {len(cases)} evaluation cases")

        for case in cases:
            print(f"\nLabeling {case['case_id']}: {case['exception_type']} for {case['vendor_id']}")

            relevant, irrelevant, invalid = determine_labels_for_case(case, evidence_corpus, self.reference_date)

            # Verify all IDs exist
            all_ids = relevant + irrelevant + invalid
            evidence_ids = set(evidence_corpus.keys())
            missing = [eid for eid in all_ids if eid not in evidence_ids]
            if missing:
                raise ValueError(f"Missing evidence IDs: {missing}")

            # Check for duplicates within each category
            for cat_name, cat_ids in [("relevant", relevant), ("irrelevant", irrelevant), ("invalid", invalid)]:
                if len(cat_ids) != len(set(cat_ids)):
                    raise ValueError(f"Duplicate IDs in {cat_name}: {cat_ids}")

            case["relevant_evidence_ids"] = relevant
            case["irrelevant_evidence_ids"] = irrelevant
            case["invalid_evidence_ids"] = invalid

            print(f"  Relevant: {len(relevant)}, Irrelevant: {len(irrelevant)}, Invalid: {len(invalid)}")

        # Save
        eval_dir = output_dir or self.settings.get_eval_path()
        eval_dir.mkdir(parents=True, exist_ok=True)
        eval_file = eval_dir / "eval_dataset.json"
        with open(eval_file, "w") as f:
            json.dump({"cases": cases}, f, indent=2, default=str)
        print(f"\nSaved labeled evaluation dataset to {eval_file}")


def main():
    parser = argparse.ArgumentParser(description="Populate evaluation dataset with ground-truth labels")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output-dir", type=str, help="Output directory (default: apx/data/datasets/eval)")
    args = parser.parse_args()

    generator = EvalDatasetGenerator(seed=args.seed)
    if args.output_dir:
        generator.generate(Path(args.output_dir))
    else:
        generator.generate()


if __name__ == "__main__":
    main()