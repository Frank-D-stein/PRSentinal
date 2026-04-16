"""PR comment rendering using Jinja2 templates."""
from __future__ import annotations

from pathlib import Path

from github.PullRequest import PullRequest
from jinja2 import Environment, FileSystemLoader

# Sentinel tag used to find and update existing comments
_COMMENT_TAG = "<!-- pr-sentinel-report -->"
_AI_DIMENSIONS = {
    "description",
    "diff_coherence",
    "ai_slop_signals",
    "breaking_awareness",
}


def _get_templates_dir() -> str:
    return str(Path(__file__).parent / "templates")


def render_comment(
    scores: dict[str, float],
    overall_score: float,
    flags: list[str],
    notes: dict[str, str],
    ai_scored: bool,
    min_score: float = 6.0,
) -> str:
    """Render the PR comment body from the scoring data."""
    display_scores = {
        key: (None if not ai_scored and key in _AI_DIMENSIONS else round(value, 1))
        for key, value in scores.items()
    }

    env = Environment(
        loader=FileSystemLoader(_get_templates_dir()),
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template("comment.md.j2")
    return template.render(
        scores=scores,
        display_scores=display_scores,
        overall_score=overall_score,
        flags=flags,
        notes=notes,
        ai_scored=ai_scored,
        min_score=min_score,
        tag=_COMMENT_TAG,
    )


def post_comment(pr: PullRequest, body: str) -> None:
    """Post (or update) the PR Sentinel report comment on the pull request."""
    for comment in pr.get_issue_comments():
        if _COMMENT_TAG in comment.body:
            comment.edit(body)
            return
    pr.create_issue_comment(body)
