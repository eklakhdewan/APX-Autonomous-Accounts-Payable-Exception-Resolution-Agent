from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import yaml
from pydantic import BaseModel, Field, field_validator


class RetrievalProfile(BaseModel):
    dense_model: str
    reranker_model: str
    device: str
    batch_size: int
    max_seq_length: int
    bm25_top_k: int
    dense_top_k: int
    rrf_k: int
    rrf_constant: int
    reranker_top_k: int
    evidence_validity_enabled: bool
    description: str = ""


class AgentConfig(BaseModel):
    max_investigation_steps: int = Field(default=10, ge=1)
    default_llm_provider: str = Field(default="mock")


class RetrievalConfig(BaseModel):
    profiles: dict[str, RetrievalProfile]
    defaults: dict[str, Any]


class AgentSettings(BaseModel):
    max_investigation_steps: int = Field(default=10, ge=1)
    default_llm_provider: str = Field(default="mock")


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
    retrieval: RetrievalConfig
    agent: AgentSettings
    data_dir: Path = Field(default=Path("apx/data/datasets"))

    @classmethod
    def load(cls, config_path: str | Path = "apx/config/risk_policy.yaml") -> Settings:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Risk policy not found: {path}")
        with path.open("r") as f:
            raw = yaml.safe_load(f)
        
        # Load retrieval config separately
        retrieval_path = Path("apx/config/retrieval_profiles.yaml")
        if retrieval_path.exists():
            with retrieval_path.open("r") as f:
                retrieval_raw = yaml.safe_load(f)
        else:
            retrieval_raw = {"profiles": {}, "defaults": {}, "agent": {}}
        
        # Handle the case where profiles is at top level of retrieval_profiles.yaml
        profiles = retrieval_raw.get("profiles", retrieval_raw.get("profiles", {}))
        defaults = retrieval_raw.get("defaults", retrieval_raw.get("defaults", {}))
        agent_config = retrieval_raw.get("agent", retrieval_raw.get("agent", {}))
        
        return cls(
            risk_policy=RiskPolicy(**raw),
            retrieval=RetrievalConfig(profiles=profiles, defaults=defaults),
            agent=AgentSettings(**agent_config),
            data_dir=Path("apx/data/datasets")
        )

    def get_tolerance(self) -> ToleranceConfig:
        return self.risk_policy.tolerance

    def get_retrieval_profile(self, profile_name: str | None = None) -> RetrievalProfile:
        if profile_name is None:
            profile_name = self.retrieval.defaults.get("active_profile", "DEV")
        profiles = self.retrieval.profiles
        if profile_name not in profiles:
            raise ValueError(f"Retrieval profile '{profile_name}' not found")
        return profiles[profile_name]

    def get_corpus_path(self) -> Path:
        return Path(self.retrieval.defaults.get("corpus_path", "apx/data/datasets/evidence"))

    def get_eval_path(self) -> Path:
        return Path(self.retrieval.defaults.get("eval_path", "apx/data/datasets/eval"))

    def get_index_cache_path(self) -> Path:
        return Path(self.retrieval.defaults.get("index_cache_path", "apx/data/datasets/evidence/index"))

    def get_agent_settings(self) -> AgentSettings:
        return self.agent


_settings: Settings | None = None


def get_settings(config_path: str | Path = "apx/config/risk_policy.yaml") -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings.load(config_path)
    return _settings


def reset_settings():
    global _settings
    _settings = None