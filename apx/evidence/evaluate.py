#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from apx.config.settings import get_settings
from apx.data.schemas import ExceptionReport, ExceptionCode, ExceptionSeverity, APException, ValidationStatus
from apx.evidence.dates import APX_REFERENCE_DATE
from apx.evidence.engine import HybridContextEngine
from apx.evidence.schemas import Evidence, EvidenceSet, ValidityStatus


def load_evidence_corpus(corpus_path: Path) -> dict[str, Evidence]:
    with corpus_path.open("r") as f:
        data = json.load(f)
    return {e["evidence_id"]: Evidence.model_construct(**e) for e in data["evidence"]}


def load_eval_dataset(eval_path: Path) -> list[dict[str, Any]]:
    with eval_path.open("r") as f:
        data = json.load(f)
    return data["cases"]


def compute_recall_at_k(relevant: list[str], retrieved: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    retrieved_k = retrieved[:k]
    hits = sum(1 for eid in retrieved_k if eid in relevant)
    return hits / len(relevant)


def compute_mrr(relevant: list[str], retrieved: list[str]) -> float:
    if not relevant:
        return 1.0
    for i, eid in enumerate(retrieved, 1):
        if eid in relevant:
            return 1.0 / i
    return 0.0


def compute_ndcg_at_k(relevant: list[str], retrieved: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    retrieved_k = retrieved[:k]
    
    # DCG
    dcg = 0.0
    for i, eid in enumerate(retrieved_k, 1):
        rel = 1.0 if eid in relevant else 0.0
        if i == 1:
            dcg += rel
        else:
            dcg += rel / np.log2(i + 1)
    
    # IDCG
    ideal_retrieved = relevant[:k]
    idcg = 0.0
    for i, eid in enumerate(ideal_retrieved, 1):
        if i == 1:
            idcg += 1.0
        else:
            idcg += 1.0 / np.log2(i + 1)
    
    return dcg / idcg if idcg > 0 else 0.0


def run_evaluation():
    settings = get_settings()
    corpus_path = settings.get_corpus_path() / "evidence_corpus.json"
    eval_path = settings.get_eval_path() / "eval_dataset.json"

    print("Loading evidence corpus...")
    evidence_map = load_evidence_corpus(corpus_path)
    print(f"Loaded {len(evidence_map)} evidence records")

    print("Loading evaluation dataset...")
    eval_cases = load_eval_dataset(eval_path)
    print(f"Loaded {len(eval_cases)} evaluation cases")

    # Initialize engine - reference date must match the corpus validity anchor
    print("Initializing HybridContextEngine (DEV profile)...")
    engine = HybridContextEngine(profile_name="DEV", reference_date=APX_REFERENCE_DATE)

    all_results = []
    
    for case in eval_cases:
        print(f"\nEvaluating {case['case_id']}: {case['exception_type']} for {case['vendor_id']}")
        
        # Ground truth labels
        gt_relevant = set(case.get("relevant_evidence_ids", []))
        gt_irrelevant = set(case.get("irrelevant_evidence_ids", []))
        gt_invalid = set(case.get("invalid_evidence_ids", []))
        
        # Create exception report
        report = ExceptionReport(
            invoice_id=f"INV-{case['case_id']}",
            vendor_id=case['vendor_id'],
            exceptions=[
                APException(
                    exception_code=ExceptionCode(case['exception_type']),
                    severity=ExceptionSeverity.MEDIUM,
                    message=f"Test {case['exception_type']}",
                    details={},
                ),
            ],
            validation_status=ValidationStatus.EXCEPTIONS,
        )
        
        # Run retrieval
        start_time = time.time()
        result: EvidenceSet = engine.retrieve(report)
        latency = time.time() - start_time
        
        # Retrieved evidence IDs in ranked order
        retrieved_ids = [e.evidence.evidence_id for e in result.validated_evidence]
        
        # Valid vs invalid from engine
        valid_ids = set(e.evidence.evidence_id for e in result.validated_evidence if e.validity_status == ValidityStatus.VALID)
        invalid_ids = set(e.evidence.evidence_id for e in result.validated_evidence if e.validity_status != ValidityStatus.VALID)
        
        # Compute metrics against ground truth
        # Recall@K: fraction of ground-truth relevant items retrieved in top-K
        recall_5 = compute_recall_at_k(list(gt_relevant), retrieved_ids, 5)
        recall_10 = compute_recall_at_k(list(gt_relevant), retrieved_ids, 10)
        mrr = compute_mrr(list(gt_relevant), retrieved_ids)
        ndcg_10 = compute_ndcg_at_k(list(gt_relevant), retrieved_ids, 10)
        
        # Invalid evidence rejection rate (engine should mark invalid items as invalid)
        invalid_rejection_rate = len(invalid_ids & gt_invalid) / len(gt_invalid) if gt_invalid else 1.0
        
        # Vendor-scope correctness: fraction of retrieved items that belong to the correct vendor
        vendor_scope_correct = sum(1 for e in result.validated_evidence 
                                    if e.evidence.vendor_id is None or e.evidence.vendor_id == case['vendor_id']) / len(result.validated_evidence) if result.validated_evidence else 1.0
        
        # Valid evidence rate
        valid_rate = len(valid_ids) / len(retrieved_ids) if retrieved_ids else 0
        
        case_result = {
            "case_id": case["case_id"],
            "exception_type": case["exception_type"],
            "vendor_id": case["vendor_id"],
            "total_retrieved": len(retrieved_ids),
            "valid_count": len(valid_ids),
            "invalid_count": len(invalid_ids),
            "recall_5": recall_5,
            "recall_10": recall_10,
            "mrr": mrr,
            "ndcg_10": ndcg_10,
            "invalid_rejection_rate": invalid_rejection_rate,
            "vendor_scope_correct": vendor_scope_correct,
            "valid_rate": valid_rate,
            "latency_seconds": latency,
            "retrieved_ids": retrieved_ids,
            "gt_relevant": list(gt_relevant),
            "gt_irrelevant": list(gt_irrelevant),
            "gt_invalid": list(gt_invalid),
        }
        
        all_results.append(case_result)
        
        print(f"  Total: {case_result['total_retrieved']}, Valid: {case_result['valid_count']}, Invalid: {case_result['invalid_count']}")
        print(f"  Recall@5: {case_result['recall_5']:.4f}, Recall@10: {case_result['recall_10']:.4f}")
        print(f"  MRR: {case_result['mrr']:.4f}, nDCG@10: {case_result['ndcg_10']:.4f}")
        print(f"  Invalid rejection: {case_result['invalid_rejection_rate']:.2%}")
        print(f"  Vendor-scope: {case_result['vendor_scope_correct']:.2%}")
        print(f"  Latency: {case_result['latency_seconds']:.2f}s")

    # Aggregate metrics
    avg_recall_5 = np.mean([r["recall_5"] for r in all_results])
    avg_recall_10 = np.mean([r["recall_10"] for r in all_results])
    avg_mrr = np.mean([r["mrr"] for r in all_results])
    avg_ndcg_10 = np.mean([r["ndcg_10"] for r in all_results])
    avg_invalid_rejection = np.mean([r["invalid_rejection_rate"] for r in all_results])
    avg_vendor_scope = np.mean([r["vendor_scope_correct"] for r in all_results])
    avg_valid_rate = np.mean([r["valid_rate"] for r in all_results])
    avg_latency = np.mean([r["latency_seconds"] for r in all_results])

    print("\n" + "="*60)
    print("PHASE 2 RETRIEVAL EVALUATION RESULTS")
    print("="*60)
    print(f"Evaluation cases: {len(all_results)}")
    print(f"Corpus size: {len(evidence_map)}")
    print(f"Profile: DEV (bge-small-en-v1.5 + bge-reranker-base)")
    print(f"Reference date: {APX_REFERENCE_DATE.isoformat()}")
    print()
    print("Per-case results:")
    for r in all_results:
        print(f"  {r['case_id']}: R@5={r['recall_5']:.4f}, R@10={r['recall_10']:.4f}, "
              f"MRR={r['mrr']:.4f}, nDCG@10={r['ndcg_10']:.4f}, "
              f"invalid_rej={r['invalid_rejection_rate']:.2%}, "
              f"vendor_scope={r['vendor_scope_correct']:.2%}, latency={r['latency_seconds']:.2f}s")
    print()
    print("Aggregate metrics:")
    print(f"  Recall@5: {avg_recall_5:.4f}")
    print(f"  Recall@10: {avg_recall_10:.4f}")
    print(f"  MRR: {avg_mrr:.4f}")
    print(f"  nDCG@10: {avg_ndcg_10:.4f}")
    print(f"  Invalid-evidence rejection rate: {avg_invalid_rejection:.2%}")
    print(f"  Vendor-scope correctness: {avg_vendor_scope:.2%}")
    print(f"  Valid evidence rate: {avg_valid_rate:.2%}")
    print(f"  Avg retrieval latency: {avg_latency:.2f}s")
    print()
    print("Ground truth methodology:")
    print("  - Relevant: Valid evidence for the case vendor (vendor policies, contracts, payment terms, historical resolutions)")
    print("  - Irrelevant: Cross-vendor evidence + test noise (scope=irrelevant)")
    print("  - Invalid: Evidence failing validity checks (expired, stale_test, wrong vendor, rejected outcome, outdated policy)")
    print("  - Ground truth derived independently from evidence corpus, NOT from retrieval output")
    print()

    return all_results


if __name__ == "__main__":
    run_evaluation()