"""Score combination helpers for PR Sentinel."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeightedDimension:
    score: float
    weight: float
    included: bool = True


def calculate_overall_score(dimensions: dict[str, WeightedDimension]) -> float:
    """Return a normalized overall score using only included dimensions."""
    active_dimensions = [dimension for dimension in dimensions.values() if dimension.included]
    total_weight = sum(dimension.weight for dimension in active_dimensions)

    if total_weight <= 0:
        return 5.0

    weighted_total = sum(dimension.score * dimension.weight for dimension in active_dimensions)
    return round(weighted_total / total_weight, 2)
