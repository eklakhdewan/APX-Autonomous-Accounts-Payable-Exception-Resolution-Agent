from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

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


class DenseRetriever:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "cpu",
        top_k: int = 50,
        batch_size: int = 16,
        max_seq_length: int = 512,
        corpus_path: Path | None = None,
        index_cache_path: Path | None = None,
        local_files_only: bool = False,
    ):
        self.model_name = model_name
        self.device = device
        self.top_k = top_k
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self.local_files_only = local_files_only
        self.settings = get_settings()
        self.corpus_path = corpus_path or self.settings.get_corpus_path()
        self.index_cache_path = index_cache_path or self.settings.get_index_cache_path()
        self.model: SentenceTransformer | None = None
        self.evidence_corpus: list[Evidence] = []
        self.embeddings: np.ndarray | None = None

    def _load_model(self):
        if self.model is None:
            self.model = SentenceTransformer(self.model_name, device=self.device, local_files_only=self.local_files_only)
            self.model.max_seq_length = self.max_seq_length

    def load_corpus(self) -> list[Evidence]:
        corpus_file = self.corpus_path / "evidence_corpus.json"
        if not corpus_file.exists():
            raise FileNotFoundError(f"Evidence corpus not found at {corpus_file}")
        with corpus_file.open("r") as f:
            data = json.load(f)
        self.evidence_corpus = [Evidence.model_construct(**_parse_evidence_data(e)) for e in data["evidence"]]
        return self.evidence_corpus

    def build_index(self, evidence_list: list[Evidence] | None = None):
        if evidence_list is not None:
            self.evidence_corpus = evidence_list
        elif not self.evidence_corpus:
            self.load_corpus()

        self._load_model()

        texts = [e.content for e in self.evidence_corpus]
        self.embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Save index to cache
        self.index_cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = self.index_cache_path / "dense_index.pkl"
        with cache_file.open("wb") as f:
            pickle.dump({
                "embeddings": self.embeddings,
                "evidence_ids": [e.evidence_id for e in self.evidence_corpus],
                "model_name": self.model_name,
            }, f)

    def load_index(self) -> bool:
        cache_file = self.index_cache_path / "dense_index.pkl"
        if not cache_file.exists():
            return False
        try:
            with cache_file.open("rb") as f:
                data = pickle.load(f)
            if data.get("model_name") != self.model_name:
                return False
            self.embeddings = data["embeddings"]
            if not self.evidence_corpus:
                self.load_corpus()
            current_ids = [e.evidence_id for e in self.evidence_corpus]
            if data["evidence_ids"] != current_ids:
                return False
            return True
        except Exception:
            return False

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedCandidate]:
        if self.embeddings is None:
            if not self.load_index():
                self.build_index()

        self._load_model()

        k = top_k or self.top_k
        query_embedding = self.model.encode(
            [query],
            batch_size=1,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Cosine similarity (embeddings are normalized)
        scores = np.dot(self.embeddings, query_embedding.T).flatten()

        top_indices = np.argsort(scores)[::-1][:k]

        candidates = []
        for rank, idx in enumerate(top_indices):
            evidence = self.evidence_corpus[idx]
            candidate = RetrievedCandidate(
                evidence=evidence,
                dense_score=float(scores[idx]),
                dense_rank=rank + 1,
                retrieval_sources=["Dense"],
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