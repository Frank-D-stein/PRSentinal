"""PR Sentinel – main entrypoint."""
from __future__ import annotations

import fnmatch
import json
import os
import sys

from github import Github

from .ai_scorer import run_ai_scoring
from .comment import post_comment, render_comment
from .config import load_config
from .fetcher import fetch_pr_data
from .heuristics import run_heuristics
from .labeler import apply_labels, set_commit_status


def _build_notes(
    heuristic_scores,  # HeuristicScores
    ai_notes: dict[str, str],
    ai_scored: bool,
) -> dict[str, str]:
    """Build human-readable notes for each scoring dimension."""
    total = heuristic_scores.total_lines
    ratio = heuristic_scores.test_ratio

    def change_size_note() -> str:
        s = heuristic_scores.change_size
        if s >= 9:
            return f"Focused, reviewable scope ({total} lines)"
        if s >= 7:
            return f"Manageable size ({total} lines)"
        if s >= 5:
            return f"⚠️ Getting large ({total} lines)"
        return f"⚠️ Very large change ({total} lines)"

    def test_coverage_note() -> str:
        s = heuristic_scores.test_coverage
        if s >= 9:
            return "Good test coverage"
        if s >= 7:
            return f"Adequate coverage ({ratio:.0%} test ratio)"
        if s >= 4:
            return f"⚠️ Low test coverage ({ratio:.0%} test ratio)"
        if ratio > 0:
            return f"⚠️ Very low test coverage ({ratio:.0%} test ratio)"
        return "⚠️ No tests added for new code"

    def commit_note() -> str:
        s = heuristic_scores.commit_messages
        if s >= 9:
            return "Follows conventional commit format"
        if s >= 7:
            return "Clear, descriptive messages"
        if s >= 5:
            return "⚠️ Some messages lack context"
        return "⚠️ Vague or missing commit context"

    notes: dict[str, str] = {
        "change_size": change_size_note(),
        "test_coverage": test_coverage_note(),
        "commit_messages": commit_note(),
    }

    if ai_scored:
        notes.update(
            {
                "description": ai_notes.get("description", "AI-evaluated"),
                "diff_coherence": ai_notes.get("diff_coherence", "AI-evaluated"),
                "ai_slop_signals": ai_notes.get("ai_slop_signals", "AI-evaluated"),
                "breaking_awareness": ai_notes.get("breaking_awareness", "AI-evaluated"),
            }
        )
    else:
        notes.update(
            {
                "description": "Not scored (no API key)",
                "diff_coherence": "Not scored (no API key)",
                "ai_slop_signals": "Not scored (no API key)",
                "breaking_awareness": "Not scored (no API key)",
            }
        )
    return notes


