"""Unit tests for PR comment rendering."""
from __future__ import annotations

from src.comment import render_comment


def test_render_comment_hides_ai_scores_when_ai_is_skipped():
    comment = render_comment(
        scores={
            "description": 5.0,
            "diff_coherence": 5.0,
            "test_coverage": 8.0,
            "commit_messages": 7.0,
            "change_size": 9.0,
            "ai_slop_signals": 5.0,
            "breaking_awareness": 5.0,
        },
        overall_score=8.0,
        flags=[],
        notes={
            "description": "Not scored",
            "diff_coherence": "Not scored",
            "test_coverage": "Good coverage",
            "commit_messages": "Clear history",
            "change_size": "Focused scope",
            "ai_slop_signals": "Not scored",
            "breaking_awareness": "Not scored",
        },
        ai_scored=False,
        min_score=6.0,
    )

    assert "| Description | N/A | Not scored |" in comment
    assert "| Test coverage | 8/10 | Good coverage |" in comment
    assert "AI-only dimensions were omitted from the overall score." in comment
