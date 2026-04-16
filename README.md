# PR Sentinel

PR Sentinel is a Docker-based GitHub Action that reviews incoming pull requests and produces a review-readiness score before a human reviewer steps in.

It combines:
- Fast heuristics for change size, test coverage, and commit quality
- Optional Anthropic scoring for PR description quality, diff coherence, AI-slop signals, and breaking-change awareness
- A PR comment with the score breakdown
- Optional labels and a failing status check when a PR misses the bar

## What It Needs

To run in GitHub Actions:
- A GitHub repository with Actions enabled
- A workflow that runs on `pull_request`
- `GITHUB_TOKEN` permissions to read the repo and write PR metadata
- An `ANTHROPIC_API_KEY` secret if you want the AI scoring pass

To run locally:
- Python 3.11+
- `pip`
- A GitHub token
- An Anthropic API key only if you want AI scoring locally

Python dependencies are declared in [pyproject.toml](C:/Users/dillo/PRSentinal/pyproject.toml:1).

## Quick Start

### Use It In This Repo

```yaml
name: PR Sentinel

on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read
  pull-requests: write
  issues: write
  statuses: write

jobs:
  pr-sentinel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          min-score: "6.0"
          block-on-fail: "true"
          label-prs: "true"
```

### Use It From Another Repo

There are no release tags yet, so pin a commit SHA until the action is versioned.

```yaml
- uses: Frank-D-stein/PRSentinal@<commit-sha>
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Inputs

- `anthropic-api-key`: Optional. Enables the AI scoring pass.
- `github-token`: Optional in workflows, but required in practice for GitHub API access.
- `min-score`: Minimum passing score from `0.0` to `10.0`. Default `6.0`.
- `block-on-fail`: If `true`, the action sets a failing status and exits non-zero when the PR misses the threshold.
- `label-prs`: If `true`, applies quality labels to the PR.
- `config-path`: Path to the config file. Default `.github/pr-sentinel.yml`.

## Outputs

- `score`: The overall PR score
- `passed`: `true` when the PR meets or exceeds `min-score`

## Configuration

Create `.github/pr-sentinel.yml` to override defaults:

```yaml
scoring:
  min_score: 6.0
  weights:
    description: 0.20
    diff_coherence: 0.20
    test_coverage: 0.20
    commit_messages: 0.15
    change_size: 0.10
    ai_slop_signals: 0.10
    breaking_awareness: 0.05

thresholds:
  max_diff_lines: 800
  min_test_ratio: 0.15

labels:
  enabled: true
  low: quality/needs-work
  medium: quality/ok
  high: quality/excellent
  ai_generated: likely-ai-generated

exemptions:
  authors: []
  labels:
    - skip-pr-sentinel
  paths:
    - docs/**
    - "**/*.md"
```

## Scoring Model

PR Sentinel scores these dimensions:
- `description`: How well the PR explains why the change exists
- `diff_coherence`: Whether the diff matches the description and commit story
- `test_coverage`: How much test code was added relative to non-test code
- `commit_messages`: Whether commit messages are descriptive and structured
- `change_size`: Whether the diff is reviewable in scope
- `ai_slop_signals`: Whether the code looks boilerplate-heavy or low-signal
- `breaking_awareness`: Whether breaking changes are acknowledged

If AI scoring is skipped, the overall score is reweighted to use only the heuristic dimensions instead of silently treating missing AI dimensions as neutral.

## Local Development

```powershell
git clone https://github.com/Frank-D-stein/PRSentinal.git
cd PRSentinal
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

To run the action logic locally:

```powershell
$env:GITHUB_TOKEN = "..."
$env:GITHUB_REPOSITORY = "owner/repo"
$env:PR_NUMBER = "123"
$env:ANTHROPIC_API_KEY = "..."  # optional
python -m src.main
```

## How It Behaves

- Fetches PR metadata and the unified diff from GitHub
- Runs local heuristics first
- Runs the AI pass only when an Anthropic key is present and the changed files are not fully exempted
- Posts or updates a single PR Sentinel comment
- Optionally applies labels
- Optionally sets a failing commit status

## Limitations

- The AI pass only sees the first portion of large diffs
- The quality score is directional, not a substitute for human review
- The action is not tagged yet, so remote consumers should pin a commit SHA
