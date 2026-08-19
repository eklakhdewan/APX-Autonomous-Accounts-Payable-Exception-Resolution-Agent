from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class EvidenceType(str, Enum):
    HISTORICAL_RESOLUTION = "historical_resolution"
    VENDOR_POLICY = "vendor_policy"
    CONTRACT = "contract"
    PAYMENT_TERM = "payment_term"


class SourceAuthority(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    REGULATORY = "regulatory"
    CONTRACTUAL = "contractual"


class ValidityStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    STALE = "stale"
    OUT_OF_SCOPE = "out_of_scope"
    VENDOR_MISMATCH = "vendor_mismatch"
    INVALID_OUTCOME = "invalid_outcome"
    WRONG_POLICY_VERSION = "wrong_policy_version"


class Evidence(BaseModel):
    evidence_id: str = Field(..., min_length=1)
    evidence_type: EvidenceType
    scope: str = Field(..., min_length=1)
    scope_target: str = Field(..., min_length=1)
    vendor_id: Optional[str] = None
    effective_from: date
    effective_until: date
    policy_version: str = Field(..., min_length=1)
    outcome: str = Field(..., min_length=1)
    source_authority: SourceAuthority
    usage_count: int = Field(default=0, ge=0)
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    applicable_exception_types: list[str] = Field(default_factory=list)

    @field_validator("usage_count", mode="before")
    @classmethod
    def _to_int(cls, v):
        if isinstance(v, int):
            return v
        return int(v)

    @field_validator("applicable_exception_types", mode="before")
    @classmethod
    def _normalize_exception_types(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v.strip().upper()] if v.strip() else []
        cleaned = []
        for item in v:
            if item is None:
                continue
            value = str(item).strip().upper()
            if value:
                cleaned.append(value)
        return list(dict.fromkeys(cleaned))


class EvidenceValidityResult(BaseModel):
    evidence_id: str
    is_valid: bool
    status: ValidityStatus
    reasons: list[str] = Field(default_factory=list)


class RetrievedCandidate(BaseModel):
    evidence: Evidence
    bm25_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    dense_score: Optional[float] = None
    dense_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    rrf_rank: Optional[int] = None
    reranker_score: Optional[float] = None
    final_rank: Optional[int] = None
    retrieval_sources: list[str] = Field(default_factory=list)


class ValidatedEvidence(BaseModel):
    evidence: Evidence
    relevance_score: float
    reranker_score: float
    retrieval_sources: list[str]
    rank: int
    validity_status: ValidityStatus
    validity_reasons: list[str] = Field(default_factory=list)
    scope_metadata: dict[str, Any] = Field(default_factory=dict)
    source_authority: SourceAuthority
    content: str


class EvidenceSet(BaseModel):
    invoice_id: str
    vendor_id: str
    exception_codes: list[str]
    query: str
    candidates: list[RetrievedCandidate] = Field(default_factory=list)
    validated_evidence: list[ValidatedEvidence] = Field(default_factory=list)
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def valid_count(self) -> int:
        return len([e for e in self.validated_evidence if e.validity_status == ValidityStatus.VALID])

    @property
    def invalid_count(self) -> int:
        return len(self.validated_evidence) - self.valid_count