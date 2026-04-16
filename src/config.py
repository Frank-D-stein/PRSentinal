"""Configuration loading and validation for PR Sentinel."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    description: float = 0.20
    diff_coherence: float = 0.20
    test_coverage: float = 0.20
    commit_messages: float = 0.15
    change_size: float = 0.10
    ai_slop_signals: float = 0.10
    breaking_awareness: float = 0.05


class ScoringConfig(BaseModel):
    min_score: float = 6.0
    weights: ScoringWeights = Field(default_factory=ScoringWeights)


class ThresholdsConfig(BaseModel):
    max_diff_lines: int = 800
    min_test_ratio: float = 0.15


class LabelsConfig(BaseModel):
    enabled: bool = True
    low: str = "quality/needs-work"
    medium: str = "quality/ok"
    high: str = "quality/excellent"
    ai_generated: str = "likely-ai-generated"


class ExemptionsConfig(BaseModel):
    authors: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)


class Config(BaseModel):
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    thresholds: ThresholdsConfig = Field(default_factory=ThresholdsConfig)
    labels: LabelsConfig = Field(default_factory=LabelsConfig)
    exemptions: ExemptionsConfig = Field(default_factory=ExemptionsConfig)


def load_config(config_path: str = ".github/pr-sentinel.yml") -> Config:
    """Load config from file, falling back to defaults if not found."""
    path = Path(config_path)
    if path.exists():
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return Config.model_validate(data)
    return Config()
