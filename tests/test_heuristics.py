"""Unit tests for heuristic scoring checks."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.heuristics import (
    HeuristicScores,
    is_test_file,
    run_heuristics,
    score_change_size,
    score_commit_messages,
    score_test_coverage,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ── is_test_file ──────────────────────────────────────────────────────────────


class TestIsTestFile:
    def test_test_prefix(self):
        assert is_test_file("test_utils.py") is True

    def test_test_suffix(self):
        assert is_test_file("utils_test.py") is True

    def test_test_directory(self):
        assert is_test_file("tests/test_utils.py") is True

    def test_nested_test_directory(self):
        assert is_test_file("src/tests/test_utils.py") is True

    def test_jest_test_extension(self):
        assert is_test_file("utils.test.js") is True

    def test_jest_spec_extension(self):
        assert is_test_file("utils.spec.ts") is True

    def test_spec_directory(self):
        assert is_test_file("spec/utils_spec.rb") is True

    def test_regular_source_file(self):
        assert is_test_file("src/utils.py") is False

    def test_docs_file(self):
        assert is_test_file("docs/readme.md") is False

    def test_config_file(self):
        assert is_test_file("pyproject.toml") is False


# ── score_change_size ─────────────────────────────────────────────────────────


class TestScoreChangeSize:
    def test_empty_diff(self):
        assert score_change_size(0, 0, 800) == 10.0

    def test_tiny_change(self):
        # 10 lines << 800 * 0.25 = 200
        assert score_change_size(5, 5, 800) == 10.0

    def test_small_change(self):
        # 300 lines <= 800 * 0.5 = 400
        assert score_change_size(150, 150, 800) == 9.0

    def test_medium_change(self):
        # 500 lines is between 800*0.5 and 800*0.75
        assert score_change_size(250, 250, 800) == 8.0

    def test_at_limit(self):
        # 800 lines exactly <= max_diff_lines
        assert score_change_size(400, 400, 800) == 6.0

    def test_over_limit(self):
        # 1000 lines is > 800 but <= 1200 (800 * 1.5)
        assert score_change_size(500, 500, 800) == 4.0

    def test_double_limit(self):
        # 1600 lines is > 800 * 2
        assert score_change_size(800, 800, 800) <= 2.0

    def test_massive_change(self):
        assert score_change_size(5000, 5000, 800) == 1.0


# ── score_test_coverage ───────────────────────────────────────────────────────


class TestScoreTestCoverage:
    def test_with_tests(self):
        diff = (FIXTURES / "sample_diff_with_tests.diff").read_text()
        score, ratio = score_test_coverage(diff, 0.15)
        assert score >= 7.0
        assert ratio > 0.0

    def test_no_tests(self):
        diff = (FIXTURES / "sample_diff_no_tests.diff").read_text()
        score, ratio = score_test_coverage(diff, 0.15)
        assert score <= 3.0
        assert ratio == 0.0

    def test_invalid_diff_returns_neutral(self):
        score, ratio = score_test_coverage("not a valid diff", 0.15)
        assert score == 5.0
        assert ratio == 0.0

    def test_empty_diff_returns_neutral(self):
        score, ratio = score_test_coverage("", 0.15)
        assert score == 5.0
        assert ratio == 0.0

    def test_large_diff_without_tests(self):
        diff = (FIXTURES / "sample_diff_large.diff").read_text()
        score, ratio = score_test_coverage(diff, 0.15)
        assert score <= 3.0


# ── score_commit_messages ─────────────────────────────────────────────────────


class TestScoreCommitMessages:
    def test_all_conventional(self):
        commits = [
            {"message": "feat: add user authentication"},
            {"message": "fix: correct null pointer in login handler"},
            {"message": "docs: update API reference"},
        ]
        assert score_commit_messages(commits) == 10.0

    def test_conventional_with_scope(self):
        commits = [{"message": "feat(auth): implement OAuth2 login flow"}]
        assert score_commit_messages(commits) == 10.0

    def test_conventional_breaking_change(self):
        commits = [{"message": "feat!: redesign public API"}]
        assert score_commit_messages(commits) == 10.0

    def test_descriptive_non_conventional(self):
        commits = [{"message": "Improve error handling in authentication module"}]
        score = score_commit_messages(commits)
        assert 6.0 <= score <= 8.0

    def test_mixed_quality(self):
        commits = [
            {"message": "feat: add new feature"},
            {"message": "fix"},  # too short
        ]
        score = score_commit_messages(commits)
        assert 5.0 <= score <= 8.0

    def test_all_poor(self):
        commits = [
            {"message": "wip"},
            {"message": "fix"},
            {"message": "x"},
        ]
        assert score_commit_messages(commits) <= 3.0

    def test_empty_commits(self):
        assert score_commit_messages([]) == 5.0

    def test_missing_message_key(self):
        commits = [{}]
        assert score_commit_messages(commits) <= 3.0


# ── run_heuristics ────────────────────────────────────────────────────────────


class TestRunHeuristics:
    def test_returns_heuristic_scores(self):
        config = Config()
        diff = (FIXTURES / "sample_diff_with_tests.diff").read_text()
        commits = [{"message": "feat: add arithmetic utility functions"}]
        result = run_heuristics(diff, commits, 20, 5, config)

        assert isinstance(result, HeuristicScores)
        assert 0.0 <= result.change_size <= 10.0
        assert 0.0 <= result.test_coverage <= 10.0
        assert 0.0 <= result.commit_messages <= 10.0

    def test_total_lines_populated(self):
        config = Config()
        diff = (FIXTURES / "sample_diff_no_tests.diff").read_text()
        commits = [{"message": "chore: refactor data layer"}]
        result = run_heuristics(diff, commits, 30, 10, config)
        assert result.total_lines == 40

    def test_test_ratio_populated(self):
        config = Config()
        diff = (FIXTURES / "sample_diff_with_tests.diff").read_text()
        commits = [{"message": "feat: add utilities"}]
        result = run_heuristics(diff, commits, 15, 3, config)
        assert result.test_ratio >= 0.0

    def test_high_quality_pr_scores_well(self):
        config = Config()
        diff = (FIXTURES / "sample_diff_with_tests.diff").read_text()
        commits = [
            {"message": "feat: add subtract, multiply and divide utility functions"},
            {"message": "test: add unit tests for new utility functions"},
        ]
        result = run_heuristics(diff, commits, 15, 5, config)
        assert result.commit_messages >= 7.0
        assert result.test_coverage >= 7.0
        assert result.change_size == 10.0
