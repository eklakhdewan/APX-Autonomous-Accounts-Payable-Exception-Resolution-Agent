from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from apx.config.settings import get_settings
from apx.evidence.schemas import Evidence, RetrievedCandidate


def _parse_evidence_data(data: dict) -> dict:
    """Parse evidence data, converting date strings to date objects and enums."""
    from apx.evidence.schemas import EvidenceType, SourceAuthority, ValidityStatus
    parsed = data.copy()
    for key in ("effective_from", "effective_until"):
        if key in parsed and isinstance(parsed[key], str):
            parsed[key] = date.fromisoformat(parsed[key])
    if "usage_count" in parsed and isinstance(parsed["usage_count"], str):
        parsed["usage_count"] = int(parsed["usage_count"])
    if "evidence_type" in parsed and isinstance(parsed["evidence_type"], str):
        parsed["evidence_type"] = EvidenceType(parsed["evidence_type"])
    if "source_authority" in parsed and isinstance(parsed["source_authority"], str):
        parsed["source_authority"] = SourceAuthority(parsed["source_authority"])
    if "validity_status" in parsed and isinstance(parsed["validity_status"], str):
        parsed["validity_status"] = ValidityStatus(parsed["validity_status"])
    return parsed


class BM25Retriever:
    def __init__(self, top_k: int = 50, corpus_path: Path | None = None, index_cache_path: Path | None = None):
        self.top_k = top_k
        self.settings = get_settings()
        self.corpus_path = corpus_path or self.settings.get_corpus_path()
        self.index_cache_path = index_cache_path or self.settings.get_index_cache_path()
        self.bm25: BM25Okapi | None = None
        self.evidence_corpus: list[Evidence] = []
        self.tokenized_corpus: list[list[str]] = []

    def load_corpus(self) -> list[Evidence]:
        corpus_file = self.corpus_path / "evidence_corpus.json"
        if not corpus_file.exists():
            raise FileNotFoundError(f"Evidence corpus not found at {corpus_file}")
        with corpus_file.open("r") as f:
            data = json.load(f)
        self.evidence_corpus = [Evidence.model_construct(**_parse_evidence_data(e)) for e in data["evidence"]]
        return self.evidence_corpus

    def _tokenize(self, text: str) -> list[str]:
        return text.lower().split()

    def build_index(self, evidence_list: list[Evidence] | None = None):
        if evidence_list is not None:
            self.evidence_corpus = evidence_list
        elif not self.evidence_corpus:
            self.load_corpus()

        self.tokenized_corpus = [self._tokenize(e.content) for e in self.evidence_corpus]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

        # Save index to cache
        self.index_cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = self.index_cache_path / "bm25_index.pkl"
        with cache_file.open("wb") as f:
            pickle.dump({
                "bm25": self.bm25,
                "tokenized_corpus": self.tokenized_corpus,
                "evidence_ids": [e.evidence_id for e in self.evidence_corpus],
            }, f)

    def load_index(self) -> bool:
        cache_file = self.index_cache_path / "bm25_index.pkl"
        if not cache_file.exists():
            return False
        try:
            with cache_file.open("rb") as f:
                data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.tokenized_corpus = data["tokenized_corpus"]
            # Verify evidence corpus matches
            cached_ids = data["evidence_ids"]
            if not self.evidence_corpus:
                self.load_corpus()
            current_ids = [e.evidence_id for e in self.evidence_corpus]
            if cached_ids != current_ids:
                return False
            return True
        except Exception:
            return False

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedCandidate]:
        if self.bm25 is None:
            if not self.load_index():
                self.build_index()

        k = top_k or self.top_k
        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        candidates = []
        for rank, idx in enumerate(top_indices):
            evidence = self.evidence_corpus[idx]
            candidate = RetrievedCandidate(
                evidence=evidence,
                bm25_score=float(scores[idx]),
                bm25_rank=rank + 1,
                retrieval_sources=["BM25"],
            )
            candidates.append(candidate)

        return candidates

    def get_evidence_by_id(self, evidence_id: str) -> Evidence | None:
        if not self.evidence_corpus:
            self.load_corpus()
        for e in self.evidence_corpus:
            if e.evidence_id == evidence_id:
                return e
        return None