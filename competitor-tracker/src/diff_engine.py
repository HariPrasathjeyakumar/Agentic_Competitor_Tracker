"""Deterministic text normalization and line-level diff engine."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src import PROJECT_ROOT, resolve_path
from src.scout import slugify

_BOILERPLATE_PREFIXES = ("copyright", "cookie", "privacy", "terms")

_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)
_DATE_RE = re.compile(
    rf"(?:\b(?:{_MONTH_NAMES})\.?\s+\d{{1,2}},?\s+\d{{4}}\b"
    rf"|\b\d{{1,2}}\s+(?:{_MONTH_NAMES})\.?\s+\d{{4}}\b"
    rf"|\b\d{{4}}-\d{{2}}-\d{{2}}\b)",
    flags=re.IGNORECASE,
)
_TIME_RE = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM))?\b",
    flags=re.IGNORECASE,
)


@dataclass
class DiffEvent:
    competitor: str
    page: str
    as_of: str
    old_text: str
    new_text: str
    added_text: str
    char_count: int


def normalize(text: str) -> str:
    """Normalize snapshot text by stripping boilerplate lines, dates, times, and extra whitespace."""
    if not text:
        return ""
    cleaned_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = line.lower()
        if any(lowered.startswith(prefix) for prefix in _BOILERPLATE_PREFIXES):
            continue
        line = _DATE_RE.sub("", line)
        line = _TIME_RE.sub("", line)
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _extract_date_prefix(path: Path) -> str:
    return path.stem[:10]


def find_previous_snapshot(snapshot_dir: Path, current_ref: date | str | Path) -> Path | None:
    """Return the most recent snapshot strictly preceding current_ref (Path or date)."""
    if not snapshot_dir.exists():
        return None
    candidates = sorted(snapshot_dir.glob("*.md"), key=lambda p: p.stem)
    if not candidates:
        return None

    if isinstance(current_ref, Path):
        prior = [p for p in candidates if p.stem < current_ref.stem]
        return prior[-1] if prior else None

    as_of_str = current_ref.isoformat() if isinstance(current_ref, date) else str(current_ref)[:10]
    prior = [p for p in candidates if _extract_date_prefix(p) < as_of_str]
    return prior[-1] if prior else None


def find_current_snapshot(snapshot_dir: Path, as_of: date) -> Path | None:
    """Find the latest snapshot matching the given as_of date prefix."""
    if not snapshot_dir.exists():
        return None
    as_of_str = as_of.isoformat()
    matching = sorted(
        (p for p in snapshot_dir.glob("*.md") if _extract_date_prefix(p) == as_of_str),
        key=lambda p: p.stem,
    )
    return matching[-1] if matching else None


def diff_snapshots(
    competitor: str,
    page: str,
    current_path: Path,
    previous_path: Path | None,
    min_diff_chars: int,
    as_of: str | None = None,
) -> DiffEvent | None:
    """Compute normalized added lines between previous_path and current_path."""
    if previous_path is None:
        return None

    old_raw = previous_path.read_text(encoding="utf-8")
    new_raw = current_path.read_text(encoding="utf-8")
    old_norm = normalize(old_raw)
    new_norm = normalize(new_raw)

    added_lines: list[str] = []
    for line in difflib.ndiff(old_norm.splitlines(), new_norm.splitlines()):
        if line.startswith("+ "):
            content = line[2:].strip()
            if content:
                added_lines.append(content)

    added_text = "\n".join(added_lines).strip()
    if len(added_text) < min_diff_chars:
        return None

    resolved_as_of = as_of if as_of is not None else _extract_date_prefix(current_path)
    return DiffEvent(
        competitor=competitor,
        page=page,
        as_of=resolved_as_of,
        old_text=old_raw,
        new_text=new_raw,
        added_text=added_text,
        char_count=len(added_text),
    )


def run_diff(
    config: dict[str, Any],
    as_of: date,
    current_paths: list[Path] | None = None,
    base_dir: Path | None = None,
) -> tuple[list[DiffEvent], dict[str, int]]:
    """Diff newly captured or latest snapshots against their immediately preceding scan."""
    root = base_dir if base_dir is not None else PROJECT_ROOT
    snapshots_dir = resolve_path(config, "snapshots_dir", base_dir=root)
    min_diff_chars = int(config.get("thresholds", {}).get("min_diff_chars", 60))

    path_lookup: dict[tuple[str, str], Path] = {}
    if current_paths:
        for p in current_paths:
            # Expected layout: snapshots_dir / <comp_slug> / <page> / <scan>.md
            page_name = p.parent.name
            comp_slug = p.parent.parent.name
            path_lookup[(comp_slug, page_name)] = p

    events: list[DiffEvent] = []
    stats = {
        "pages_checked": 0,
        "baseline": 0,
        "below_threshold": 0,
        "changed": 0,
    }

    for comp in config.get("competitors", []):
        name = str(comp["name"])
        comp_slug = slugify(name)
        for page_name in ("changelog", "pricing"):
            page_dir = snapshots_dir / comp_slug / page_name
            current_path = path_lookup.get((comp_slug, page_name)) or find_current_snapshot(page_dir, as_of)
            if current_path is None or not current_path.exists():
                continue

            stats["pages_checked"] += 1
            prev_path = find_previous_snapshot(page_dir, current_path)
            if prev_path is None:
                stats["baseline"] += 1
                continue

            diff_ev = diff_snapshots(
                competitor=name,
                page=page_name,
                current_path=current_path,
                previous_path=prev_path,
                min_diff_chars=min_diff_chars,
                as_of=as_of.isoformat(),
            )
            if diff_ev is None:
                stats["below_threshold"] += 1
            else:
                stats["changed"] += 1
                events.append(diff_ev)

    return events, stats
