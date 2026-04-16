"""Claude API scoring pass for AI-evaluated PR quality dimensions."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from anthropic import Anthropic
from jinja2 import Environment, FileSystemLoader


@dataclass
class AIScores:
    description_quality: float
    diff_coherence: float
    ai_slop_signals: float
    breaking_awareness: float
    notes: dict[str, str] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


_DEFAULT_NOTES: dict[str, str] = {
    "description": "Not evaluated",
    "diff_coherence": "Not evaluated",
    "ai_slop_signals": "Not evaluated",
    "breaking_awareness": "Not evaluated",
}

# Maximum characters of diff to send to the AI to keep costs down
_MAX_DIFF_CHARS = 8_000


def _parse_ai_response(text: str) -> dict:
    """Extract a JSON object from the AI response, handling markdown code fences."""
    # Try fenced code block first
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))
    # Fallback: bare JSON object
    bare = re.search(r"\{.*\}", text, re.DOTALL)
    if bare:
        return json.loads(bare.group())
    return {}


def run_ai_scoring(
    diff: str,
    pr_body: str,
    pr_title: str,
    commits: list[dict],
    api_key: str,
    prompts_dir: str | None = None,
) -> AIScores:
    """Call the Claude API to score AI-specific PR quality dimensions."""
    if prompts_dir is None:
        prompts_dir = str(Path(__file__).parent.parent / "prompts")

    client = Anthropic(api_key=api_key)

    env = Environment(loader=FileSystemLoader(prompts_dir), autoescape=False)
    template = env.get_template("score.j2")

    prompt = template.render(
        diff=diff[:_MAX_DIFF_CHARS],
        diff_truncated=len(diff) > _MAX_DIFF_CHARS,
        pr_body=pr_body or "(no description provided)",
        pr_title=pr_title,
        commits=commits,
    )

    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    try:
        data = _parse_ai_response(response_text)
    except (json.JSONDecodeError, AttributeError):
        data = {}

    def _clamp(val: object, default: float = 5.0) -> float:
        try:
            return max(0.0, min(10.0, float(val)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    notes = data.get("notes", {})
    if not isinstance(notes, dict):
        notes = {}

    return AIScores(
        description_quality=_clamp(data.get("description_quality")),
        diff_coherence=_clamp(data.get("diff_coherence")),
        ai_slop_signals=_clamp(data.get("ai_slop_signals")),
        breaking_awareness=_clamp(data.get("breaking_awareness")),
        notes={
            "description": str(notes.get("description", "AI-evaluated")),
            "diff_coherence": str(notes.get("diff_coherence", "AI-evaluated")),
            "ai_slop_signals": str(notes.get("ai_slop_signals", "AI-evaluated")),
            "breaking_awareness": str(notes.get("breaking_awareness", "AI-evaluated")),
        },
        flags=[str(f) for f in data.get("flags", []) if f],
    )
