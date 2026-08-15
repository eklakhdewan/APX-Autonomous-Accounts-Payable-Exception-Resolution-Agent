from __future__ import annotations

from collections import defaultdict
from typing import Any

from apx.evidence.schemas import RetrievedCandidate


def rrf_fuse(
    bm25_candidates: list[RetrievedCandidate],
    dense_candidates: list[RetrievedCandidate],
    k: int = 60,
    rrf_constant: int = 60,
) -> list[RetrievedCandidate]:
    scores = defaultdict(float)
    evidence_map: dict[str, RetrievedCandidate] = {}

    # Process BM25 candidates
    for candidate in bm25_candidates:
        evidence_id = candidate.evidence.evidence_id
        evidence_map[evidence_id] = candidate
        rank = candidate.bm25_rank or 0
        if rank > 0:
            scores[evidence_id] += 1.0 / (rrf_constant + rank)

    # Process dense candidates
    for candidate in dense_candidates:
        evidence_id = candidate.evidence.evidence_id
        if evidence_id not in evidence_map:
            evidence_map[evidence_id] = candidate
        rank = candidate.dense_rank or 0
        if rank > 0:
            scores[evidence_id] += 1.0 / (rrf_constant + rank)

    # Create fused candidates
    fused = []
    for evidence_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        candidate = evidence_map[evidence_id]
        fused_candidate = RetrievedCandidate(
            evidence=candidate.evidence,
            bm25_score=candidate.bm25_score,
            bm25_rank=candidate.bm25_rank,
            dense_score=candidate.dense_score,
            dense_rank=candidate.dense_rank,
            rrf_score=score,
            rrf_rank=len(fused) + 1,
            retrieval_sources=list(set(candidate.retrieval_sources)),
        )
        fused.append(fused_candidate)

    return fused