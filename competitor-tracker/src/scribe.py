"""Scribe module for atomic feed persistence and stdout digest formatting."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def append_event(feed_path: str | Path, event: dict[str, Any]) -> None:
    """Append one event record to feed_path JSON array using a Windows-safe atomic replace."""
    target = Path(feed_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    events: list[dict[str, Any]] = []
    if target.exists():
        raw = target.read_text(encoding="utf-8").strip()
        if raw:
            loaded = json.loads(raw)
            if isinstance(loaded, list):
                events = loaded

    events.append(event)

    fd, tmp_name = tempfile.mkstemp(prefix=".feed_", suffix=".tmp", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(events, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def digest_line(event: dict[str, Any]) -> str:
    """Format a concise one-line human-readable digest for an event record."""
    competitor = event.get("competitor", "Unknown")
    status = event.get("status", "unknown")
    classifier = event.get("classifier") or {}
    analyst = event.get("analyst") or {}
    strategist = event.get("strategist") or {}

    if status == "dismissed":
        category = classifier.get("category", "noise")
        return f"[DISMISSED] {competitor}: {category} ({event.get('page', '')})"

    if status == "invalid_evidence":
        threat = analyst.get("threat_level", "UNKNOWN")
        return f"[INVALID_EVIDENCE/{threat}] {competitor}: quote not found in snapshot"

    if status == "parse_failed":
        return f"[PARSE_FAILED] {competitor}: {event.get('status_reason', 'agent output invalid')}"

    threat = analyst.get("threat_level", "INFO")
    feature = classifier.get("feature_name") or event.get("page", "feature change")
    rec = strategist.get("recommendation", "monitor")
    contested = "yes" if event.get("contested") else "no"
    return f"[{threat}] {competitor}: {feature} (strategist: {rec}, contested: {contested})"


def print_digest(event: dict[str, Any]) -> None:
    """Print the formatted digest line to stdout."""
    print(digest_line(event))
