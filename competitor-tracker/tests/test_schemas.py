"""Tests for src/schemas.py Pydantic v2 validation and JSON parsing."""

from __future__ import annotations

import pytest

from src.schemas import AnalystOutput, ClassifierOutput, StrategistOutput, parse_json_output


def test_classifier_output_valid_and_invalid() -> None:
    valid = ClassifierOutput(
        is_feature_launch=True,
        category="new_feature",
        feature_name="Thread Summaries",
        confidence=0.92,
    )
    assert valid.is_feature_launch is True

    with pytest.raises(Exception):
        ClassifierOutput(
            is_feature_launch="yes",  # strict bool
            category="new_feature",
            feature_name="Thread Summaries",
            confidence=0.92,
        )

    with pytest.raises(Exception):
        ClassifierOutput(
            is_feature_launch=False,
            category="unknown_cat",
            feature_name=None,
            confidence=0.5,
        )


def test_analyst_output_valid_and_invalid() -> None:
    valid = AnalystOutput(
        threat_level="HIGH",
        reasoning="First clear sentence explaining impact. Second sentence detailing overlap with TeamChat.",
        evidence_quote="summarize any thread in one click",
        overlaps_roadmap_item="Channels and threads",
        confidence=0.88,
    )
    assert valid.threat_level == "HIGH"

    # Too short evidence quote (< 15 chars)
    with pytest.raises(Exception):
        AnalystOutput(
            threat_level="LOW",
            reasoning="First sentence here. Second sentence here.",
            evidence_quote="too short",
            overlaps_roadmap_item=None,
            confidence=0.7,
        )

    # Only 1 sentence in reasoning
    with pytest.raises(Exception):
        AnalystOutput(
            threat_level="LOW",
            reasoning="Only one single sentence of reasoning here without a second.",
            evidence_quote="summarize any thread in one click",
            overlaps_roadmap_item=None,
            confidence=0.7,
        )


def test_strategist_contest_reason_required_when_contesting() -> None:
    valid = StrategistOutput(
        recommendation="differentiate",
        actions=["Emphasize self-hosted privacy guarantees."],
        contests_analyst=True,
        contest_reason="The launch only affects cloud-only workspaces, not our self-hosted buyers.",
    )
    assert valid.contests_analyst is True

    with pytest.raises(Exception):
        StrategistOutput(
            recommendation="ignore",
            actions=["Do nothing for now."],
            contests_analyst=True,
            contest_reason=None,
        )

    with pytest.raises(Exception):
        StrategistOutput(
            recommendation="ignore",
            actions=["Do nothing for now."],
            contests_analyst=True,
            contest_reason="   ",
        )


def test_parse_json_output_strips_markdown_fences() -> None:
    raw = (
        "Here is the classification result:\n"
        "```json\n"
        '{"is_feature_launch": false, "category": "bug_fix", "feature_name": null, "confidence": 0.95}\n'
        "```\n"
        "Hope that helps!"
    )
    parsed = parse_json_output(raw, ClassifierOutput)
    assert parsed.is_feature_launch is False
    assert parsed.category == "bug_fix"