def main() -> None:
    # ── Environment ──────────────────────────────────────────────────────────
    github_token = os.environ.get("GITHUB_TOKEN", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "")
    config_path = os.environ.get("CONFIG_PATH", ".github/pr-sentinel.yml")
    block_on_fail = os.environ.get("BLOCK_ON_FAIL", "false").lower() == "true"
    label_prs = os.environ.get("LABEL_PRS", "true").lower() == "true"

    # Resolve PR number from event payload or env var
    pr_number: int | None = None
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if event_path and os.path.exists(event_path):
        with open(event_path) as f:
            event = json.load(f)
        pr_number = event.get("number") or (event.get("pull_request") or {}).get("number")

    if pr_number is None:
        raw = os.environ.get("PR_NUMBER") or os.environ.get("GITHUB_EVENT_NUMBER")
        if raw:
            pr_number = int(raw)

    if not pr_number:
        print("ERROR: Could not determine PR number.", file=sys.stderr)
        sys.exit(1)

    # ── Config ───────────────────────────────────────────────────────────────
    config = load_config(config_path)

    # Allow the action input to override min_score
    min_score_raw = os.environ.get("MIN_SCORE", "")
    if min_score_raw:
        try:
            config.scoring.min_score = float(min_score_raw)
        except ValueError:
            pass

    # ── Fetch PR data ─────────────────────────────────────────────────────────
    print(f"Fetching PR #{pr_number} from {repo_name} …")
    pr_data = fetch_pr_data(github_token, repo_name, pr_number)

    # ── Exemption checks ─────────────────────────────────────────────────────
    if pr_data.author in config.exemptions.authors:
        print(f"Author '{pr_data.author}' is exempted from scoring. Skipping.")
        sys.exit(0)

    for label in pr_data.labels:
        if label in config.exemptions.labels:
            print(f"PR has exemption label '{label}'. Skipping.")
            sys.exit(0)

    # ── Heuristic pass ───────────────────────────────────────────────────────
    print("Running heuristic pass …")
    heuristic_scores = run_heuristics(
        pr_data.diff,
        pr_data.commits,
        pr_data.additions,
        pr_data.deletions,
        config,
    )

    # ── AI pass ──────────────────────────────────────────────────────────────
    ai_scored = False
    ai_score_obj = None

    if anthropic_key:
        # Skip AI pass if every changed file matches an exemption path pattern
        needs_ai = True
        if config.exemptions.paths and pr_data.changed_files:
            needs_ai = not all(
                any(fnmatch.fnmatch(f, pat) for pat in config.exemptions.paths)
                for f in pr_data.changed_files
            )

        if needs_ai:
            print("Running AI scoring pass …")
            try:
                ai_score_obj = run_ai_scoring(
                    pr_data.diff,
                    pr_data.body,
                    pr_data.title,
                    pr_data.commits,
                    anthropic_key,
                )
                ai_scored = True
            except Exception as exc:
                print(f"WARNING: AI scoring failed: {exc}", file=sys.stderr)
        else:
            print("All changed files are path-exempted; skipping AI pass.")
    else:
        print("No ANTHROPIC_API_KEY provided; skipping AI pass.")

    # ── Combine scores ───────────────────────────────────────────────────────
    w = config.scoring.weights

    description_score = ai_score_obj.description_quality if ai_scored and ai_score_obj else 5.0
    diff_coherence_score = ai_score_obj.diff_coherence if ai_scored and ai_score_obj else 5.0
    ai_slop_score = ai_score_obj.ai_slop_signals if ai_scored and ai_score_obj else 5.0
    breaking_score = ai_score_obj.breaking_awareness if ai_scored and ai_score_obj else 5.0

    scores: dict[str, float] = {
        "description": description_score,
        "diff_coherence": diff_coherence_score,
        "test_coverage": heuristic_scores.test_coverage,
        "commit_messages": heuristic_scores.commit_messages,
        "change_size": heuristic_scores.change_size,
        "ai_slop_signals": ai_slop_score,
        "breaking_awareness": breaking_score,
    }

    overall_score = round(
        scores["description"] * w.description
        + scores["diff_coherence"] * w.diff_coherence
        + scores["test_coverage"] * w.test_coverage
        + scores["commit_messages"] * w.commit_messages
        + scores["change_size"] * w.change_size
        + scores["ai_slop_signals"] * w.ai_slop_signals
        + scores["breaking_awareness"] * w.breaking_awareness,
        2,
    )

    # ── Flags ─────────────────────────────────────────────────────────────────
    flags: list[str] = list(ai_score_obj.flags if ai_score_obj else [])

    if heuristic_scores.test_coverage < 5.0:
        flags.append("⚠️ Test coverage below threshold for diff size")
    if heuristic_scores.change_size < 5.0:
        flags.append(f"⚠️ Large change ({heuristic_scores.total_lines} lines changed)")
    if heuristic_scores.commit_messages < 5.0:
        flags.append("⚠️ One or more commit messages lack sufficient context")

    # ── Notes ─────────────────────────────────────────────────────────────────
    ai_notes = ai_score_obj.notes if ai_score_obj else {}
    notes = _build_notes(heuristic_scores, ai_notes, ai_scored)

    # ── Post comment ──────────────────────────────────────────────────────────
    print("Posting PR comment …")
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    comment_body = render_comment(
        scores=scores,
        overall_score=overall_score,
        flags=flags,
        notes=notes,
        ai_scored=ai_scored,
        min_score=config.scoring.min_score,
    )
    post_comment(pr, comment_body)

    # ── Labels ────────────────────────────────────────────────────────────────
    if label_prs and config.labels.enabled:
        print("Applying labels …")
        apply_labels(pr, overall_score, ai_slop_score, config)

    # ── Commit status ─────────────────────────────────────────────────────────
    if block_on_fail:
        print("Setting commit status …")
        set_commit_status(
            github_token,
            repo_name,
            pr_data.head_sha,
            overall_score,
            config.scoring.min_score,
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = overall_score >= config.scoring.min_score
    print(
        f"\nPR #{pr_number} scored {overall_score:.1f}/10 "
        f"({'PASS ✅' if passed else 'FAIL ❌'}, threshold {config.scoring.min_score:.1f})"
    )

    # Write Action outputs
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"score={overall_score}\n")
            f.write(f"passed={'true' if passed else 'false'}\n")

    if not passed and block_on_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
