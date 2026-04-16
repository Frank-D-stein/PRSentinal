"""Label and commit-status management for PR Sentinel."""
from __future__ import annotations

from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from .config import Config


def _ensure_label(repo: Repository, name: str, color: str = "0075ca") -> None:
    """Create the label if it doesn't already exist."""
    try:
        repo.get_label(name)
    except Exception:
        try:
            repo.create_label(name, color)
        except Exception:
            pass  # Label may have been created by a concurrent run


_QUALITY_COLORS = {
    "high": "0e8a16",    # green
    "medium": "e4e669",  # yellow
    "low": "b60205",     # red
}


def apply_labels(
    pr: PullRequest,
    overall_score: float,
    ai_slop_score: float,
    config: Config,
) -> None:
    """Apply quality labels to the PR based on scores."""
    repo = pr.base.repo

    # Determine quality tier
    if overall_score >= 7.5:
        quality_label = config.labels.high
        color = _QUALITY_COLORS["high"]
    elif overall_score >= 5.0:
        quality_label = config.labels.medium
        color = _QUALITY_COLORS["medium"]
    else:
        quality_label = config.labels.low
        color = _QUALITY_COLORS["low"]

    # Remove existing quality labels before applying the new one
    existing_quality = {config.labels.low, config.labels.medium, config.labels.high}
    for label in pr.labels:
        if label.name in existing_quality and label.name != quality_label:
            try:
                pr.remove_from_labels(label.name)
            except Exception:
                pass

    _ensure_label(repo, quality_label, color)
    pr.add_to_labels(quality_label)

    # Apply AI-generated label when slop score is low (lots of AI signals detected)
    ai_label = config.labels.ai_generated
    if ai_slop_score < 4.0:
        _ensure_label(repo, ai_label, "d93f0b")
        pr.add_to_labels(ai_label)
    else:
        # Remove it if it was previously applied
        for label in pr.labels:
            if label.name == ai_label:
                try:
                    pr.remove_from_labels(ai_label)
                except Exception:
                    pass
                break


def set_commit_status(
    token: str,
    repo_name: str,
    sha: str,
    overall_score: float,
    min_score: float,
) -> None:
    """Set a GitHub commit status for the PR head commit."""
    g = Github(token)
    repo = g.get_repo(repo_name)
    commit = repo.get_commit(sha)

    passed = overall_score >= min_score
    state = "success" if passed else "failure"
    description = (
        f"Score: {overall_score:.1f}/10 "
        f"({'passes' if passed else 'below'} threshold of {min_score:.1f})"
    )
    commit.create_status(
        state=state,
        description=description,
        context="PR Sentinel",
    )
