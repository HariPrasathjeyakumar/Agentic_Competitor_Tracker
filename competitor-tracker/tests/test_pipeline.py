"""End-to-end pipeline and ablation tests using FakeLLMClient."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src import load_config
from src.dataset import generate_dataset
from src.evaluate import run_evaluation
from src.llm import FakeLLMClient
from src.pipeline import run_monitor_cycle
from src.scout import save_snapshot_text


def _setup_workspace(tmp_path: Path) -> dict:
    cfg = load_config()
    cfg["paths"]["snapshots_dir"] = str(tmp_path / "snapshots")
    cfg["paths"]["cache_dir"] = str(tmp_path / "cache")
    cfg["paths"]["feed_path"] = str(tmp_path / "feed.json")
    cfg["paths"]["labels_dir"] = str(tmp_path / "labels")
    cfg["paths"]["eval_report_json"] = str(tmp_path / "eval_report.json")
    cfg["paths"]["eval_report_md"] = str(tmp_path / "eval_report.md")
    cfg["paths"]["logs_dir"] = str(tmp_path / "logs")
    cfg["paths"]["heldout_flag_path"] = str(tmp_path / "labels" / "heldout_used.flag")
    cfg["competitors"] = [
        {
            "name": "Locus",
            "changelog_url": "http://127.0.0.1:5001/changelog",
            "pricing_url": "http://127.0.0.1:5001/pricing",
        }
    ]
    return cfg


def _seed_day1_and_patch_scout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cfg: dict, new_changelog: str) -> None:
    snap_dir = Path(cfg["paths"]["snapshots_dir"])
    save_snapshot_text("Locus", "changelog", date(2026, 11, 15), "Initial changelog baseline entry.", snap_dir, scan_id="2026-11-15_090000_000001")
    save_snapshot_text("Locus", "pricing", date(2026, 11, 15), "Free plan $0. Team plan $8.", snap_dir, scan_id="2026-11-15_090000_000001")

    def fake_run_scout(config, as_of, base_dir=None, scan_id=None):
        p1 = save_snapshot_text("Locus", "changelog", as_of, new_changelog, snap_dir, scan_id="2026-11-23_090000_000001")
        p2 = save_snapshot_text("Locus", "pricing", as_of, "Free plan $0. Team plan $8.", snap_dir, scan_id="2026-11-23_090000_000001")
        return [p1, p2]

    monkeypatch.setattr("src.pipeline.run_scout", fake_run_scout)


def test_full_cycle_confirmed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    added = "Locus AI: summarize any thread in one click across every engineering channel starting today."
    _seed_day1_and_patch_scout(monkeypatch, tmp_path, cfg, f"Initial changelog baseline entry.\n{added}")

    fake = FakeLLMClient({
        "classifier": json.dumps({
            "is_feature_launch": True,
            "category": "new_feature",
            "feature_name": "Locus AI Thread Summarization",
            "confidence": 0.94,
        }),
        "analyst": json.dumps({
            "threat_level": "HIGH",
            "reasoning": "Locus launched AI summaries directly targeting busy engineering threads. This adds competitive pressure on TeamChat.",
            "evidence_quote": "summarize any thread in one click across every engineering channel",
            "overlaps_roadmap_item": "Channels and threads",
            "confidence": 0.9,
        }),
        "strategist": json.dumps({
            "recommendation": "differentiate",
            "actions": ["Emphasize privacy-first self-hosted AI controls."],
            "contests_analyst": False,
            "contest_reason": None,
        }),
    })

    summary = run_monitor_cycle(cfg, as_of=date(2026, 11, 23), llm=fake, ablation="full")
    assert summary["counts"]["confirmed"] == 1
    feed = json.loads(Path(cfg["paths"]["feed_path"]).read_text(encoding="utf-8"))
    assert len(feed) == 1
    assert feed[0]["status"] == "confirmed"


def test_non_launch_yields_dismissed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    added = "Fixed a desktop notification memory leak on Windows 11 and macOS Sonoma without altering features."
    _seed_day1_and_patch_scout(monkeypatch, tmp_path, cfg, f"Initial changelog baseline entry.\n{added}")

    fake = FakeLLMClient({
        "classifier": json.dumps({
            "is_feature_launch": False,
            "category": "bug_fix",
            "feature_name": None,
            "confidence": 0.96,
        }),
    })

    summary = run_monitor_cycle(cfg, as_of=date(2026, 11, 23), llm=fake, ablation="full")
    assert summary["counts"]["dismissed"] == 1
    assert fake.calls_made == 1  # Analyst and Strategist never called


def test_bad_quote_yields_invalid_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    added = "Locus AI: summarize any thread in one click across every engineering channel starting today."
    _seed_day1_and_patch_scout(monkeypatch, tmp_path, cfg, f"Initial changelog baseline entry.\n{added}")

    fake = FakeLLMClient({
        "classifier": json.dumps({
            "is_feature_launch": True,
            "category": "new_feature",
            "feature_name": "Locus AI",
            "confidence": 0.91,
        }),
        "analyst": json.dumps({
            "threat_level": "HIGH",
            "reasoning": "Locus launched a major feature. This directly challenges TeamChat core workflows.",
            "evidence_quote": "completely hallucinated quote not in snapshot",
            "overlaps_roadmap_item": None,
            "confidence": 0.85,
        }),
    })

    summary = run_monitor_cycle(cfg, as_of=date(2026, 11, 23), llm=fake, ablation="full")
    assert summary["counts"]["invalid_evidence"] == 1
    assert fake.calls_made == 2  # Stopped before Strategist


def test_second_bad_json_yields_parse_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    added = "Locus AI: summarize any thread in one click across every engineering channel starting today."
    _seed_day1_and_patch_scout(monkeypatch, tmp_path, cfg, f"Initial changelog baseline entry.\n{added}")

    fake = FakeLLMClient({
        "classifier": ["not json at all", "still invalid json!"],
    })

    summary = run_monitor_cycle(cfg, as_of=date(2026, 11, 23), llm=fake, ablation="full")
    assert summary["counts"]["parse_failed"] == 1
    assert fake.calls_made == 2  # Original + 1 retry


def test_no_classifier_ablation_skips_classifier(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    added = "Updated spacing and padding in the sidebar navigation links without adding new capabilities."
    _seed_day1_and_patch_scout(monkeypatch, tmp_path, cfg, f"Initial changelog baseline entry.\n{added}")

    fake = FakeLLMClient({
        "analyst": json.dumps({
            "threat_level": "LOW",
            "reasoning": "Minor UI polish update detected on changelog. No functional impact on TeamChat users.",
            "evidence_quote": "Updated spacing and padding in the sidebar navigation",
            "overlaps_roadmap_item": None,
            "confidence": 0.8,
        }),
        "strategist": json.dumps({
            "recommendation": "ignore",
            "actions": ["No action needed for cosmetic spacing updates."],
            "contests_analyst": False,
            "contest_reason": None,
        }),
    })

    summary = run_monitor_cycle(cfg, as_of=date(2026, 11, 23), llm=fake, ablation="no_classifier")
    assert summary["counts"]["confirmed"] == 1
    assert summary["events"][0]["classifier"] is None
    assert "classifier" not in summary["events"][0]["models"]


def test_three_layer_heldout_lock(tmp_path: Path) -> None:
    cfg = _setup_workspace(tmp_path)
    generate_dataset(config=cfg)

    # Layer 1: missing --final
    with pytest.raises(PermissionError, match="--final"):
        run_evaluation(split="heldout", dry_run=True, final=False, config=cfg)

    # Layer 2: held_out_locked: true in config
    with pytest.raises(PermissionError, match="held_out_locked"):
        run_evaluation(split="heldout", dry_run=True, final=True, config=cfg)

    # Unlock config and run once -> succeeds and writes flag
    cfg["evaluation"]["held_out_locked"] = False
    report = run_evaluation(split="heldout", ablation="full", dry_run=True, final=True, config=cfg)
    assert report["split"] == "heldout"
    assert Path(cfg["paths"]["heldout_flag_path"]).exists()

    # Layer 3: second run is permanently blocked by heldout_used.flag
    with pytest.raises(PermissionError, match="already consumed"):
        run_evaluation(split="heldout", ablation="full", dry_run=True, final=True, config=cfg)
