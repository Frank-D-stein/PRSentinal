"""Fast, free heuristic scoring checks for PR quality."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from unidiff import PatchSet

from .config import Config

# Conventional commit pattern: type(scope)!: subject
CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\(.+\))?(!)?: .{3,}"
)

# Patterns that identify test files
_TEST_FILE_PATTERNS = [
    r"(^|/)tests?/",
    r"(^|/)specs?/",
    r"test_[^/]+$",
    r"[^/]+_test\.[^/]+$",
    r"[^/]+\.test\.[^/]+$",
    r"[^/]+\.spec\.[^/]+$",
]
_TEST_FILE_RE = re.compile("|".join(_TEST_FILE_PATTERNS), re.IGNORECASE)


@dataclass
class HeuristicScores:
    change_size: float
    test_coverage: float
    commit_messages: float
    total_lines: int = 0
    test_ratio: float = 0.0


def is_test_file(filename: str) -> bool:
    """Return True if the filename looks like a test file."""
    return bool(_TEST_FILE_RE.search(filename))


def score_change_size(additions: int, deletions: int, max_diff_lines: int) -> float:
    """Score the PR based on total diff size relative to the configured maximum."""
    total = additions + deletions
    if total == 0:
        return 10.0
    if total <= max_diff_lines * 0.25:
        return 10.0
    if total <= max_diff_lines * 0.50:
        return 9.0
    if total <= max_diff_lines * 0.75:
        return 8.0
    if total <= max_diff_lines:
        return 6.0
    if total <= max_diff_lines * 1.5:
        return 4.0
    if total <= max_diff_lines * 2:
        return 2.0
    return 1.0


def score_test_coverage(diff: str, min_test_ratio: float) -> tuple[float, float]:
    """
    Score test coverage based on the ratio of test lines to non-test lines.

    Returns (score, ratio).
    """
    if not diff.strip():
        return 5.0, 0.0

    try:
        patch = PatchSet(diff)
    except Exception:
        return 5.0, 0.0

    # An empty (or non-parseable) patch has no signal — return neutral.
    if not patch:
        return 5.0, 0.0

    test_added = 0
    non_test_added = 0

    for patched_file in patch:
        # Use the pre-computed `.added` count instead of iterating over hunks.
        added = patched_file.added
        if is_test_file(patched_file.path):
            test_added += added
        else:
            non_test_added += added

    if non_test_added == 0:
        if test_added == 0:
            # Nothing was added at all
            return 5.0, 0.0
        # Only test files were modified
        return 10.0, 1.0

    total_added = test_added + non_test_added
    ratio = test_added / total_added

    if ratio >= min_test_ratio * 2:
        return 10.0, ratio
    if ratio >= min_test_ratio:
        return 8.0, ratio
    if ratio >= min_test_ratio * 0.5:
        return 5.0, ratio
    if ratio > 0:
        return 3.0, ratio
    return 1.0, 0.0


def score_commit_messages(commits: list[dict]) -> float:
    """Score commit messages based on format quality."""
    if not commits:
        return 5.0

    scores = []
    for commit in commits:
        message = commit.get("message", "").split("\n")[0].strip()
        if CONVENTIONAL_COMMIT_RE.match(message):
            scores.append(10.0)
        elif len(message) >= 20:
            scores.append(7.0)
        elif len(message) >= 10:
            scores.append(5.0)
        else:
            scores.append(2.0)

    return sum(scores) / len(scores)


def run_heuristics(
    diff: str,
    commits: list[dict],
    additions: int,
    deletions: int,
    config: Config,
) -> HeuristicScores:
    """Run all heuristic checks and return the combined scores."""
    change_size = score_change_size(additions, deletions, config.thresholds.max_diff_lines)
    test_score, test_ratio = score_test_coverage(diff, config.thresholds.min_test_ratio)
    commit_score = score_commit_messages(commits)
    return HeuristicScores(
        change_size=change_size,
        test_coverage=test_score,
        commit_messages=commit_score,
        total_lines=additions + deletions,
        test_ratio=test_ratio,
    )
