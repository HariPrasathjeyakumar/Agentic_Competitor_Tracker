"""Tests for src/diff_engine.py normalization, thresholds, baseline, and timestamped scans."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from src.diff_engine import diff_snapshots, find_previous_snapshot, normalize
from src.scout import save_snapshot_text


def test_normalize_collapses_whitespace_and_strips_dates_times_boilerplate() -> None:
    raw = (
        "Copyright 2026 Locus Labs\n"
        "Cookie Settings | All\n"
        "Privacy Policy\n"
        "Terms of Service\n"
        "Last updated: Nov 23, 2026 at 09:14 AM\n"
        "Release   on   2026-11-23   and   23 November 2026  at 9:14 AM\n"
        "Added    one-click   thread   summaries\n"
    )
    norm = normalize(raw)
    lines = norm.splitlines()
    assert not any(line.startswith(("Copyright", "Cookie", "Privacy", "Terms")) for line in lines)
    assert "Nov 23, 2026" not in norm
    assert "2026-11-23" not in norm
    assert "23 November 2026" not in norm
    assert "09:14" not in norm
    assert "9:14 AM" not in norm
    assert "Added one-click thread summaries" in norm


def test_threshold_drops_small_diffs(tmp_path: Path) -> None:
    prev = tmp_path / "2026-11-15_090000_000001.md"
    curr = tmp_path / "2026-11-23_090000_000001.md"
    prev.write_text("Existing changelog entry line one.", encoding="utf-8")
    curr.write_text("Existing changelog entry line one.\nTiny fix.", encoding="utf-8")

    ev = diff_snapshots("Locus", "changelog", curr, prev, min_diff_chars=60)
    assert ev is None


def test_baseline_returns_none_when_no_previous_snapshot(tmp_path: Path) -> None:
    snap_dir = tmp_path / "locus" / "changelog"
    snap_dir.mkdir(parents=True)
    curr = snap_dir / "2026-11-15_090000_000001.md"
    curr.write_text("Initial baseline content.", encoding="utf-8")

    prev = find_previous_snapshot(snap_dir, curr)
    assert prev is None
    assert diff_snapshots("Locus", "changelog", curr, prev, min_diff_chars=60) is None


def test_same_day_timestamped_scans_do_not_overwrite(tmp_path: Path) -> None:
    p1 = save_snapshot_text(
        "Locus", "changelog", date(2026, 11, 23),
        "Baseline line one for Locus.", tmp_path, scan_id="2026-11-23_090000_000001"
    )
    p2 = save_snapshot_text(
        "Locus", "changelog", date(2026, 11, 23),
        "Baseline line one for Locus.\nLocus AI: summarize any thread in one click across all engineering channels today.",
        tmp_path,
        scan_id="2026-11-23_090500_000001",
    )
    assert p1.exists() and p2.exists() and p1 != p2
    prev = find_previous_snapshot(p2.parent, p2)
    assert prev == p1
    ev = diff_snapshots("Locus", "changelog", p2, prev, min_diff_chars=60)
    assert ev is not None
    assert "Locus AI: summarize any thread in one click" in ev.added_text
