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
import argparse
from datetime import date
from pathlib import Path
from typing import Any

from apx.config.settings import get_settings
from apx.evidence.dates import APX_REFERENCE_DATE
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


def _normalise_exception_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.upper()] if value else []
    items = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip().upper()
        if text:
            items.append(text)
    return list(dict.fromkeys(items))


def evidence_matches_exception(evidence: dict[str, Any], exception_type: str) -> bool:
    metadata_exception = evidence.get("metadata", {}).get("exception_code")
    if metadata_exception:
        return str(metadata_exception).upper() == str(exception_type).upper()
    applicable = _normalise_exception_list(evidence.get("applicable_exception_types", []))
    return str(exception_type).upper() in applicable


def evidence_applies_to_case(evidence: dict[str, Any], case_exception_type: str) -> bool:
    if evidence.get("evidence_type") == "historical_resolution":
        return evidence_matches_exception(evidence, case_exception_type)

    applicable = _normalise_exception_list(evidence.get("applicable_exception_types", []))
    if not applicable:
        return False
    return str(case_exception_type).upper() in applicable


def determine_labels_for_case(
    case: dict[str, Any],
    evidence_corpus: dict[str, dict],
    reference_date: date,
) -> tuple[list[str], list[str], list[str]]:
    """
    Determine relevant, irrelevant, and invalid evidence IDs for a case.

    Ground truth is deterministic and requires temporal validity, correct vendor/scope,
    and explicit exception applicability. It intentionally does not use retrieval rankings
    or any randomized sampling.
    """
    vendor_id = case["vendor_id"]
    exception_type = case["exception_type"]

    relevant = set()
    irrelevant = set()
    invalid = set()

    for eid, ev in sorted(evidence_corpus.items()):
        is_valid, _ = check_evidence_validity(ev, vendor_id, reference_date)

        if not is_valid:
            invalid.add(eid)
            continue

        if ev.get("vendor_id") and ev["vendor_id"] != vendor_id:
            irrelevant.add(eid)
            continue

        if ev.get("evidence_type") == "historical_resolution":
            is_relevant = evidence_matches_exception(ev, exception_type)
        else:
            is_relevant = evidence_applies_to_case(ev, exception_type)

        if is_relevant:
            relevant.add(eid)
        else:
            irrelevant.add(eid)

    return sorted(relevant), sorted(irrelevant), sorted(invalid)


class EvalDatasetGenerator:
    def __init__(self, seed: int = 42, reference_date: date | None = None):
        self.seed = seed
        self.settings = get_settings()
        self.reference_date = reference_date or APX_REFERENCE_DATE

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
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=APX_REFERENCE_DATE,
        help=f"Temporal anchor for evidence validity (default: {APX_REFERENCE_DATE.isoformat()})",
    )
    parser.add_argument("--output-dir", type=str, help="Output directory (default: apx/data/datasets/eval)")
    args = parser.parse_args()

    generator = EvalDatasetGenerator(seed=args.seed, reference_date=args.reference_date)
    if args.output_dir:
        generator.generate(Path(args.output_dir))
    else:
        generator.generate()


if __name__ == "__main__":
    main()