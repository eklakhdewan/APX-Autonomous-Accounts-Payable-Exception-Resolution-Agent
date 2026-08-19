from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import math

from apx.evidence.schemas import EvidenceSet, ValidatedEvidence, EvidenceType, ValidityStatus


@dataclass
class RetrievalResult:
    """Result of retrieval evaluation."""
    total_queries: int = 0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    per_query: List[Dict[str, Any]] = field(default_factory=list)
    valid_evidence_rate: float = 0.0
    invalid_evidence_rejection_rate: float = 0.0
    vendor_scope_correctness: float = 0.0


class RetrievalEvaluator:
    """
    Evaluates the Phase 2 retrieval system.

    Required metrics: Recall@5, Recall@10, MRR, nDCG@10.
    Uses explicit relevance labels distinguishing relevant/irrelevant/invalid evidence.
    """

    def __init__(self):
        pass

    def evaluate(
        self,
        evidence_set: EvidenceSet,
        relevant_ids: Set[str],
        irrelevant_ids: Set[str],
        invalid_ids: Set[str],
        k_values: List[int] = None,
    ) -> RetrievalResult:
        """Evaluate a single evidence set retrieval."""
        if k_values is None:
            k_values = [5, 10]

        candidates = evidence_set.candidates
        if not candidates:
            return RetrievalResult()

        # Map candidate to relevance
        relevance_map = {}
        for c in candidates:
            eid = c.evidence.evidence_id
            if eid in relevant_ids:
                relevance_map[eid] = 1.0
            elif eid in invalid_ids:
                relevance_map[eid] = 0.0  # Invalid evidence gets 0 relevance
            else:
                relevance_map[eid] = 0.0  # Irrelevant also 0

        # Compute metrics
        recall_at_k = {}
        for k in k_values:
            top_k = candidates[:k]
            relevant_in_top_k = sum(1 for c in top_k if relevance_map.get(c.evidence.evidence_id, 0) > 0)
            total_relevant = len(relevant_ids)
            recall_at_k[k] = relevant_in_top_k / total_relevant if total_relevant > 0 else 0.0

        # MRR - Mean Reciprocal Rank
        mrr = 0.0
        for rank, c in enumerate(candidates, 1):
            if relevance_map.get(c.evidence.evidence_id, 0) > 0:
                mrr = 1.0 / rank
                break

        # nDCG@10
        ndcg_at_10 = self._compute_ndcg(candidates, relevance_map, 10)

        # Valid evidence rate
        valid_count = sum(1 for c in candidates if c.evidence.evidence_id in relevant_ids)
        total_candidates = len(candidates)
        valid_evidence_rate = valid_count / total_candidates if total_candidates > 0 else 0.0

        # Invalid evidence rejection rate
        invalid_in_results = sum(1 for c in candidates if c.evidence.evidence_id in invalid_ids)
        total_invalid = len(invalid_ids)
        invalid_evidence_rejection_rate = 1.0 - (invalid_in_results / total_invalid) if total_invalid > 0 else 1.0

        # Vendor scope correctness
        # This requires invoice/vendor context
        vendor_correct = sum(1 for c in candidates if c.evidence.vendor_id == evidence_set.vendor_id)
        vendor_scope_correctness = vendor_correct / total_candidates if total_candidates > 0 else 0.0

        return RetrievalResult(
            total_queries=1,
            recall_at_5=recall_at_k.get(5, 0.0),
            recall_at_10=recall_at_k.get(10, 0.0),
            mrr=mrr,
            ndcg_at_10=ndcg_at_10,
            per_query=[{
                "query_id": evidence_set.invoice_id,
                "recall_at_5": recall_at_k.get(5, 0.0),
                "recall_at_10": recall_at_k.get(10, 0.0),
                "mrr": mrr,
                "ndcg_at_10": ndcg_at_10,
                "valid_count": valid_count,
                "invalid_count": invalid_in_results,
            }],
            valid_evidence_rate=valid_evidence_rate,
            invalid_evidence_rejection_rate=invalid_evidence_rejection_rate,
            vendor_scope_correctness=vendor_scope_correctness,
        )

    def evaluate_batch(
        self,
        evidence_sets: List[EvidenceSet],
        relevance_labels: Dict[str, Dict[str, Set[str]]],  # invoice_id -> {relevant, irrelevant, invalid}
    ) -> RetrievalResult:
        """Evaluate multiple evidence sets."""
        if not evidence_sets:
            return RetrievalResult()

        all_recall_5 = []
        all_recall_10 = []
        all_mrr = []
        all_ndcg = []
        all_valid_rate = []
        all_invalid_rej = []
        all_vendor_scope = []
        per_query = []

        for es in evidence_sets:
            labels = relevance_labels.get(es.invoice_id, {})
            relevant = labels.get("relevant", set())
            irrelevant = labels.get("irrelevant", set())
            invalid = labels.get("invalid", set())

            result = self.evaluate(es, relevant, irrelevant, invalid)

            all_recall_5.append(result.recall_at_5)
            all_recall_10.append(result.recall_at_10)
            all_mrr.append(result.mrr)
            all_ndcg.append(result.ndcg_at_10)
            all_valid_rate.append(result.valid_evidence_rate)
            all_invalid_rej.append(result.invalid_evidence_rejection_rate)
            all_vendor_scope.append(result.vendor_scope_correctness)
            per_query.extend(result.per_query)

        return RetrievalResult(
            total_queries=len(evidence_sets),
            recall_at_5=sum(all_recall_5) / len(all_recall_5) if all_recall_5 else 0.0,
            recall_at_10=sum(all_recall_10) / len(all_recall_10) if all_recall_10 else 0.0,
            mrr=sum(all_mrr) / len(all_mrr) if all_mrr else 0.0,
            ndcg_at_10=sum(all_ndcg) / len(all_ndcg) if all_ndcg else 0.0,
            per_query=per_query,
            valid_evidence_rate=sum(all_valid_rate) / len(all_valid_rate) if all_valid_rate else 0.0,
            invalid_evidence_rejection_rate=sum(all_invalid_rej) / len(all_invalid_rej) if all_invalid_rej else 0.0,
            vendor_scope_correctness=sum(all_vendor_scope) / len(all_vendor_scope) if all_vendor_scope else 0.0,
        )

    def _compute_ndcg(
        self,
        candidates: List[Any],
        relevance_map: Dict[str, float],
        k: int = 10,
    ) -> float:
        """Compute nDCG@k."""
        top_k = candidates[:k]

        # DCG
        dcg = 0.0
        for i, c in enumerate(top_k):
            rel = relevance_map.get(c.evidence.evidence_id, 0.0)
            if i == 0:
                dcg += rel
            else:
                dcg += rel / math.log2(i + 1)

        # IDCG - ideal DCG
        ideal_rels = sorted(relevance_map.values(), reverse=True)[:k]
        idcg = 0.0
        for i, rel in enumerate(ideal_rels):
            if i == 0:
                idcg += rel
            else:
                idcg += rel / math.log2(i + 1)

        return dcg / idcg if idcg > 0 else 0.0


import math