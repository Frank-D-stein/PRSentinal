"""Unit tests for configuration loading."""
from __future__ import annotations

from pathlib import Path

from src.config import load_config


def test_load_config_returns_defaults_for_missing_file(tmp_path: Path):
    config = load_config(str(tmp_path / "missing.yml"))

    assert config.scoring.min_score == 6.0
    assert config.thresholds.max_diff_lines == 800
    assert config.labels.enabled is True


def test_load_config_reads_overrides(tmp_path: Path):
    config_path = tmp_path / "pr-sentinel.yml"
    config_path.write_text(
        "\n".join(
            [
                "scoring:",
                "  min_score: 7.5",
                "thresholds:",
                "  max_diff_lines: 500",
                "labels:",
                "  enabled: false",
                "exemptions:",
                "  labels:",
                "    - skip-pr-sentinel",
            ]
        )
    )

    config = load_config(str(config_path))

    assert config.scoring.min_score == 7.5
    assert config.thresholds.max_diff_lines == 500
    assert config.labels.enabled is False
    assert config.exemptions.labels == ["skip-pr-sentinel"]
