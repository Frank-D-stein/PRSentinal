"""Unit tests for score combination."""
from __future__ import annotations

from src.scoring import WeightedDimension, calculate_overall_score


def test_calculate_overall_score_uses_all_active_dimensions():
    overall = calculate_overall_score(
        {
            "heuristic": WeightedDimension(score=8.0, weight=0.4),
            "ai": WeightedDimension(score=6.0, weight=0.6),
        }
    )

    assert overall == 6.8


def test_calculate_overall_score_reweights_when_ai_is_skipped():
    overall = calculate_overall_score(
        {
            "test_coverage": WeightedDimension(score=9.0, weight=0.2),
            "commit_messages": WeightedDimension(score=8.0, weight=0.15),
            "change_size": WeightedDimension(score=10.0, weight=0.1),
            "description": WeightedDimension(score=5.0, weight=0.2, included=False),
            "diff_coherence": WeightedDimension(score=5.0, weight=0.2, included=False),
            "ai_slop_signals": WeightedDimension(score=5.0, weight=0.1, included=False),
            "breaking_awareness": WeightedDimension(score=5.0, weight=0.05, included=False),
        }
    )

    assert overall == 8.89


def test_calculate_overall_score_returns_neutral_when_no_dimensions_are_active():
    overall = calculate_overall_score(
        {
            "description": WeightedDimension(score=10.0, weight=0.0, included=False),
        }
    )

    assert overall == 5.0
