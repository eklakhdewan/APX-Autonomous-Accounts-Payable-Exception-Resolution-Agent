from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml
from pydantic import BaseModel, Field, field_validator


class AmountRiskConfig(BaseModel):
    low_threshold: float = Field(..., ge=0)
    medium_threshold: float = Field(..., ge=0)
    high_threshold: float = Field(..., ge=0)
    weight: float = Field(..., ge=0, le=1)


class SeverityRiskConfig(BaseModel):
    weights: dict[str, float]
    weight: float = Field(..., ge=0, le=1)


class ConfidenceRiskConfig(BaseModel):
    high_threshold: float = Field(..., ge=0, le=1)
    medium_threshold: float = Field(..., ge=0, le=1)
    low_threshold: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)


class EvidenceRiskConfig(BaseModel):
    min_evidence_count: int = Field(..., ge=0)
    weight: float = Field(..., ge=0, le=1)


class HistoricalRiskConfig(BaseModel):
    min_success_rate: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)


class CompoundRiskWeights(BaseModel):
    amount: float = Field(..., ge=0, le=1)
    severity: float = Field(..., ge=0, le=1)
    confidence: float = Field(..., ge=0, le=1)
    evidence: float = Field(..., ge=0, le=1)
    historical: float = Field(..., ge=0, le=1)

    @field_validator("amount", "severity", "confidence", "evidence", "historical", mode="after")
    @classmethod
    def _check_sum(cls, v, info):
        if info.field_name == "historical":
            total = (info.data.get("amount", 0) + info.data.get("severity", 0) +
                     info.data.get("confidence", 0) + info.data.get("evidence", 0) + v)
            if abs(total - 1.0) > 0.001:
                raise ValueError(f"Compound risk weights must sum to 1.0, got {total}")
        return v


class AmountThresholds(BaseModel):
    auto_resolve_max: float = Field(..., ge=0)
    review_required_min: float = Field(..., ge=0)
    escalate_min: float = Field(..., ge=0)


class ConfidenceThresholds(BaseModel):
    auto_resolve_min: float = Field(..., ge=0, le=1)
    human_review_max: float = Field(..., ge=0, le=1)


class EvidenceThresholds(BaseModel):
    auto_resolve_min: int = Field(..., ge=0)
    human_review_min: int = Field(..., ge=0)


class HistoricalSuccessThresholds(BaseModel):
    auto_resolve_min: float = Field(..., ge=0, le=1)


class AlwaysEscalateRule(BaseModel):
    exception_code: str | None = None
    condition: str | None = None
    reason: str


class AutoResolveRule(BaseModel):
    exception_code: str
    max_amount: float = Field(..., ge=0)
    reason: str


class ToleranceConfig(BaseModel):
    amount_percentage: float = Field(..., ge=0, le=1)
    amount_absolute: float = Field(..., ge=0)
    tax_percentage: float = Field(..., ge=0, le=1)
    quantity_percentage: float = Field(..., ge=0, le=1)
    discount_percentage: float = Field(..., ge=0, le=1)


class RiskPolicy(BaseModel):
    amount_risk: AmountRiskConfig
    severity_risk: SeverityRiskConfig
    confidence_risk: ConfidenceRiskConfig
    evidence_risk: EvidenceRiskConfig
    historical_risk: HistoricalRiskConfig
    compound_risk_weights: CompoundRiskWeights
    amount_thresholds: AmountThresholds
    confidence_thresholds: ConfidenceThresholds
    evidence_thresholds: EvidenceThresholds
    historical_success_thresholds: HistoricalSuccessThresholds
    always_escalate_rules: list[AlwaysEscalateRule]
    auto_resolve_rules: list[AutoResolveRule]
    tolerance: ToleranceConfig


class Settings(BaseModel):
    risk_policy: RiskPolicy
    data_dir: Path = Field(default=Path("apx/data/datasets"))

    @classmethod
    def load(cls, config_path: str | Path = "apx/config/risk_policy.yaml") -> Settings:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Risk policy not found: {path}")
        with path.open("r") as f:
            raw = yaml.safe_load(f)
        return cls(risk_policy=RiskPolicy(**raw), data_dir=Path("apx/data/datasets"))

    def get_tolerance(self) -> ToleranceConfig:
        return self.risk_policy.tolerance


_settings: Settings | None = None


def get_settings(config_path: str | Path = "apx/config/risk_policy.yaml") -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load(config_path)
    return _settings


def reset_settings():
    global _settings
    _settings = None