"""GitHub API fetching for PR diff, description, and commits."""
from __future__ import annotations

from dataclasses import dataclass, field

import requests
from github import Github


@dataclass
class PRData:
    number: int
    title: str
    body: str
    author: str
    labels: list[str]
    diff: str
    commits: list[dict]
    changed_files: list[str]
    additions: int
    deletions: int
    head_sha: str


def fetch_pr_data(token: str, repo_name: str, pr_number: int) -> PRData:
    """Fetch all PR metadata, diff, and commits from the GitHub API."""
    g = Github(token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # Fetch unified diff via raw GitHub API
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    diff_resp = requests.get(pr.url, headers=headers, timeout=30)
    diff_resp.raise_for_status()
    diff = diff_resp.text

    # Collect commits
    commits: list[dict] = []
    for commit in pr.get_commits():
        commits.append(
            {
                "sha": commit.sha,
                "message": commit.commit.message,
                "author": commit.commit.author.name if commit.commit.author else "",
            }
        )

    # Collect changed file paths
    changed_files = [f.filename for f in pr.get_files()]

    return PRData(
        number=pr.number,
        title=pr.title,
        body=pr.body or "",
        author=pr.user.login,
        labels=[label.name for label in pr.labels],
        diff=diff,
        commits=commits,
        changed_files=changed_files,
        additions=pr.additions,
        deletions=pr.deletions,
        head_sha=pr.head.sha,
    )
