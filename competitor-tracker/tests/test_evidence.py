"""Tests for src/evidence.py verbatim quote verification."""

from __future__ import annotations

from src.evidence import normalize_ws, verify_quote


def test_exact_match_passes() -> None:
    src = "Locus AI: summarize any thread in one click across engineering channels."
    assert verify_quote("summarize any thread in one click", src) is True


def test_invented_quote_fails() -> None:
    src = "Locus AI: summarize any thread in one click across engineering channels."
    assert verify_quote("Locus launched enterprise video conferencing", src) is False


def test_whitespace_and_case_differences_pass() -> None:
    src = "Locus AI:\n  summarize   any\tthread in   one click today."
    assert verify_quote("locus ai: summarize any thread in one click", src) is True
    assert normalize_ws("  A\n\t B  ") == "a b"


def test_short_quote_under_15_chars_fails() -> None:
    src = "Locus AI now ships fast summaries."
    assert verify_quote("fast summaries", src) is False
