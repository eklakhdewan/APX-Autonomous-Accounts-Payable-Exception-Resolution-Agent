#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

from apx.config.settings import get_settings
from apx.evidence.schemas import (
    Evidence,
    EvidenceType,
    SourceAuthority,
)
from apx.data.schemas import ExceptionCode


class EvalDatasetGenerator:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.settings = get_settings()

    def generate(self, output_dir: Path | None = None):
        import random

        eval_dir = output_dir or self.settings.get_eval_path()
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Generate evaluation cases with known relevant/irrelevant/invalid evidence
        eval_cases = []

        # Case 1: AMOUNT_MISMATCH for V-0001
        eval_cases.append({
            "case_id": "EVAL-001",
            "exception_type": ExceptionCode.AMOUNT_MISMATCH.value,
            "vendor_id": "V-0001",
            "query": "amount mismatch vendor V-0001 invoice validation price variance total variance",
            "relevant_evidence_ids": [],  # Will be populated after corpus generation
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 2: GRN_MISMATCH for V-0002
        eval_cases.append({
            "case_id": "EVAL-002",
            "exception_type": ExceptionCode.GRN_MISMATCH.value,
            "vendor_id": "V-0002",
            "query": "goods receipt mismatch vendor V-0002 quantity variance receipt quantity GRN quantity",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 3: VENDOR_MISMATCH for V-0003
        eval_cases.append({
            "case_id": "EVAL-003",
            "exception_type": ExceptionCode.VENDOR_MISMATCH.value,
            "vendor_id": "V-0003",
            "query": "vendor mismatch vendor V-0003 vendor validation supplier mismatch vendor verification",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 4: TAX_ERROR for V-0004
        eval_cases.append({
            "case_id": "EVAL-004",
            "exception_type": ExceptionCode.TAX_ERROR.value,
            "vendor_id": "V-0004",
            "query": "tax error vendor V-0004 tax calculation tax validation tax variance tax rate",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 5: CREDIT_ISSUE for V-0005
        eval_cases.append({
            "case_id": "EVAL-005",
            "exception_type": ExceptionCode.CREDIT_ISSUE.value,
            "vendor_id": "V-0005",
            "query": "credit issue vendor V-0005 credit hold credit status vendor credit credit limit",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 6: PO_MISMATCH for V-0006
        eval_cases.append({
            "case_id": "EVAL-006",
            "exception_type": ExceptionCode.PO_MISMATCH.value,
            "vendor_id": "V-0006",
            "query": "purchase order mismatch vendor V-0006 PO validation PO reference purchase order number",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 7: CURRENCY_MISMATCH for V-0007
        eval_cases.append({
            "case_id": "EVAL-007",
            "exception_type": ExceptionCode.CURRENCY_MISMATCH.value,
            "vendor_id": "V-0007",
            "query": "currency mismatch vendor V-0007 currency validation foreign currency exchange rate",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 8: LINE_ITEM_MISMATCH for V-0008
        eval_cases.append({
            "case_id": "EVAL-008",
            "exception_type": ExceptionCode.LINE_ITEM_MISMATCH.value,
            "vendor_id": "V-0008",
            "query": "line item mismatch vendor V-0008 line item variance item price item quantity PO line matching",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 9: DISCOUNT_ERROR for V-0009
        eval_cases.append({
            "case_id": "EVAL-009",
            "exception_type": ExceptionCode.DISCOUNT_ERROR.value,
            "vendor_id": "V-0009",
            "query": "discount error vendor V-0009 discount validation early payment discount discount terms",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Case 10: DUPLICATE_INVOICE for V-0010
        eval_cases.append({
            "case_id": "EVAL-010",
            "exception_type": ExceptionCode.DUPLICATE_INVOICE.value,
            "vendor_id": "V-0010",
            "query": "duplicate invoice vendor V-0010 duplicate detection invoice duplication duplicate prevention",
            "relevant_evidence_ids": [],
            "irrelevant_evidence_ids": [],
            "invalid_evidence_ids": [],
        })

        # Save evaluation dataset
        eval_file = eval_dir / "eval_dataset.json"
        with eval_file.open("w") as f:
            json.dump({"cases": eval_cases}, f, indent=2, default=str)

        print(f"Generated {len(eval_cases)} evaluation cases to {eval_file}")


def main():
    import random

    parser = argparse.ArgumentParser(description="Generate Phase 2 evaluation dataset")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    args = parser.parse_args()

    generator = EvalDatasetGenerator(seed=args.seed)
    if args.output_dir:
        generator.generate(Path(args.output_dir))
    else:
        generator.generate()


if __name__ == "__main__":
    main()