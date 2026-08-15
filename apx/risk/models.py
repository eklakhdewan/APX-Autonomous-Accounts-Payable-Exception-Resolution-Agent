from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskDimension(str, Enum):
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    VENDOR = "vendor"
    OPERATIONAL = "operational"
    EVIDENCE_CONFIDENCE = "evidence_confidence"


class RiskDimensionScore(BaseModel):
    dimension: RiskDimension
    score: Decimal = Field(..., ge=0, le=1)
    weight: Decimal = Field(..., ge=0, le=1)
    weighted_score: Decimal = Field(..., ge=0, le=1)
    factors: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    overall_score: Decimal = Field(..., ge=0, le=1)
    risk_level: RiskLevel
    dimension_scores: list[RiskDimensionScore] = Field(default_factory=list)
    investigation_outcome: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    calculation_metadata: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class RiskThresholds(BaseModel):
    low_max: Decimal = Field(default=Decimal("0.3"), ge=0, le=1)
    medium_max: Decimal = Field(default=Decimal("0.6"), ge=0, le=1)
    high_max: Decimal = Field(default=Decimal("0.8"), ge=0, le=1)
    # CRITICAL is > high_max


class RiskPolicyConfig(BaseModel):
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    dimension_weights: dict[str, Decimal] = Field(default_factory=dict)
    financial_thresholds: dict[str, Decimal] = Field(default_factory=dict)
    severity_weights: dict[str, Decimal] = Field(default_factory=dict)
    confidence_thresholds: dict[str, Decimal] = Field(default_factory=dict)
    evidence_thresholds: dict[str, int] = Field(default_factory=dict)
    historical_thresholds: dict[str, Decimal] = Field(default_factory=dict)
    always_escalate_rules: list[dict[str, Any]] = Field(default_factory=list)
    auto_resolve_rules: list[dict[str, Any]] = Field(default_factory=list)
    compound_weights: dict[str, Decimal] = Field(default_factory=dict)