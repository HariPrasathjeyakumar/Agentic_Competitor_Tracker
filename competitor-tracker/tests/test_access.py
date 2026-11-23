"""Tests enforcing strict code-level information barriers across agents."""

from __future__ import annotations

import json

from src import load_config
from src.diff_engine import DiffEvent
from src.llm import FakeLLMClient
from src.pipeline import process_diff_event


def test_information_barriers_across_agents() -> None:
    cfg = load_config()
    product_desc = cfg["product"]["description"]
    unique_added = (
        "Introducing Quantum-Safe Channel Encryption across all engineering threads, "
        "allowing workspaces to rotate keys every hour with zero configuration."
    )
    full_snapshot = (
        "HEADER NAVIGATION BAR\n"
        f"{unique_added}\n"
        "UNIQUE_FULL_SNAPSHOT_MARKER_991\n"
        "Copyright 2026 Locus Labs Inc."
    )

    diff_ev = DiffEvent(
        competitor="Locus",
        page="changelog",
        as_of="2026-11-23",
        old_text="HEADER NAVIGATION BAR\nCopyright 2026 Locus Labs Inc.",
        new_text=full_snapshot,
        added_text=unique_added,
        char_count=len(unique_added),
    )

    fake = FakeLLMClient(
        responses={
            "classifier": json.dumps({
                "is_feature_launch": True,
                "category": "new_feature",
                "feature_name": "Quantum-Safe Channel Encryption",
                "confidence": 0.95,
            }),
            "analyst": json.dumps({
                "threat_level": "MEDIUM",
                "reasoning": (
                    "This release strengthens Locus's security positioning for small engineering teams. "
                    "TeamChat should compare this against our self-hosted deployment story."
                ),
                "evidence_quote": "Quantum-Safe Channel Encryption across all engineering threads",
                "overlaps_roadmap_item": "Self-hosted deployment option",
                "confidence": 0.88,
            }),
            "strategist": json.dumps({
                "recommendation": "differentiate",
                "actions": ["Highlight self-hosted deployment and zero-cloud key ownership."],
                "contests_analyst": False,
                "contest_reason": None,
            }),
        }
    )

    record = process_diff_event(diff_ev, config=cfg, llm=fake, ablation="full")
    assert record["status"] == "confirmed"
    assert len(fake.history) == 3

    cls_prompt = next(item["prompt"] for item in fake.history if item["agent"] == "classifier")
    ana_prompt = next(item["prompt"] for item in fake.history if item["agent"] == "analyst")
    str_prompt = next(item["prompt"] for item in fake.history if item["agent"] == "strategist")

    # Classifier must NOT see product description, key features, or full snapshot marker
    assert product_desc not in cls_prompt
    assert "File sharing up to 100 MB" not in cls_prompt
    assert "UNIQUE_FULL_SNAPSHOT_MARKER_991" not in cls_prompt
    assert unique_added in cls_prompt

    # Analyst must NOT see full snapshot marker or strategist output
    assert "UNIQUE_FULL_SNAPSHOT_MARKER_991" not in ana_prompt
    assert "Highlight self-hosted deployment" not in ana_prompt
    assert product_desc in ana_prompt
    assert unique_added in ana_prompt

    # Strategist must NOT see raw added text or full snapshot marker
    assert unique_added not in str_prompt
    assert "UNIQUE_FULL_SNAPSHOT_MARKER_991" not in str_prompt
    assert product_desc in str_prompt
    assert "Quantum-Safe Channel Encryption across all engineering threads" in str_prompt  # via Analyst's evidence_quote JSON
