from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import CrossEncoder

from apx.config.settings import get_settings
from apx.evidence.schemas import RetrievedCandidate


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: str = "cpu",
        top_k: int = 20,
        batch_size: int = 16,
        max_seq_length: int = 512,
        local_files_only: bool = False,
    ):
        self.model_name = model_name
        self.device = device
        self.top_k = top_k
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self.local_files_only = local_files_only
        self.settings = get_settings()
        self.model: CrossEncoder | None = None

    def _load_model(self):
        if self.model is None:
            print(f"Loading cross-encoder model: {self.model_name}...")
            self.model = CrossEncoder(self.model_name, device=self.device, max_length=self.max_seq_length, local_files_only=self.local_files_only)
            print(f"Cross-encoder model loaded")

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedCandidate],
        top_k: int | None = None,
    ) -> list[RetrievedCandidate]:
        if not candidates:
            return []

        self._load_model()

        k = top_k or self.top_k
        k = min(k, len(candidates))

        # Prepare query-document pairs
        pairs = [(query, candidate.evidence.content) for candidate in candidates[:k]]

        # Get reranker scores
        scores = self.model.predict(pairs, batch_size=self.batch_size, show_progress_bar=False)

        # Create reranked candidates
        reranked = []
        for rank, (candidate, score) in enumerate(
            sorted(zip(candidates[:k], scores), key=lambda x: x[1], reverse=True)
        ):
            reranked_candidate = RetrievedCandidate(
                evidence=candidate.evidence,
                bm25_score=candidate.bm25_score,
                bm25_rank=candidate.bm25_rank,
                dense_score=candidate.dense_score,
                dense_rank=candidate.dense_rank,
                rrf_score=candidate.rrf_score,
                rrf_rank=candidate.rrf_rank,
                reranker_score=float(score),
                final_rank=rank + 1,
                retrieval_sources=list(set(candidate.retrieval_sources + ["Reranker"])),
            )
            reranked.append(reranked_candidate)

        return reranked