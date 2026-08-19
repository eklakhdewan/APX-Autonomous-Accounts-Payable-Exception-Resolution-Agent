from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Optional

from apx.config.settings import get_settings
from apx.data.schemas import ExceptionReport, ExceptionCode
from apx.evidence.schemas import (
    Evidence,
    EvidenceSet,
    RetrievedCandidate,
    ValidatedEvidence,
    ValidityStatus,
    SourceAuthority,
)
from apx.evidence.bm25 import BM25Retriever
from apx.evidence.dense import DenseRetriever
from apx.evidence.rrf import rrf_fuse
from apx.evidence.reranker import CrossEncoderReranker
from apx.evidence.validity import EvidenceValidator
from apx.evidence.query import create_query_from_exception_report


class HybridContextEngine:
    def __init__(
        self,
        profile_name: str = "DEV",
        bm25_top_k: int | None = None,
        dense_top_k: int | None = None,
        rrf_k: int | None = None,
        rrf_constant: int | None = None,
        reranker_top_k: int | None = None,
        evidence_validity_enabled: bool | None = None,
        reference_date: date | str | None = None,
    ):
        self.settings = get_settings()
        self.profile = self.settings.get_retrieval_profile(profile_name)

        # Override with provided values or use profile defaults
        self.bm25_top_k = bm25_top_k or self.profile.bm25_top_k
        self.dense_top_k = dense_top_k or self.profile.dense_top_k
        self.rrf_k = rrf_k or self.profile.rrf_k
        self.rrf_constant = rrf_constant or self.profile.rrf_constant
        self.reranker_top_k = reranker_top_k or self.profile.reranker_top_k
        self.evidence_validity_enabled = (
            evidence_validity_enabled if evidence_validity_enabled is not None else self.profile.evidence_validity_enabled
        )

        # Handle reference_date - accept string or date
        if isinstance(reference_date, str):
            reference_date = date.fromisoformat(reference_date)

        # Initialize retrievers
        self.bm25_retriever = BM25Retriever(top_k=self.bm25_top_k)
        self.dense_retriever = DenseRetriever(
            model_name=self.profile.dense_model,
            device=self.profile.device,
            top_k=self.dense_top_k,
            batch_size=self.profile.batch_size,
            max_seq_length=self.profile.max_seq_length,
            local_files_only=self.profile.local_files_only,
        )
        self.reranker = CrossEncoderReranker(
            model_name=self.profile.reranker_model,
            device=self.profile.device,
            top_k=self.reranker_top_k,
            batch_size=self.profile.batch_size,
            max_seq_length=self.profile.max_seq_length,
            local_files_only=self.profile.local_files_only,
        )
        self.validator = EvidenceValidator(reference_date=reference_date)

        # Ensure indexes exist
        self._ensure_indexes()

    def _ensure_indexes(self):
        # Load or build BM25 index
        if not self.bm25_retriever.load_index():
            self.bm25_retriever.load_corpus()
            self.bm25_retriever.build_index()

        # Load or build dense index
        if not self.dense_retriever.load_index():
            self.dense_retriever.load_corpus()
            self.dense_retriever.build_index()

    def retrieve(self, exception_report: ExceptionReport) -> EvidenceSet:
        # Build query
        query = create_query_from_exception_report(exception_report)
        exception_codes = exception_report.exception_codes

        # BM25 retrieval
        bm25_candidates = self.bm25_retriever.retrieve(query, top_k=self.bm25_top_k)

        # Dense retrieval
        dense_candidates = self.dense_retriever.retrieve(query, top_k=self.dense_top_k)

        # RRF fusion
        fused_candidates = rrf_fuse(
            bm25_candidates,
            dense_candidates,
            k=self.rrf_k,
            rrf_constant=self.rrf_constant,
        )

        # Cross-encoder reranking
        reranked_candidates = self.reranker.rerank(query, fused_candidates, top_k=self.reranker_top_k)

        # Evidence validity filtering
        validated_evidence = []
        if self.evidence_validity_enabled:
            for candidate in reranked_candidates:
                validity_result = self.validator.validate(
                    candidate.evidence,
                    exception_codes,
                    invoice_vendor_id=exception_report.vendor_id,
                )

                validated = ValidatedEvidence(
                    evidence=candidate.evidence,
                    relevance_score=candidate.reranker_score or candidate.rrf_score or 0.0,
                    reranker_score=candidate.reranker_score or 0.0,
                    retrieval_sources=candidate.retrieval_sources,
                    rank=candidate.final_rank or candidate.rrf_rank or 0,
                    validity_status=validity_result.status,
                    validity_reasons=validity_result.reasons,
                    scope_metadata={
                        "scope": candidate.evidence.scope,
                        "scope_target": candidate.evidence.scope_target,
                        "vendor_id": candidate.evidence.vendor_id,
                        "effective_from": candidate.evidence.effective_from.isoformat(),
                        "effective_until": candidate.evidence.effective_until.isoformat(),
                        "policy_version": candidate.evidence.policy_version,
                    },
                    source_authority=candidate.evidence.source_authority,
                    content=candidate.evidence.content,
                )
                validated_evidence.append(validated)
        else:
            # Skip validation, just convert to ValidatedEvidence
            for candidate in reranked_candidates:
                validated = ValidatedEvidence(
                    evidence=candidate.evidence,
                    relevance_score=candidate.reranker_score or candidate.rrf_score or 0.0,
                    reranker_score=candidate.reranker_score or 0.0,
                    retrieval_sources=candidate.retrieval_sources,
                    rank=candidate.final_rank or candidate.rrf_rank or 0,
                    validity_status=ValidityStatus.VALID,
                    validity_reasons=[],
                    scope_metadata={
                        "scope": candidate.evidence.scope,
                        "scope_target": candidate.evidence.scope_target,
                        "vendor_id": candidate.evidence.vendor_id,
                        "effective_from": candidate.evidence.effective_from.isoformat(),
                        "effective_until": candidate.evidence.effective_until.isoformat(),
                        "policy_version": candidate.evidence.policy_version,
                    },
                    source_authority=candidate.evidence.source_authority,
                    content=candidate.evidence.content,
                )
                validated_evidence.append(validated)

        # Create EvidenceSet
        evidence_set = EvidenceSet(
            invoice_id=exception_report.invoice_id,
            vendor_id=exception_report.vendor_id,
            exception_codes=[e.value for e in exception_report.exception_codes],
            query=query,
            candidates=reranked_candidates,
            validated_evidence=validated_evidence,
            retrieval_metadata={
                "profile": self.profile.description,
                "bm25_top_k": self.bm25_top_k,
                "dense_top_k": self.dense_top_k,
                "rrf_k": self.rrf_k,
                "rrf_constant": self.rrf_constant,
                "reranker_top_k": self.reranker_top_k,
                "total_candidates": len(reranked_candidates),
                "valid_evidence_count": len([e for e in validated_evidence if e.validity_status == ValidityStatus.VALID]),
            },
        )

        return evidence_set


def create_hybrid_context_engine(profile_name: str = "DEV") -> HybridContextEngine:
    return HybridContextEngine(profile_name=profile_name)